# This file is Copyright (c) 2020 LambdaConcept <contact@lambdaconcept.com>
# License: BSD

from math import log2

from nmigen import *
from nmigen.utils import log2_int

from nmigen_soc import wishbone
from nmigen_soc.memory import MemoryMap
from lambdasoc.periph import Peripheral


class gramWishbone(Peripheral, Elaboratable):
    def __init__(self, core, data_width=32, granularity=8):
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

        # Write datapath
        m.d.comb += [
            self.native_port.wdata.valid.eq(self.bus.cyc & self.bus.stb & self.bus.we),
        ]

        ratio_bitmask = Repl(1, log2_int(self.ratio))

        with m.Switch(self.bus.adr & ratio_bitmask):
            for i in range(self.ratio):
                with m.Case(i):
                    m.d.comb += self.native_port.wdata.we.eq(Repl(self.bus.sel, self.bus.granularity//8) << (self.ratio*i))

        with m.Switch(self.bus.adr & ratio_bitmask):
            for i in range(self.ratio):
                with m.Case(i):
                    m.d.comb += self.native_port.wdata.data.eq(self.bus.dat_w << (self.bus.data_width*i))

        # Read datapath
        m.d.comb += [
            self.native_port.rdata.ready.eq(1),
        ]

        with m.Switch(self.bus.adr & ratio_bitmask):
            for i in range(self.ratio):
                with m.Case(i):
                    m.d.comb += self.bus.dat_r.eq(self.native_port.rdata.data >> (self.bus.data_width*i))

        with m.FSM():
            with m.State("Send-Cmd"):
                m.d.comb += [
                    self.native_port.cmd.valid.eq(self.bus.cyc & self.bus.stb),
                    self.native_port.cmd.we.eq(self.bus.we),
                    self.native_port.cmd.addr.eq(self.bus.adr >> log2_int(self.bus.data_width//self.bus.granularity)),
                ]

                with m.If(self.native_port.cmd.valid & self.native_port.cmd.ready):
                    with m.If(self.bus.we):
                        m.next = "Wait-Write"
                    with m.Else():
                        m.next = "Wait-Read"

            with m.State("Wait-Read"):
                with m.If(self.native_port.rdata.valid):
                    m.d.comb += self.bus.ack.eq(1)
                    m.next = "Send-Cmd"

            with m.State("Wait-Write"):
                with m.If(self.native_port.wdata.ready):
                    m.d.comb += self.bus.ack.eq(1)
                    m.next = "Send-Cmd"

        return m
