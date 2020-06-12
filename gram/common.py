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

# PHY Pads Transformers ----------------------------------------------------------------------------


class PHYPadsReducer:
    """PHY Pads Reducer

    Reduce DRAM pads to only use specific modules.

    For testing purposes, we often need to use only some of the DRAM modules. PHYPadsReducer allows
    selecting specific modules and avoid re-definining dram pins in the Platform for this.
    """

    def __init__(self, pads, modules):
        self.pads = pads
        self.modules = modules

    def __getattr__(self, name):
        if name in ["dq"]:
            return Array([getattr(self.pads, name)[8*i + j]
                          for i in self.modules
                          for j in range(8)])
        if name in ["dm", "dqs", "dqs_p", "dqs_n"]:
            return Array([getattr(self.pads, name)[i] for i in self.modules])
        else:
            return getattr(self.pads, name)


class PHYPadsCombiner:
    """PHY Pads Combiner

    Combine DRAM pads from fully dissociated chips in a unique DRAM pads structure.

    Most generally, DRAM chips are sharing command/address lines between chips (using a fly-by
    topology since DDR3). On some boards, the DRAM chips are using separate command/address lines
    and this combiner can be used to re-create a single pads structure (that will be compatible with
    LiteDRAM's PHYs) to create a single DRAM controller from multiple fully dissociated DRAMs chips.
    """

    def __init__(self, pads):
        if not isinstance(pads, list):
            self.groups = [pads]
        else:
            self.groups = pads
        self.sel = 0

    def sel_group(self, n):
        self.sel = n

    def __getattr__(self, name):
        if name in ["dm", "dq", "dqs", "dqs_p", "dqs_n"]:
            return Array([getattr(self.groups[j], name)[i]
                          for i in range(len(getattr(self.groups[0], name)))
                          for j in range(len(self.groups))])
        else:
            return getattr(self.groups[self.sel], name)

# BitSlip ------------------------------------------------------------------------------------------


class BitSlip(Elaboratable):
    def __init__(self, dw, rst=None, slp=None, cycles=1):
        self.i = Signal(dw)
        self.o = Signal(dw)
        self.rst = Signal() if rst is None else rst
        self.slp = Signal() if slp is None else slp
        self._cycles = cycles

    def elaborate(self, platform):
        m = Module()

        value = Signal(range(self._cycles*dw))
        with m.If(self.slp):
            m.d.sync += value.eq(value+1)
        with m.Elif(self.rst):
            m.d.sync += value.eq(0)

        r = Signal((self._cycles+1)*dw, reset_less=True)
        m.d.sync += r.eq(Cat(r[dw:], self.i))
        cases = {}
        for i in range(self._cycles*dw):
            cases[i] = self.o.eq(r[i:dw+i])
        m.d.comb += Case(value, cases)

        return m

# DQS Pattern --------------------------------------------------------------------------------------


class DQSPattern(Elaboratable):
    def __init__(self, preamble=None, postamble=None, wlevel_en=0, wlevel_strobe=0, register=False):
        self.preamble = Signal() if preamble is None else preamble
        self.postamble = Signal() if postamble is None else postamble
        self.o = Signal(8)
        self._wlevel_en = wlevel_en
        self._wlevel_strobe = wlevel_strobe
        self._register = register

    def elaborate(self, platform):
        m = Module()

        with m.If(self.preamble):
            m.d.comb += self.o.eq(0b00010101)
        with m.Elif(self.postamble):
            m.d.comb += self.o.eq(0b01010100)
        with m.Elif(self._wlevel_en):
            with m.If(self._wlevel_strobe):
                m.d.comb += self.o.eq(0b00000001)
            with m.Else():
                m.d.comb += self.o.eq(0b00000000)
        with m.Else():
            m.d.comb += self.o.eq(0b01010101)

        if self._register:
            o = Signal.like(self.o)
            m.d.sync += o.eq(self.o)
            self.o = o

        return m

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

    # Optional RDIMM configuration
    def set_rdimm(self, tck, rcd_pll_bypass, rcd_ca_cs_drive, rcd_odt_cke_drive, rcd_clk_drive):
        assert self.memtype == "DDR4"
        self.is_rdimm = True
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


class gramNativeWritePort(gramNativePort):
    def __init__(self, *args, **kwargs):
        gramNativePort.__init__(self, "write", *args, **kwargs)


class gramNativeReadPort(gramNativePort):
    def __init__(self, *args, **kwargs):
        gramNativePort.__init__(self, "read", *args, **kwargs)


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
            with m.Else():
                m.d.sync += count.eq(count-1)
                with m.If(count == 1):
                    m.d.sync += self.ready.eq(1)
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
            m.d.comb += count.eq(reduce(add, [window[i]
                                              for i in range(self._tfaw)]))
            with m.If(count < 4):
                with m.If(count == 3):
                    m.d.sync += self.ready.eq(~self.valid)
                with m.Else():
                    m.d.sync += self.ready.eq(1)

        return m
