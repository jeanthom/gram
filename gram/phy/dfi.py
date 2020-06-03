# This file is Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
#              Copyright (c) 2020 LambdaConcept <contact@lambdaconcept.com>

from nmigen import *
from nmigen.hdl.rec import *

def phase_cmd_description(addressbits, bankbits, nranks):
    return [
        ("address", addressbits, DIR_FANOUT),
        ("bank",       bankbits, DIR_FANOUT),
        ("cas_n",             1, DIR_FANOUT),
        ("cs_n",         nranks, DIR_FANOUT),
        ("ras_n",             1, DIR_FANOUT),
        ("we_n",              1, DIR_FANOUT),
        ("cke",          nranks, DIR_FANOUT),
        ("odt",          nranks, DIR_FANOUT),
        ("reset_n",           1, DIR_FANOUT),
        ("act_n",             1, DIR_FANOUT)
    ]


def phase_wrdata_description(databits):
    return [
        ("wrdata",         databits, DIR_FANOUT),
        ("wrdata_en",             1, DIR_FANOUT),
        ("wrdata_mask", databits//8, DIR_FANOUT)
    ]


def phase_rddata_description(databits):
    return [
        ("rddata_en",           1, DIR_FANOUT),
        ("rddata",       databits, DIR_FANIN),
        ("rddata_valid",        1, DIR_FANIN)
    ]


def phase_description(addressbits, bankbits, nranks, databits):
    r = phase_cmd_description(addressbits, bankbits, nranks)
    r += phase_wrdata_description(databits)
    r += phase_rddata_description(databits)
    return r


class Interface(Record):
    def __init__(self, addressbits, bankbits, nranks, databits, nphases=1):
        layout = [("p"+str(i), phase_description(addressbits, bankbits, nranks, databits)) for i in range(nphases)]
        Record.__init__(self, layout)
        self.phases = [getattr(self, "p"+str(i)) for i in range(nphases)]
        for p in self.phases:
            p.cas_n.reset = 1
            p.cs_n.reset = (2**nranks-1)
            p.ras_n.reset = 1
            p.we_n.reset = 1
            p.act_n.reset = 1

    # Returns pairs (DFI-mandated signal name, Migen signal object)
    def get_standard_names(self, m2s=True, s2m=True):
        r = []
        add_suffix = len(self.phases) > 1
        for n, phase in enumerate(self.phases):
            for field, size, direction in phase.layout:
                if (m2s and direction == DIR_FANOUT) or (s2m and direction == DIR_FANIN):
                    if add_suffix:
                        if direction == DIR_FANOUT:
                            suffix = "_p" + str(n)
                        else:
                            suffix = "_w" + str(n)
                    else:
                        suffix = ""
                    r.append(("dfi_" + field + suffix, getattr(phase, field)))
        return r


class Interconnect(Elaboratable):
    def __init__(self, master, slave):
        self._master = master
        self._slave = slave

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self._master.connect(self._slave)
        return m


class DDR4DFIMux(Elaboratable):
    def __init__(self, dfi_i, dfi_o):
        self.dfi_i = dfi_i
        self.dfi_o = dfi_o

    def elaborate(self, platform):
        m = Module()

        dfi_i = self.dfi_i
        dfi_o = self.dfi_o

        for i in range(len(dfi_i.phases)):
            p_i = dfi_i.phases[i]
            p_o = dfi_o.phases[i]
            m.d.comb += p_i.connect(p_o)
            with m.If(~p_i.ras_n & p_i.cas_n & p_i.we_n):
                m.d.comb += [
                    p_o.act_n.eq(0),
                    p_o.we_n.eq(p_i.address[14]),
                    p_o.cas_n.eq(p_i.address[15]),
                    p_o.ras_n.eq(p_i.address[16]),
                ]
            with m.Else():
                m.d.comb += p_o.act_n.eq(1)

        return m
