# This file is Copyright (c) 2020 LambdaConcept <contact@lambdaconcept.com>

from nmigen import *
from nmigen.lib.cdc import ResetSynchronizer
from nmigen_soc import wishbone, memory

from lambdasoc.cpu.minerva import MinervaCPU
from lambdasoc.periph.intc import GenericInterruptController
from lambdasoc.periph.serial import AsyncSerialPeripheral
from lambdasoc.periph.sram import SRAMPeripheral
from lambdasoc.periph.timer import TimerPeripheral
from lambdasoc.periph import Peripheral
from lambdasoc.soc.base import SoC

from gram.core import gramCore
from gram.phy.ecp5ddrphy import ECP5DDRPHY
from gram.modules import MT41K256M16
from gram.frontend.wishbone import gramWishbone

from customecpix5 import ECPIX5Platform
from uartbridge import UARTBridge
from crg import *

class DDR3SoC(SoC, Elaboratable):
    def __init__(self, *, clk_freq,
                 ddrphy_addr, dramcore_addr,
                 ddr_addr):
        self._arbiter = wishbone.Arbiter(addr_width=30, data_width=32, granularity=8,
                                         features={"cti", "bte"})
        self._decoder = wishbone.Decoder(addr_width=30, data_width=32, granularity=8,
                                         features={"cti", "bte"})

        self.crg = ECPIX5CRG()

        self.ub = UARTBridge(divisor=868, pins=platform.request("uart", 0))
        self._arbiter.add(self.ub.bus)

        self.ddrphy = ECP5DDRPHY(platform.request("ddr3", 0))
        self._decoder.add(self.ddrphy.bus, addr=ddrphy_addr)

        ddrmodule = MT41K256M16(platform.default_clk_frequency, "1:2")

        self.dramcore = gramCore(
            phy=self.ddrphy,
            geom_settings=ddrmodule.geom_settings,
            timing_settings=ddrmodule.timing_settings,
            clk_freq=clk_freq)
        self._decoder.add(self.dramcore.bus, addr=dramcore_addr)

        self.drambone = gramWishbone(self.dramcore)
        self._decoder.add(self.drambone.bus, addr=ddr_addr)

        self.memory_map = self._decoder.bus.memory_map

        self.clk_freq = clk_freq

    def elaborate(self, platform):
        m = Module()

        m.submodules.sysclk = self.crg

        m.submodules.arbiter = self._arbiter
        m.submodules.ub = self.ub

        m.submodules.decoder = self._decoder
        m.submodules.ddrphy = self.ddrphy
        m.submodules.dramcore = self.dramcore
        m.submodules.drambone = self.drambone

        m.d.comb += [
            self._arbiter.bus.connect(self._decoder.bus),
        ]

        return m


if __name__ == "__main__":
    platform = ECPIX5Platform()

    soc = DDR3SoC(clk_freq=int(platform.default_clk_frequency),
        ddrphy_addr=0x00008000, dramcore_addr=0x00009000,
        ddr_addr=0x10000000)

    soc.build(do_build=True)
    platform.build(soc, do_program=True)
