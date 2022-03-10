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
# XXX
class gramWishbone(Peripheral, Elaboratable):
    def __init__(self, core, data_width=32, granularity=8,
                             features=frozenset()):

        super().__init__(name="wishbone")

        self.native_port = core.crossbar.get_native_port()

        self.ratio = self.native_port.data_width//data_width

        addr_width = log2_int(core.size//(self.native_port.data_width//data_width))
        self.bus = wishbone.Interface(addr_width=addr_width+log2_int(self.ratio),
                                      data_width=data_width, granularity=granularity)

        map = MemoryMap(addr_width=addr_width+log2_int(self.ratio)+log2_int(data_width//granularity),
            data_width=granularity)
        self.bus.memory_map = map

    def elaborate(self, platform):
        m = Module()
        cmd = self.native_port.cmd
        wdata = self.native_port.wdata
        rdata = self.native_port.rdata

        # Write datapath
        m.d.comb += wdata.valid.eq(self.bus.cyc & self.bus.stb & self.bus.we)

        ratio_bitmask = Repl(1, log2_int(self.ratio))

        sel = Signal.like(self.bus.sel)
        with m.If(self.bus.sel == 0):
            m.d.comb += sel.eq(Repl(1, sel.width))
        with m.Else():
            m.d.comb += sel.eq(self.bus.sel)

        with m.Switch(self.bus.adr & ratio_bitmask):
            for i in range(self.ratio):
                with m.Case(i):
                    m.d.comb += wdata.we.eq(Repl(sel, self.bus.granularity//8) << (self.ratio*i))

        with m.Switch(self.bus.adr & ratio_bitmask):
            for i in range(self.ratio):
                with m.Case(i):
                    m.d.comb += wdata.data.eq(self.bus.dat_w << (self.bus.data_width*i))

        # Read datapath
        m.d.comb += rdata.ready.eq(1)

        with m.Switch(self.bus.adr & ratio_bitmask):
            for i in range(self.ratio):
                with m.Case(i):
                    m.d.comb += self.bus.dat_r.eq(rdata.data >> (self.bus.data_width*i))

        with m.FSM():
            with m.State("Send-Cmd"):
                m.d.comb += [
                    cmd.valid.eq(self.bus.cyc & self.bus.stb),
                    cmd.we.eq(self.bus.we),
                    cmd.addr.eq(self.bus.adr >> log2_int(self.bus.data_width//self.bus.granularity)),
                ]

                with m.If(cmd.valid & cmd.ready):
                    with m.If(self.bus.we):
                        m.next = "Wait-Write"
                    with m.Else():
                        m.next = "Wait-Read"

            with m.State("Wait-Read"):
                with m.If(rdata.valid):
                    m.d.comb += self.bus.ack.eq(1)
                    m.next = "Send-Cmd"

            with m.State("Wait-Write"):
                with m.If(wdata.ready):
                    m.d.comb += self.bus.ack.eq(1)
                    m.next = "Send-Cmd"

        return m
