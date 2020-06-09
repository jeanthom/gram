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

        self._port = core.crossbar.get_port()

        dram_size = core.size//4
        dram_addr_width = log2_int(dram_size)
        granularity = 8

        self.bus = wishbone.Interface(addr_width=dram_addr_width,
            data_width=32, granularity=granularity)

        map = MemoryMap(addr_width=dram_addr_width, data_width=granularity)
        map.add_resource(self, size=dram_size)
        self.bus.memory_map = map

    def elaborate(self, platform):
        m = Module()

        ratio = wishbone_data_width//port_data_width
        count = Signal(max=max(ratio, 2))
        with m.FSM():
            with m.State("Send-Cmd"):
                m.d.comb += [
                    port.cmd.valid.eq(self.bus.cyc & self.bus.stb),
                    port.cmd.we.eq(self.bus.we),
                    port.cmd.addr.eq(self.bus.adr*ratio + count - adr_offset),
                ]
                with m.If(port.cmd.valid & port.cmd.ready):


        #   with m.State("Write"):
        #       ...

        #   with m.State("Read"):
        #       ...

        return m
