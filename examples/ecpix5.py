from nmigen import *
from nmigen_soc import wishbone, memory

from lambdasoc.cpu.minerva import MinervaCPU
from lambdasoc.periph.intc import GenericInterruptController
from lambdasoc.periph.serial import AsyncSerialPeripheral
from lambdasoc.periph.sram import SRAMPeripheral
from lambdasoc.periph.timer import TimerPeripheral
from lambdasoc.periph import Peripheral
from lambdasoc.soc.cpu import CPUSoC

from gram.core import gramCore
from gram.phy.ecp5ddrphy import ECP5DDRPHY
from gram.modules import MT41K256M16

from customecpix5 import ECPIX5Platform

class PLL(Elaboratable):
    def __init__(self, clkin, clksel=Signal(shape=2, reset=2), clkout1=Signal(), clkout2=Signal(), clkout3=Signal(), clkout4=Signal(), lock=Signal(), CLKI_DIV=1, CLKFB_DIV=1, CLK1_DIV=3, CLK2_DIV=4, CLK3_DIV=5, CLK4_DIV=6):
        self.clkin = clkin
        self.clkout1 = clkout1
        self.clkout2 = clkout2
        self.clkout3 = clkout3
        self.clkout4 = clkout4
        self.clksel = clksel
        self.lock = lock
        self.CLKI_DIV = CLKI_DIV
        self.CLKFB_DIV = CLKFB_DIV
        self.CLKOP_DIV = CLK1_DIV
        self.CLKOS_DIV = CLK2_DIV
        self.CLKOS2_DIV = CLK3_DIV
        self.CLKOS3_DIV = CLK4_DIV
        self.ports = [
            self.clkin,
            self.clkout1,
            self.clkout2,
            self.clkout3,
            self.clkout4,
            self.clksel,
            self.lock,
        ]

    def elaborate(self, platform):
        clkfb = Signal()
        pll = Instance("EHXPLLL",
            p_PLLRST_ENA='DISABLED',
            p_INTFB_WAKE='DISABLED',
            p_STDBY_ENABLE='DISABLED',
            p_CLKOP_FPHASE=0,
            p_CLKOP_CPHASE=11,
            p_OUTDIVIDER_MUXA='DIVA',
            p_CLKOP_ENABLE='ENABLED',
            p_CLKOP_DIV=self.CLKOP_DIV, #Max 948 MHz at OP=79 FB=1 I=1 F_in=12 MHz, Min 30 MHz (28 MHz locks sometimes, lock LED blinks) Hmm... /3*82/25
            p_CLKOS_DIV=self.CLKOS_DIV,
            p_CLKOS2_DIV=self.CLKOS2_DIV,
            p_CLKOS3_DIV=self.CLKOS3_DIV,
            p_CLKFB_DIV=self.CLKFB_DIV, #25
            p_CLKI_DIV=self.CLKI_DIV, #6
            p_FEEDBK_PATH='USERCLOCK',
            i_CLKI=self.clkin,
            i_CLKFB=clkfb,
            i_RST=0,
            i_STDBY=0,
            i_PHASESEL0=0,
            i_PHASESEL1=0,
            i_PHASEDIR=0,
            i_PHASESTEP=0,
            i_PLLWAKESYNC=0,
            i_ENCLKOP=0,
            i_ENCLKOS=0,
            i_ENCLKOS2=0,
            i_ENCLKOS3=0,
            o_CLKOP=self.clkout1,
            o_CLKOS=self.clkout2,
            o_CLKOS2=self.clkout3,
            o_CLKOS3=self.clkout4,
            o_LOCK=self.lock,
            #o_LOCK=pll_lock
            )
        m = Module()
        m.submodules += pll
        with m.If(self.clksel == 0):
            m.d.comb += clkfb.eq(self.clkout1)
        with m.Elif(self.clksel == 1):
            m.d.comb += clkfb.eq(self.clkout2)
        with m.Elif(self.clksel == 2):
            m.d.comb += clkfb.eq(self.clkout3)
        with m.Else():
            m.d.comb += clkfb.eq(self.clkout4)
        return m

class SysClocker(Elaboratable):
	def elaborate(self, platform):
		m = Module()

		m.submodules.pll = pll = PLL(ClockSignal("sync"), CLKI_DIV=1, CLKFB_DIV=2, CLK1_DIV=2, CLK2_DIV=16)
		cd_sys2x = ClockDomain("sys2x", local=False)
		m.d.comb += cd_sys2x.clk.eq(pll.clkout1)
		m.domains += cd_sys2x

		cd_init = ClockDomain("init", local=False)
		m.d.comb += cd_init.clk.eq(pll.clkout2)
		m.domains += cd_init

		return m

class DDR3SoC(CPUSoC, Elaboratable):
	def __init__(self, *, reset_addr, clk_freq,
				 rom_addr, rom_size,
				 ram_addr, ram_size,
				 uart_addr, uart_divisor, uart_pins,
				 timer_addr, timer_width,
				 ddrphy_addr, dramcore_addr):
		self._arbiter = wishbone.Arbiter(addr_width=30, data_width=32, granularity=8,
										 features={"cti", "bte"})
		self._decoder = wishbone.Decoder(addr_width=30, data_width=32, granularity=8,
										 features={"cti", "bte"})

		self.cpu = MinervaCPU(reset_address=reset_addr)
		self._arbiter.add(self.cpu.ibus)
		self._arbiter.add(self.cpu.dbus)

		self.rom = SRAMPeripheral(size=rom_size, writable=False)
		self._decoder.add(self.rom.bus, addr=rom_addr)

		self.ram = SRAMPeripheral(size=ram_size)
		self._decoder.add(self.ram.bus, addr=ram_addr)

		self.uart = AsyncSerialPeripheral(divisor=uart_divisor, pins=uart_pins)
		self._decoder.add(self.uart.bus, addr=uart_addr)

		self.timer = TimerPeripheral(width=timer_width)
		self._decoder.add(self.timer.bus, addr=timer_addr)

		self.intc = GenericInterruptController(width=len(self.cpu.ip))
		self.intc.add_irq(self.timer.irq, 0)
		self.intc.add_irq(self.uart .irq, 1)

		self.ddrphy = ECP5DDRPHY(platform.request("ddr3", 0))
		self._decoder.add(self.ddrphy.bus, addr=ddrphy_addr)

		ddrmodule = MT41K256M16(clk_freq, "1:4")

		self.dramcore = gramCore(
			phy = self.ddrphy,
            geom_settings   = ddrmodule.geom_settings,
            timing_settings = ddrmodule.timing_settings,
            clk_freq = clk_freq)
		#self._decoder.add(self.dramcore.bus, addr=dramcore_addr)

		self.memory_map = self._decoder.bus.memory_map

		self.clk_freq = clk_freq

	def elaborate(self, platform):
		m = Module()

		m.submodules.arbiter = self._arbiter
		m.submodules.cpu     = self.cpu

		m.submodules.decoder = self._decoder
		m.submodules.rom     = self.rom
		m.submodules.ram     = self.ram
		m.submodules.uart    = self.uart
		m.submodules.timer   = self.timer
		m.submodules.intc    = self.intc
		m.submodules.ddrphy  = self.ddrphy
		m.submodules.dramcore = self.dramcore

		m.submodules.sysclk = SysClocker()

		m.d.comb += [
			self._arbiter.bus.connect(self._decoder.bus),
			self.cpu.ip.eq(self.intc.ip),
		]

		return m


if __name__ == "__main__":
	platform = ECPIX5Platform()

	uart_divisor = int(platform.default_clk_frequency // 115200)
	uart_pins = platform.request("uart", 0)

	soc = DDR3SoC(
		 reset_addr=0x00000000, clk_freq=int(platform.default_clk_frequency),
		   rom_addr=0x00000000, rom_size=0x4000,
		   ram_addr=0x00004000, ram_size=0x1000,
		  uart_addr=0x00005000, uart_divisor=uart_divisor, uart_pins=uart_pins,
		 timer_addr=0x00006000, timer_width=32,
		ddrphy_addr=0x00007000, dramcore_addr=0x00008000
	)

	soc.build(do_build=True, do_init=True)
	platform.build(soc, do_program=True)
