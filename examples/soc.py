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

from ecpix5_85 import ECPIX585Platform
from uartbridge import UARTBridge
from crg import *

class DDR3SoC(SoC, Elaboratable):
    def __init__(self, *,
                 uart_pins, ddr_pins,
                 ddrphy_addr, dramcore_addr,
                 ddr_addr):
        self._arbiter = wishbone.Arbiter(addr_width=30, data_width=32, granularity=8,
                                         features={"cti", "bte"})
        self._decoder = wishbone.Decoder(addr_width=30, data_width=32, granularity=8,
                                         features={"cti", "bte"})

        self.crg = ECPIX5CRG()

        self.cpu = MinervaCPU(reset_address=0)
        self._arbiter.add(self.cpu.ibus)
        self._arbiter.add(self.cpu.dbus)
        self.intc = GenericInterruptController(width=len(self.cpu.ip))

        self.rom = SRAMPeripheral(size=4096, writable=False)
        with open("firmware/main.bin", "rb") as f:
            words = iter(lambda: f.read(self.cpu.data_width // 8), b'')
            bios  = [int.from_bytes(w, self.cpu.byteorder) for w in words]
        self.rom.init = bios
        self._decoder.add(self.rom.bus, addr=0)

        self.ram = SRAMPeripheral(size=4096)
        self._decoder.add(self.ram.bus, addr=0x1000)

        self.uart = AsyncSerialPeripheral(divisor=100000000//115200, pins=uart_pins)
        self._decoder.add(self.uart.bus, addr=0x2000)

        
        self.ddrphy = DomainRenamer("dramsync")(ECP5DDRPHY(ddr_pins))
        self._decoder.add(self.ddrphy.bus, addr=ddrphy_addr)

        ddrmodule = MT41K256M16(platform.default_clk_frequency, "1:2")

        self.dramcore = DomainRenamer("dramsync")(gramCore(
            phy=self.ddrphy,
            geom_settings=ddrmodule.geom_settings,
            timing_settings=ddrmodule.timing_settings,
            clk_freq=platform.default_clk_frequency))
        self._decoder.add(self.dramcore.bus, addr=dramcore_addr)

        self.drambone = DomainRenamer("dramsync")(gramWishbone(self.dramcore))
        self._decoder.add(self.drambone.bus, addr=ddr_addr)

        self.memory_map = self._decoder.bus.memory_map

        self.clk_freq = platform.default_clk_frequency

    def elaborate(self, platform):
        m = Module()

        m.submodules.sysclk = self.crg
        
        m.submodules.rom = self.rom
        m.submodules.ram = self.ram
        m.submodules.uart = self.uart
        m.submodules.intc = self.intc
        m.submodules.cpu = self.cpu
        m.submodules.arbiter = self._arbiter
        m.submodules.decoder = self._decoder
        m.submodules.ddrphy = self.ddrphy
        m.submodules.dramcore = self.dramcore
        m.submodules.drambone = self.drambone

        m.d.comb += [
            self._arbiter.bus.connect(self._decoder.bus),
            self.cpu.ip.eq(self.intc.ip),
        ]

        return m


if __name__ == "__main__":
    platform = ECPIX585Platform()

    ddr_pins = platform.request("ddr3", 0, dir={"dq":"-", "dqs":"-"},
        xdr={"clk":4, "a":4, "ba":4, "clk_en":4, "odt":4, "ras":4, "cas":4, "we":4})
    uart_pins = platform.request("uart", 0)

    soc = DDR3SoC(ddrphy_addr=0x00008000, dramcore_addr=0x00009000,
        ddr_addr=0x10000000, ddr_pins=ddr_pins, uart_pins=uart_pins)

    platform.build(soc, do_program=True)
