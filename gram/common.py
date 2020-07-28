# This file is Copyright (c) 2016-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2018 John Sully <john@csquare.ca>
# This file is Copyright (c) 2018 bunnie <bunnie@kosagi.com>
# This file is Copyright (c) 2020 LambdaConcept <contact@lambdaconcept.com>
# License: BSD

import math
from functools import reduce
from operator import add
from collections import OrderedDict

from nmigen import *
from nmigen.asserts import Assert, Assume
from nmigen.hdl.rec import *
from nmigen.utils import log2_int

import gram.stream as stream

# Helpers ------------------------------------------------------------------------------------------

burst_lengths = {
    "SDR":   1,
    "DDR":   4,
    "LPDDR": 4,
    "DDR2":  4,
    "DDR3":  8,
    "DDR4":  8
}


def get_cl_cw(memtype, tck):
    f_to_cl_cwl = OrderedDict()
    if memtype == "DDR2":
        f_to_cl_cwl[400e6] = (3, 2)
        f_to_cl_cwl[533e6] = (4, 3)
        f_to_cl_cwl[677e6] = (5, 4)
        f_to_cl_cwl[800e6] = (6, 5)
        f_to_cl_cwl[1066e6] = (7, 5)
    elif memtype == "DDR3":
        f_to_cl_cwl[800e6] = (6, 5)
        f_to_cl_cwl[1066e6] = (7, 6)
        f_to_cl_cwl[1333e6] = (10, 7)
        f_to_cl_cwl[1600e6] = (11, 8)
    elif memtype == "DDR4":
        f_to_cl_cwl[1600e6] = (11,  9)
    else:
        raise ValueError
    for f, (cl, cwl) in f_to_cl_cwl.items():
        if tck >= 2/f:
            return cl, cwl
    raise ValueError


def get_sys_latency(nphases, cas_latency):
    return math.ceil(cas_latency/nphases)


def get_sys_phases(nphases, sys_latency, cas_latency):
    dat_phase = sys_latency*nphases - cas_latency
    cmd_phase = (dat_phase - 1) % nphases
    return cmd_phase, dat_phase

# Settings -----------------------------------------------------------------------------------------


class Settings:
    def set_attributes(self, attributes):
        for k, v in attributes.items():
            setattr(self, k, v)


class PhySettings(Settings):
    def __init__(self, phytype, memtype, databits, dfi_databits,
                 nphases,
                 rdphase, wrphase,
                 rdcmdphase, wrcmdphase,
                 cl, read_latency, write_latency, nranks=1, cwl=None):
        self.set_attributes(locals())
        self.cwl = cl if cwl is None else cwl
        self.is_rdimm = False

    # Optional DDR3/DDR4 electrical settings:
    # rtt_nom: Non-Writes on-die termination impedance
    # rtt_wr: Writes on-die termination impedance
    # ron: Output driver impedance
    def add_electrical_settings(self, rtt_nom, rtt_wr, ron):
        assert self.memtype in ["DDR3", "DDR4"]
        self.set_attributes(locals())


class GeomSettings(Settings):
    def __init__(self, bankbits, rowbits, colbits):
        self.set_attributes(locals())
        self.addressbits = max(rowbits, colbits)


class TimingSettings(Settings):
    def __init__(self, tRP, tRCD, tWR, tWTR, tREFI, tRFC, tFAW, tCCD, tRRD, tRC, tRAS, tZQCS):
        self.set_attributes(locals())

# Layouts/Interface --------------------------------------------------------------------------------


def cmd_layout(address_width):
    return [
        ("valid",            1, DIR_FANOUT),
        ("ready",            1, DIR_FANIN),
        ("we",               1, DIR_FANOUT),
        ("addr", address_width, DIR_FANOUT),
        ("lock",             1, DIR_FANIN),  # only used internally

        ("wdata_ready",      1, DIR_FANIN),
        ("rdata_valid",      1, DIR_FANIN)
    ]


def data_layout(data_width):
    return [
        ("wdata",       data_width, DIR_FANOUT),
        ("wdata_we", data_width//8, DIR_FANOUT),
        ("rdata",       data_width, DIR_FANIN)
    ]


def cmd_description(address_width):
    return [
        ("we",   1),
        ("addr", address_width)
    ]


def wdata_description(data_width):
    return [
        ("data", data_width),
        ("we",   data_width//8)
    ]


def rdata_description(data_width):
    return [("data", data_width)]


def cmd_request_layout(a, ba):
    return [
        ("a",     a),
        ("ba",   ba),
        ("cas",   1),
        ("ras",   1),
        ("we",    1)
    ]


def cmd_request_rw_layout(a, ba):
    return cmd_request_layout(a, ba) + [
        ("is_cmd", 1),
        ("is_read", 1),
        ("is_write", 1)
    ]


class gramInterface(Record):
    def __init__(self, address_align, settings):
        rankbits = log2_int(settings.phy.nranks)
        self.address_align = address_align
        self.address_width = settings.geom.rowbits + \
            settings.geom.colbits + rankbits - address_align
        self.data_width = settings.phy.dfi_databits*settings.phy.nphases
        self.nbanks = settings.phy.nranks*(2**settings.geom.bankbits)
        self.nranks = settings.phy.nranks
        self.settings = settings

        layout = [("bank"+str(i), cmd_layout(self.address_width))
                  for i in range(self.nbanks)]
        layout += data_layout(self.data_width)
        Record.__init__(self, layout)

# Ports --------------------------------------------------------------------------------------------


class gramNativePort(Settings):
    def __init__(self, mode, address_width, data_width, clock_domain="sync", id=0):
        self.set_attributes(locals())

        if mode not in ["both", "read", "write"]:
            raise ValueError("mode must be either both/read/write, not {!r}".format(mode))

        self.lock = Signal()

        self.cmd = stream.Endpoint(cmd_description(address_width))
        self.wdata = stream.Endpoint(wdata_description(data_width))
        self.rdata = stream.Endpoint(rdata_description(data_width))

        self.flush = Signal()

    def get_bank_address(self, bank_bits, cba_shift):
        cba_upper = cba_shift + bank_bits
        return self.cmd.addr[cba_shift:cba_upper]

    def get_row_column_address(self, bank_bits, rca_bits, cba_shift):
        cba_upper = cba_shift + bank_bits
        if cba_shift < rca_bits:
            if cba_shift:
                return Cat(self.cmd.addr[:cba_shift], self.cmd.addr[cba_upper:])
            else:
                return self.cmd.addr[cba_upper:]
        else:
            return self.cmd.addr[:cba_shift]


# Timing Controllers -------------------------------------------------------------------------------

class tXXDController(Elaboratable):
    def __init__(self, txxd):
        self.valid = Signal()
        self.ready = ready = Signal(reset=txxd is None, attrs={"no_retiming": True})
        self._txxd = txxd

    def elaborate(self, platform):
        m = Module()

        if self._txxd is not None:
            count = Signal(range(max(self._txxd, 2)))
            with m.If(self.valid):
                m.d.sync += [
                    count.eq(self._txxd-1),
                    self.ready.eq((self._txxd - 1) == 0),
                ]
            with m.Elif(~self.ready):
                m.d.sync += count.eq(count-1)
                with m.If(count == 1):
                    m.d.sync += self.ready.eq(1)

        if platform == "formal":
            if self._txxd is not None and self._txxd > 0:
                hasSeenValid = Signal()
                with m.If(self.valid):
                    m.d.sync += hasSeenValid.eq(1)

                m.d.sync += Assert((hasSeenValid & (count == 0)).implies(self.ready == 1))

        return m


class tFAWController(Elaboratable):
    def __init__(self, tfaw):
        self.valid = Signal()
        self.ready = Signal(reset=1, attrs={"no_retiming": True})
        self._tfaw = tfaw

    def elaborate(self, platform):
        m = Module()

        if self._tfaw is not None:
            count = Signal(range(max(self._tfaw, 2)))
            window = Signal(self._tfaw)
            m.d.sync += window.eq(Cat(self.valid, window))
            m.d.comb += count.eq(reduce(add, [window[i] for i in range(self._tfaw)]))
            with m.If(count < 4):
                with m.If(count == 3):
                    m.d.sync += self.ready.eq(~self.valid)
                with m.Else():
                    m.d.sync += self.ready.eq(1)

        return m
