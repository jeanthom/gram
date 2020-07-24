# This file is Copyright (c) 2020 LambdaConcept <contact@lambdaconcept.com>

import random

from nmigen import *
from nmigen.asserts import Assert, Assume
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
        self._decoder = wishbone.Decoder(addr_width=30, data_width=32, granularity=8,
                                         features={"cti", "bte"})

        self.bus = wishbone.Interface(addr_width=30, data_width=32, granularity=32)

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

        ddrmodule = MT41K256M16(clk_freq, "1:2")
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

        m.submodules.decoder = self._decoder
        m.submodules.ddrphy = self.ddrphy
        m.submodules.dramcore = self.dramcore
        m.submodules.drambone = self.drambone

        m.d.comb += [
            self.bus.connect(self._decoder.bus),
        ]

        return m

class SocTestCase(FHDLTestCase):
    def init_seq(bus):
        yield from wb_write(bus, 0x0, 0xE, 0xF) # DFII_CONTROL_ODT|DFII_CONTROL_RESET_N|DFI_CONTROL_CKE
        yield from wb_write(bus, 0xC >> 2, 0x0, 0xF)
        yield from wb_write(bus, 0x10 >> 2, 0x0, 0xF)
        yield from wb_write(bus, 0x0, 0xC, 0xF)
        yield from wb_write(bus, 0x0, 0xE, 0xF)

        # MR2
        yield from wb_write(bus, 0xC >> 2, 0x200, 0xF)
        yield from wb_write(bus, 0x10 >> 2, 0x2, 0xF)
        yield from wb_write(bus, 0x4 >> 2, 0xF, 0xF)
        yield from wb_write(bus, 0x8 >> 2, 0x1, 0xF)

        # MR3
        yield from wb_write(bus, 0xC >> 2, 0x0, 0xF)
        yield from wb_write(bus, 0x10 >> 2, 0x3, 0xF)
        yield from wb_write(bus, 0x4 >> 2, 0xF, 0xF)
        yield from wb_write(bus, 0x8 >> 2, 0x1, 0xF)

        # MR1
        yield from wb_write(bus, 0xC >> 2, 0x6, 0xF)
        yield from wb_write(bus, 0x10 >> 2, 0x1, 0xF)
        yield from wb_write(bus, 0x4 >> 2, 0xF, 0xF)
        yield from wb_write(bus, 0x8 >> 2, 0x1, 0xF)

        # MR0
        yield from wb_write(bus, 0xC >> 2, 0x320, 0xF)
        yield from wb_write(bus, 0x10 >> 2, 0x0, 0xF)
        yield from wb_write(bus, 0x4 >> 2, 0xF, 0xF)
        yield from wb_write(bus, 0x8 >> 2, 0x1, 0xF)
        for i in range(200):
            yield

        # ZQ
        yield from wb_write(bus, 0xC >> 2, 0x400, 0xF)
        yield from wb_write(bus, 0x10 >> 2, 0x0, 0xF)
        yield from wb_write(bus, 0x4 >> 2, 0x3, 0xF)
        yield from wb_write(bus, 0x8 >> 2, 0x1, 0xF)
        for i in range(200):
            yield

        yield from wb_write(bus, 0, 0x1, 0xF)
        for i in range(2000):
            yield

    def test_multiple_reads(self):
        soc = DDR3SoC(clk_freq=100e6,
            dramcore_addr=0x00000000,
            ddr_addr=0x10000000)

        def process():
            yield from SocTestCase.init_seq(soc.bus)

            yield from wb_write(soc.bus, 0x10000000 >> 2, 0xACAB2020, 0xF, 128)
            yield

            # Check for data persistence
            for i in range(10):
                res = yield from wb_read(soc.bus, 0x10000000 >> 2, 0xF, 128)
                yield
                self.assertEqual(res, 0xACAB2020)

        runSimulation(soc, process, "test_soc_multiple_reads.vcd")

    def test_interleaved_read_write(self):
        soc = DDR3SoC(clk_freq=100e6,
            dramcore_addr=0x00000000,
            ddr_addr=0x10000000)

        def process():
            yield from SocTestCase.init_seq(soc.bus)

            yield from wb_write(soc.bus, 0x10000000 >> 2, 0xF00DFACE, 0xF, 128)
            yield from wb_write(soc.bus, 0x10000004 >> 2, 0x12345678, 0xF, 128)
            yield from wb_write(soc.bus, 0x10000008 >> 2, 0x00BA0BAB, 0xF, 128)

            res = yield from wb_read(soc.bus, 0x10000000 >> 2, 0xF, 128)
            self.assertEqual(res, 0xF00DFACE)

            yield from wb_write(soc.bus, 0x10000008 >> 2, 0xCAFE1000, 0xF, 128)

            res = yield from wb_read(soc.bus, 0x10000004 >> 2, 0xF, 128)
            self.assertEqual(res, 0x12345678)

            res = yield from wb_read(soc.bus, 0x10000008 >> 2, 0xF, 128)
            self.assertEqual(res, 0xCAFE1000)

        runSimulation(soc, process, "test_soc_interleaved_read_write.vcd")

    def test_sequential_reads(self):
        soc = DDR3SoC(clk_freq=100e6,
            dramcore_addr=0x00000000,
            ddr_addr=0x10000000)

        def process():
            yield from SocTestCase.init_seq(soc.bus)

            # Should read from same row/col/bank
            yield from wb_read(soc.bus, 0x10000000 >> 2, 0xF, 128)
            yield from wb_read(soc.bus, 0x10000004 >> 2, 0xF, 128)
            yield from wb_read(soc.bus, 0x10000008 >> 2, 0xF, 128)
            yield from wb_read(soc.bus, 0x1000000C >> 2, 0xF, 128)

            # Should read from a different row
            yield from wb_read(soc.bus, 0x10000010 >> 2, 0xF, 128)
            yield from wb_read(soc.bus, 0x10000014 >> 2, 0xF, 128)
            yield from wb_read(soc.bus, 0x10000018 >> 2, 0xF, 128)
            yield from wb_read(soc.bus, 0x1000001C >> 2, 0xF, 128)

        runSimulation(soc, process, "test_soc_sequential_reads.vcd")

    def test_random_memtest(self):
        soc = DDR3SoC(clk_freq=100e6,
            dramcore_addr=0x00000000,
            ddr_addr=0x10000000)

        def process():
            yield from SocTestCase.init_seq(soc.bus)

            n = 64

            memtest_values = []
            for i in range(n):
                memtest_values.append(random.randint(0, 0xFFFFFFFF))

            # Write
            for i in range(n):
                yield from wb_write(soc.bus, (0x10000000 >> 2) + i, memtest_values[i], 0xF, 256)

            # Read
            for i in range(n):
                self.assertEqual(memtest_values[i], (yield from wb_read(soc.bus, (0x10000000 >> 2) + i, 0xF, 256)))

        runSimulation(soc, process, "test_soc_random_memtest.vcd")

    def test_continuous_memtest(self):
        soc = DDR3SoC(clk_freq=100e6,
            dramcore_addr=0x00000000,
            ddr_addr=0x10000000)

        def process():
            yield from SocTestCase.init_seq(soc.bus)

            n = 128

            # Write
            for i in range(n):
                yield from wb_write(soc.bus, (0x10000000 >> 2) + i, 0xFACE0000 | i, 0xF, 256)

            # Read
            for i in range(n):
                self.assertEqual(0xFACE0000 | i, (yield from wb_read(soc.bus, (0x10000000 >> 2) + i, 0xF, 256)))

        runSimulation(soc, process, "test_soc_continuous_memtest.vcd")
