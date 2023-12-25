# This file is Copyright (c) 2020 LambdaConcept <contact@lambdaconcept.com>
# License: BSD
# Copyright (c) 2020 LambdaConcept <contact@lambdaconcept.com>
# Copyright (c) 2021 Luke Kenneth Casson Leighton <lkcl@lkcl.net>
#
# Code from LambaConcept is Licensed BSD
# Code from Luke Kenneth Casson Leighton is Licensed LGPLv3+
#
# Modifications for the Libre-SOC Project funded by NLnet and NGI POINTER
# under EU Grants 871528 and 957073

from math import log2

from nmigen import (Module, Elaboratable, Signal, Repl)
from nmigen.utils import log2_int

from nmigen_soc import wishbone
from nmigen_soc.memory import MemoryMap
from lambdasoc.periph import Peripheral

# XXX
# WARNING - THIS CODE CANNOT COPE WITH WISHBONE 4.0 PIPELINE MODE
# THE ADDRESS MAY CHANGE AFTER EACH STB AND THIS IS AN ASSUMPTION
# FROM WISHBONE 3.0 CLASSIC.  USE THE COMPATIBILITY MODE stall=cyc&~ack
# OR USE BURST-MODE ONLY
# XXX
class gramWishbone(Peripheral, Elaboratable):
    def __init__(self, core, data_width=32, granularity=8,
                             features=frozenset()):

        super().__init__(name="wishbone")

        self.native_port = core.crossbar.get_native_port()

        self.ratio = self.native_port.data_width//data_width
        addr_width = log2_int(core.size//self.ratio)
        addr_width_r = addr_width + log2_int(self.ratio)
        self.dsize = log2_int(data_width//granularity)
        self.bus = wishbone.Interface(addr_width=addr_width_r,
                                      data_width=data_width,
                                      granularity=granularity,
                                      features=features)

        mmap = MemoryMap(addr_width=addr_width_r+self.dsize,
                        data_width=granularity)

        self.bus.memory_map = mmap

    def elaborate(self, platform):
        m = Module()
        comb = m.d.comb
        cmd = self.native_port.cmd
        wdata = self.native_port.wdata
        rdata = self.native_port.rdata
        bus = self.bus

        # Write datapath
        comb += wdata.valid.eq(bus.cyc & bus.stb & bus.we)

        ratio_bitmask = Repl(1, log2_int(self.ratio))

        # XXX? sel is zero being compensated-for as all 1s does not seem right
        sel = Signal.like(bus.sel)
        with m.If(bus.sel == 0):
            comb += sel.eq(-1) # all 1s
        with m.Else():
            comb += sel.eq(bus.sel)

        with m.Switch(bus.adr & ratio_bitmask): # XXX adr changes (WB4-pipe)
            for i in range(self.ratio):
                with m.Case(i):
                    # write-enable
                    we = Repl(sel, bus.granularity//8) << (self.ratio*i)
                    comb += wdata.we.eq(we)
                    # write-data
                    data = bus.dat_w << (bus.data_width*i)
                    comb += wdata.data.eq(data)

        # Read datapath
        comb += rdata.ready.eq(1)

        with m.Switch(bus.adr & ratio_bitmask): # XXX adr changes (WB4-pipe)
            for i in range(self.ratio):
                with m.Case(i):
                    data = rdata.data >> (bus.data_width*i)
                    comb += bus.dat_r.eq(data)

        # Command FSM
        with m.FSM():
            # raise a command when WB has a request
            with m.State("Send-Cmd"):
                # XXX this logic is only WB 3.0 classic compatible!
                comb += [
                    cmd.valid.eq(bus.cyc & bus.stb),
                    cmd.we.eq(bus.we),
                    cmd.addr.eq(bus.adr >> self.dsize),
                ]

                # when cmd is accepted, move to either read or write FSM
                with m.If(cmd.valid & cmd.ready):
                    with m.If(bus.we):
                        m.next = "Wait-Write"
                    with m.Else():
                        m.next = "Wait-Read"

            # read-wait: when read valid, ack the WB bus, return idle
            with m.State("Wait-Read"):
                with m.If(rdata.valid):
                    comb += bus.ack.eq(1)
                    m.next = "Send-Cmd"

            # write-wait: when write valid, ack the WB bus, return idle
            with m.State("Wait-Write"):
                with m.If(wdata.ready):
                    comb += bus.ack.eq(1)
                    m.next = "Send-Cmd"

        return m
