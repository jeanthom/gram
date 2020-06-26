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

from icarusecpix5platform import IcarusECPIX5Platform
from uartbridge import UARTBridge

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
                       p_CLKOP_CPHASE=1,
                       p_OUTDIVIDER_MUXA='DIVA',
                       p_CLKOP_ENABLE='ENABLED',
                       p_CLKOP_DIV=self.CLKOP_DIV,
                       p_CLKOS_DIV=self.CLKOS_DIV,
                       p_CLKOS2_DIV=self.CLKOS2_DIV,
                       p_CLKOS3_DIV=self.CLKOS3_DIV,
                       p_CLKFB_DIV=self.CLKFB_DIV,
                       p_CLKI_DIV=self.CLKI_DIV,
                       p_FEEDBK_PATH='CLKOP',
                       #p_FREQUENCY_PIN_CLKOP='200',
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


class ECPIX5CRG(Elaboratable):
    def __init__(self):
        ...

    def elaborate(self, platform):
        m = Module()

        # Get 100Mhz from oscillator
        clk100 = platform.request("clk100")
        cd_rawclk = ClockDomain("rawclk", local=True, reset_less=True)
        m.d.comb += cd_rawclk.clk.eq(clk100)
        m.domains += cd_rawclk

        # Reset
        reset = platform.request(platform.default_rst).i
        gsr0 = Signal()
        gsr1 = Signal()

        m.submodules += [
            Instance("FD1S3AX", p_GSR="DISABLED", i_CK=ClockSignal("rawclk"), i_D=~reset, o_Q=gsr0),
            Instance("FD1S3AX", p_GSR="DISABLED", i_CK=ClockSignal("rawclk"), i_D=gsr0,   o_Q=gsr1),
            Instance("SGSR", i_CLK=ClockSignal("rawclk"), i_GSR=gsr1),
        ]

        # Power-on delay (655us)
        podcnt = Signal(16, reset=2**16-1)
        pod_done = Signal()
        with m.If(podcnt != 0):
            m.d.rawclk += podcnt.eq(podcnt-1)
        m.d.comb += pod_done.eq(podcnt == 0)

        # Generating sync2x (200Mhz) and init (25Mhz) from clk100
        cd_sync2x = ClockDomain("sync2x", local=False)
        cd_sync2x_unbuf = ClockDomain("sync2x_unbuf", local=True, reset_less=True)
        cd_init = ClockDomain("init", local=False)
        cd_sync = ClockDomain("sync", local=False, reset_less=True)
        cd_dramsync = ClockDomain("dramsync", local=False)
        m.submodules.pll = pll = PLL(ClockSignal("rawclk"), CLKI_DIV=1, CLKFB_DIV=2, CLK1_DIV=2, CLK2_DIV=16, CLK3_DIV=4,
            clkout1=ClockSignal("sync2x_unbuf"), clkout2=ClockSignal("init"))
        m.submodules += Instance("ECLKSYNCB",
                i_ECLKI = ClockSignal("sync2x_unbuf"),
                i_STOP  = 0,
                o_ECLKO = ClockSignal("sync2x"))
        m.domains += cd_sync2x_unbuf
        m.domains += cd_sync2x
        m.domains += cd_init
        m.domains += cd_sync
        m.domains += cd_dramsync
        m.d.comb += ResetSignal("init").eq(~pll.lock|~pod_done)
        m.d.comb += ResetSignal("dramsync").eq(~pll.lock|~pod_done)

        rgb_led = platform.request("rgb_led", 2)
        cnt = Signal(25)
        m.d.sync += cnt.eq(cnt+1)
        m.d.comb += rgb_led.r.eq(cnt[24])
        m.d.comb += rgb_led.g.eq(~pod_done)
        m.d.comb += rgb_led.b.eq(~pll.lock)

        # Generating sync (100Mhz) from sync2x
        
        m.submodules += Instance("CLKDIVF",
            p_DIV="2.0",
            i_ALIGNWD=0,
            i_CLKI=ClockSignal("sync2x"),
            i_RST=0,
            o_CDIVX=ClockSignal("sync"))
        m.d.comb += ClockSignal("dramsync").eq(ClockSignal("sync"))

        return m

class OldCRG(Elaboratable):
    def elaborate(self, platform):
        m = Module()

        m.submodules.pll = pll = PLL(ClockSignal(
            "sync"), CLKI_DIV=1, CLKFB_DIV=2, CLK1_DIV=2, CLK2_DIV=16)
        cd_sync2x = ClockDomain("sync2x", local=False)
        m.d.comb += cd_sync2x.clk.eq(pll.clkout1)
        m.domains += cd_sync2x

        cd_init = ClockDomain("init", local=False)
        m.d.comb += cd_init.clk.eq(pll.clkout2)
        m.domains += cd_init

        return m

class ThinCRG(Elaboratable):
    """
    Sync (clk100, resetless) => PLL => sync2x_unbuf (200Mhz) => ECLKSYNC => sync2x => CLKDIVF => dramsync
    """

    def __init__(self):
        ...

    def elaborate(self, platform):
        m = Module()

        # Power-on delay (655us)
        podcnt = Signal(16, reset=2**16-1)
        pod_done = Signal()
        with m.If(podcnt != 0):
            m.d.sync += podcnt.eq(podcnt-1)
        m.d.comb += pod_done.eq(podcnt == 0)

        # Generating sync2x (200Mhz) and init (25Mhz) from clk100
        cd_sync2x = ClockDomain("sync2x", local=False)
        cd_sync2x_unbuf = ClockDomain("sync2x_unbuf", local=True, reset_less=True)
        cd_init = ClockDomain("init", local=False)
        cd_dramsync = ClockDomain("dramsync", local=False)
        m.submodules.pll = pll = PLL(ClockSignal("sync"), CLKI_DIV=1, CLKFB_DIV=2, CLK1_DIV=2, CLK2_DIV=16, CLK3_DIV=4,
            clkout1=ClockSignal("sync2x_unbuf"), clkout2=ClockSignal("init"))
        m.submodules += Instance("ECLKSYNCB",
                i_ECLKI = ClockSignal("sync2x_unbuf"),
                i_STOP  = 0,
                o_ECLKO = ClockSignal("sync2x"))
        m.domains += cd_sync2x_unbuf
        m.domains += cd_sync2x
        m.domains += cd_init
        m.domains += cd_dramsync
        m.d.comb += ResetSignal("init").eq(~pll.lock|~pod_done)
        m.d.comb += ResetSignal("dramsync").eq(~pll.lock|~pod_done)

        # Generating sync (100Mhz) from sync2x
        m.submodules += Instance("CLKDIVF",
            p_DIV="2.0",
            i_ALIGNWD=0,
            i_CLKI=ClockSignal("sync2x"),
            i_RST=0,
            o_CDIVX=ClockSignal("dramsync"))

        return m


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

        self.ddrphy = ECP5DDRPHY(platform.request("ddr3", 0, dir={"dq":"-", "dqs":"-"}))
        self._decoder.add(self.ddrphy.bus, addr=ddrphy_addr)

        ddrmodule = MT41K256M16(clk_freq, "1:4")

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
    platform = IcarusECPIX5Platform()

    soc = DDR3SoC(clk_freq=int(platform.default_clk_frequency),
        ddrphy_addr=0x00008000, dramcore_addr=0x00009000,
        ddr_addr=0x10000000)

    soc.build(do_build=True)
    platform.build(soc)
