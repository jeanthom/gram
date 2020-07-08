# This file is Copyright (c) 2020 LambdaConcept <contact@lambdaconcept.com>

from nmigen import *
from nmigen_soc import wishbone, memory
from nmigen.lib.cdc import ResetSynchronizer

from lambdasoc.periph import Peripheral
from lambdasoc.soc.base import SoC

from gram.common import *
from gram.core import gramCore
from gram.phy.fakephy import FakePHY, SDRAM_VERBOSE_STD, SDRAM_VERBOSE_DBG
from gram.modules import MT41K256M16
from gram.frontend.wishbone import gramWishbone

from gram.core.multiplexer import _AntiStarvation
from utils import *

class DDR3SoC(SoC, Elaboratable):
    def __init__(self, *, clk_freq, dramcore_addr,
                 ddr_addr):
        self._arbiter = wishbone.Arbiter(addr_width=30, data_width=32, granularity=8,
                                         features={"cti", "bte"})
        self._decoder = wishbone.Decoder(addr_width=30, data_width=32, granularity=8,
                                         features={"cti", "bte"})

        self.bus = wishbone.Interface(addr_width=30, data_width=32, granularity=32)
        self._arbiter.add(self.bus)

        tck = 2/(2*2*100e6)
        nphases = 2
        databits = 16
        nranks = 1
        addressbits = 14
        bankbits = 3
        cl, cwl = get_cl_cw("DDR3", tck)
        cl_sys_latency = get_sys_latency(nphases, cl)
        cwl_sys_latency = get_sys_latency(nphases, cwl)
        rdcmdphase, rdphase = get_sys_phases(nphases, cl_sys_latency, cl)
        wrcmdphase, wrphase = get_sys_phases(nphases, cwl_sys_latency, cwl)
        physettings = PhySettings(
            phytype="ECP5DDRPHY",
            memtype="DDR3",
            databits=databits,
            dfi_databits=4*databits,
            nranks=nranks,
            nphases=nphases,
            rdphase=rdphase,
            wrphase=wrphase,
            rdcmdphase=rdcmdphase,
            wrcmdphase=wrcmdphase,
            cl=cl,
            cwl=cwl,
            read_latency=2 + cl_sys_latency + 2 + log2_int(4//nphases) + 4,
            write_latency=cwl_sys_latency
        )

        ddrmodule = MT41K256M16(clk_freq, "1:4")
        self.ddrphy = FakePHY(module=ddrmodule,
            settings=physettings,
            verbosity=SDRAM_VERBOSE_DBG)

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

        m.submodules.arbiter = self._arbiter

        m.submodules.decoder = self._decoder
        m.submodules.ddrphy = self.ddrphy
        m.submodules.dramcore = self.dramcore
        m.submodules.drambone = self.drambone

        m.d.comb += [
            self._arbiter.bus.connect(self._decoder.bus),
        ]

        return m

class SocTestCase(FHDLTestCase):
    def test_soc(self):
        m = Module()
        soc = DDR3SoC(clk_freq=100e6,
            dramcore_addr=0x00000000,
            ddr_addr=0x10000000)
        m.submodules += soc

        def process():
            #res = yield from wb_read(soc.bus, 0x10000000 >> 2, 0xF, 16384)
            yield

        runSimulation(m, process, "test_soc.vcd")
