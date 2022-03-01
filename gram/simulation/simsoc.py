# This file is Copyright (c) 2020 LambdaConcept <contact@lambdaconcept.com>

from nmigen import *
from nmigen.build import Resource, Pins, Attrs, Subsignal
from nmigen_soc import wishbone, memory

from lambdasoc.periph import Peripheral
from lambdasoc.soc.base import SoC

from gram.core import gramCore
from gram.phy.ecp5ddrphy import ECP5DDRPHY
from gram.modules import (MT41K256M16, MT41K64M16)
from gram.frontend.wishbone import gramWishbone

from icarusecpix5platform import IcarusECPIX5Platform
from crg import *

class DDR3SoC(SoC, Elaboratable):
    def __init__(self, *, clk_freq,
                 ddrphy_addr, dramcore_addr,
                 ddr_addr):
        self.crg = ECPIX5CRG()

        self._decoder = wishbone.Decoder(addr_width=30, data_width=32, granularity=8,
                                         features={"cti", "bte"})

        ddr_pins = platform.request("ddr3", 0, dir={"dq":"-", "dqs":"-"},
            xdr={"rst": 4, "clk":4, "a":4, "ba":4, "clk_en":4, "we_n":4,
                 "cs": 4, "odt":4, "ras":4, "cas":4, "we":4})
        self.ddrphy = DomainRenamer("dramsync")(ECP5DDRPHY(ddr_pins))
        self._decoder.add(self.ddrphy.bus, addr=ddrphy_addr)

        #ddrmodule = MT41K256M16(clk_freq, "1:2")
        ddrmodule = MT41K64M16(clk_freq, "1:2")

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

        resources = [
            Resource("wishbone", 0,
                Subsignal("adr", Pins("ADDR0 ADDR1 ADDR2 ADDR3 ADDR4 ADDR5 ADDR6 ADDR7"
                    " ADDR8 ADDR9 ADDR10 ADDR11 ADDR12 ADDR13 ADDR14 ADDR15"
                    " ADDR16 ADDR17 ADDR18 ADDR19 ADDR20 ADDR21 ADDR22 ADDR23"
                    " ADDR24 ADDR25 ADDR26 ADDR27 ADDR28 ADDR29 ADDR30 ADDR31", dir="i")),
                Subsignal("dat_r", Pins("DATR0 DATR1 DATR2 DATR3 DATR4 DATR5 DATR6 DATR7"
                    " DATR8 DATR9 DATR10 DATR11 DATR12 DATR13 DATR14 DATR15"
                    " DATR16 DATR17 DATR18 DATR19 DATR20 DATR21 DATR22 DATR23"
                    " DATR24 DATR25 DATR26 DATR27 DATR28 DATR29 DATR30 DATR31", dir="o")),
                Subsignal("dat_w", Pins("DATW0 DATW1 DATW2 DATW3 DATW4 DATW5 DATW6 DATW7"
                    " DATW8 DATW9 DATW10 DATW11 DATW12 DATW13 DATW14 DATW15"
                    " DATW16 DATW17 DATW18 DATW19 DATW20 DATW21 DATW22 DATW23"
                    " DATW24 DATW25 DATW26 DATW27 DATW28 DATW29 DATW30 DATW31", dir="i")),
                Subsignal("cyc", Pins("CYC", dir="i")),
                Subsignal("stb", Pins("STB", dir="i")),
                Subsignal("sel", Pins("SEL0 SEL1 SEL2 SEL3", dir="i")),
                Subsignal("ack", Pins("ACK", dir="o")),
                Subsignal("we", Pins("WE", dir="i"))),
        ]
        platform.add_resources(resources)

        m.submodules.sysclk = self.crg

        m.submodules.decoder = self._decoder
        m.submodules.ddrphy = self.ddrphy
        m.submodules.dramcore = self.dramcore
        m.submodules.drambone = self.drambone

        ext_bus = platform.request("wishbone", 0)
        m.d.comb += [
            self._decoder.bus.adr.eq(ext_bus.adr.i),
            self._decoder.bus.dat_w.eq(ext_bus.dat_w.i),
            ext_bus.dat_r.o.eq(self._decoder.bus.dat_r),
            self._decoder.bus.cyc.eq(ext_bus.cyc.i),
            self._decoder.bus.stb.eq(ext_bus.stb.i),
            self._decoder.bus.sel.eq(ext_bus.sel.i),
            ext_bus.ack.o.eq(self._decoder.bus.ack),
            self._decoder.bus.we.eq(ext_bus.we.i),
        ]

        return m


if __name__ == "__main__":
    platform = IcarusECPIX5Platform()

    soc = DDR3SoC(clk_freq=int(platform.default_clk_frequency),
        ddrphy_addr=0x00008000, dramcore_addr=0x00009000,
        ddr_addr=0x10000000)

    soc.build(do_build=True)
    platform.build(soc, build_dir="build_simsoc")
