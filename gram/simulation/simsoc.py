# This file is Copyright (c) 2020 LambdaConcept <contact@lambdaconcept.com>

from nmigen import *
from nmigen_soc import wishbone, memory

from lambdasoc.periph import Peripheral
from lambdasoc.soc.base import SoC

from gram.core import gramCore
from gram.phy.ecp5ddrphy import ECP5DDRPHY
from gram.modules import MT41K256M16
from gram.frontend.wishbone import gramWishbone

from icarusecpix5platform import IcarusECPIX5Platform
from uartbridge import UARTBridge
from crg import *

class DDR3SoC(SoC, Elaboratable):
    def __init__(self, *, clk_freq,
                 ddrphy_addr, dramcore_addr,
                 ddr_addr):
        self.crg = ECPIX5CRG()

        self._arbiter = wishbone.Arbiter(addr_width=30, data_width=32, granularity=8,
                                         features={"cti", "bte"})
        self._decoder = wishbone.Decoder(addr_width=30, data_width=32, granularity=8,
                                         features={"cti", "bte"})

        self.ub = UARTBridge(divisor=5, pins=platform.request("uart", 0))
        self._arbiter.add(self.ub.bus)

        ddr_pins = platform.request("ddr3", 0, dir={"dq":"-", "dqs":"-"},
            xdr={"clk":4, "a":4})
        self.ddrphy = DomainRenamer("dramsync")(ECP5DDRPHY(ddr_pins))
        self._decoder.add(self.ddrphy.bus, addr=ddrphy_addr)

        ddrmodule = MT41K256M16(clk_freq, "1:2")

        self.dramcore = DomainRenamer("dramsync")(gramCore(
            phy=self.ddrphy,
            geom_settings=ddrmodule.geom_settings,
            timing_settings=ddrmodule.timing_settings,
            clk_freq=clk_freq))
        self._decoder.add(self.dramcore.bus, addr=dramcore_addr)

        self.drambone = DomainRenamer("dramsync")(gramWishbone(self.dramcore))
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
    platform = IcarusECPIX5Platform()

    soc = DDR3SoC(clk_freq=int(platform.default_clk_frequency),
        ddrphy_addr=0x00008000, dramcore_addr=0x00009000,
        ddr_addr=0x10000000)

    soc.build(do_build=True)
    platform.build(soc, build_dir="build_simsoc")
