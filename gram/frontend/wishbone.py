# This file is Copyright (c) 2020 LambdaConcept <contact@lambdaconcept.com>
# License: BSD

from nmigen import *
from nmigen.utils import log2_int

from nmigen_soc import wishbone
from nmigen_soc.memory import MemoryMap
from lambdasoc.periph import Peripheral


class gramWishbone(Peripheral, Elaboratable):
    def __init__(self, core):
        super().__init__()

        self._port = core.crossbar.get_port(data_width=32)

        dram_size = core.size//4
        dram_addr_width = log2_int(dram_size)
        granularity = 8

        self.bus = wishbone.Interface(addr_width=dram_addr_width,
                                      data_width=32, granularity=granularity)

        map = MemoryMap(addr_width=dram_addr_width +
                        log2_int(granularity)-1, data_width=granularity)
        self.bus.memory_map = map

    def elaborate(self, platform):
        m = Module()

        # Write datapath
        m.d.comb += [
            self._port.wdata.valid.eq(
                self.bus.cyc & self.bus.stb & self.bus.we),
            self._port.wdata.data.eq(self.bus.dat_w),
            self._port.wdata.we.eq(self.bus.sel),
        ]

        # Read datapath
        m.d.comb += [
            self.bus.dat_r.eq(self._port.rdata),
            self._port.rdata.ready.eq(1),
        ]

        with m.FSM():
            with m.State("Send-Cmd"):
                m.d.comb += [
                    self._port.cmd.valid.eq(self.bus.cyc & self.bus.stb),
                    self._port.cmd.we.eq(self.bus.we),
                    self._port.cmd.addr.eq(self.bus.adr),
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
