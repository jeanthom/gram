# This file is Copyright (c) 2020 LambdaConcept <contact@lambdaconcept.com>
# This file is Copyright (c) 2022 Raptor Engineering, LLC <support@raptorengineering.com>

from nmigen import *
from nmigen.lib.cdc import ResetSynchronizer
from nmigen_soc import wishbone, memory

from lambdasoc.periph.intc import GenericInterruptController
from lambdasoc.periph.serial import AsyncSerialPeripheral
from lambdasoc.periph.sram import SRAMPeripheral
from lambdasoc.periph.timer import TimerPeripheral
from lambdasoc.periph import Peripheral
from lambdasoc.soc.base import SoC

from gram.core import gramCore
from gram.phy.ecp5ddrphy import ECP5DDRPHY
from gram.modules import MT41K64M16
from gram.frontend.wishbone import gramWishbone

from nmigen_boards.versa_ecp5 import VersaECP5Platform85
from ecp5_crg import ECP5CRG
#from crg import ECPIX5CRG
from uartbridge import UARTBridge
from crg import *

class DDR3SoC(SoC, Elaboratable):
    def __init__(self, *,
                 ddrphy_addr, dramcore_addr,
                 ddr_addr):
        self._decoder = wishbone.Decoder(addr_width=30, data_width=32, granularity=8,
                                         features={"cti", "bte"})

        #desired_sys_clk_freq = 100e6
        #desired_sys_clk_freq = 90e6
        #desired_sys_clk_freq = 75e6
        #desired_sys_clk_freq = 70e6
        #desired_sys_clk_freq = 65e6
        #desired_sys_clk_freq = 60e6
        #desired_sys_clk_freq = 55e6
        desired_sys_clk_freq = 50e6

        #self.crg = ECPIX5CRG()
        self.crg = ECP5CRG(sys_clk_freq=desired_sys_clk_freq)

        self.ub = UARTBridge(divisor=int(desired_sys_clk_freq/115200), pins=platform.request("uart", 0))

        ddr_pins = platform.request("ddr3", 0, dir={"dq":"-", "dqs":"-"},
            xdr={"clk":4, "a":4, "ba":4, "clk_en":4, "odt":4, "ras":4, "cas":4, "we":4, "cs":4, "rst":1})
        self.ddrphy = DomainRenamer("dramsync")(ECP5DDRPHY(ddr_pins))
        self._decoder.add(self.ddrphy.bus, addr=ddrphy_addr)

        ddrmodule = MT41K64M16(self.crg.sys_clk_freq, "1:2")

        self.dramcore = DomainRenamer("dramsync")(gramCore(
            phy=self.ddrphy,
            geom_settings=ddrmodule.geom_settings,
            timing_settings=ddrmodule.timing_settings,
            clk_freq=self.crg.sys_clk_freq))
        self._decoder.add(self.dramcore.bus, addr=dramcore_addr)

        self.drambone = DomainRenamer("dramsync")(gramWishbone(self.dramcore))
        self._decoder.add(self.drambone.bus, addr=ddr_addr)

        self.memory_map = self._decoder.bus.memory_map

        self.clk_freq = self.crg.sys_clk_freq

    def elaborate(self, platform):
        m = Module()

        m.submodules.sysclk = self.crg

        m.submodules.ub = self.ub

        m.submodules.decoder = self._decoder
        m.submodules.ddrphy = self.ddrphy
        m.submodules.dramcore = self.dramcore
        m.submodules.drambone = self.drambone

        m.d.comb += [
            self.ub.bus.connect(self._decoder.bus),
        ]

        return m


if __name__ == "__main__":
    platform = VersaECP5Platform85()

    soc = DDR3SoC(ddrphy_addr=0x00008000, dramcore_addr=0x00009000,
        ddr_addr=0x10000000)

    soc.build(do_build=True)
    platform.build(soc, do_program=True)
