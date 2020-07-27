# This file is Copyright (c) 2020 LambdaConcept <contact@lambdaconcept.com>
# License: BSD

from math import log2

from nmigen import *
from nmigen.utils import log2_int

from nmigen_soc import wishbone
from nmigen_soc.memory import MemoryMap
from lambdasoc.periph import Peripheral


class gramWishbone(Peripheral, Elaboratable):
    def __init__(self, core, data_width = 32):
        super().__init__(name="wishbone")

        self.dw = data_width
        self._port = core.crossbar.get_native_port()

        dram_size = core.size//4
        dram_addr_width = log2_int(dram_size)
        granularity = 8

        self.bus = wishbone.Interface(addr_width=dram_addr_width,
                                      data_width=self.dw, granularity=granularity)

        map = MemoryMap(addr_width=dram_addr_width +
                        log2_int(granularity)-1, data_width=granularity)
        self.bus.memory_map = map

    def elaborate(self, platform):
        m = Module()

        # Write datapath
        m.d.comb += [
            self._port.wdata.valid.eq(self.bus.cyc & self.bus.stb & self.bus.we),
        ]

        with m.Switch(self.bus.adr & 0b11):
            for i in range(4):
                with m.Case(i):
                    with m.If(self.bus.sel):
                        m.d.comb += self._port.wdata.we.eq(0xF << (4*i))
                    with m.Else():
                        m.d.comb += self._port.wdata.we.eq(0)

        with m.Switch(self.bus.adr & 0b11):
            for i in range(4):
                with m.Case(i):
                    m.d.comb += self._port.wdata.data.eq(self.bus.dat_w << (32*i))

        # Read datapath
        m.d.comb += [
            self._port.rdata.ready.eq(1),
        ]

        with m.Switch(self.bus.adr & 0b11):
            for i in range(4):
                with m.Case(i):
                    m.d.comb += self.bus.dat_r.eq(self._port.rdata.data >> (32*i))

        with m.FSM():
            with m.State("Send-Cmd"):
                m.d.comb += [
                    self._port.cmd.valid.eq(self.bus.cyc & self.bus.stb),
                    self._port.cmd.we.eq(self.bus.we),
                    self._port.cmd.addr.eq(self.bus.adr >> 2),
                ]

                with m.If(self._port.cmd.valid & self._port.cmd.ready):
                    with m.If(self.bus.we):
                        m.next = "Wait-Write"
                    with m.Else():
                        m.next = "Wait-Read"

            with m.State("Wait-Read"):
                with m.If(self._port.rdata.valid):
                    m.d.comb += self.bus.ack.eq(1)
                    m.next = "Send-Cmd"

            with m.State("Wait-Write"):
                with m.If(self._port.wdata.ready):
                    m.d.comb += self.bus.ack.eq(1)
                    m.next = "Send-Cmd"

        return m
