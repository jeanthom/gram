from nmigen import *

from lambdasoc.periph import Peripheral

from gram.dfii import DFIInjector
from gram.compat import CSRPrefixProxy
from gram.core.controller import ControllerSettings, gramController
from gram.core.crossbar import gramCrossbar

__ALL__ = ["gramCore"]

class gramCore(Peripheral, Elaboratable):
    def __init__(self, phy, geom_settings, timing_settings, clk_freq, **kwargs):
        super().__init__("core")

        bank = self.csr_bank()

        self._zero_ev = self.event(mode="rise")

        self._phy = phy
        self._geom_settings = geom_settings
        self._timing_settings = timing_settings
        self._clk_freq = clk_freq
        self._kwargs = kwargs

        self.dfii = DFIInjector(
            csr_bank=CSRPrefixProxy(bank, "dfii"),
            addressbits=self._geom_settings.addressbits,
            bankbits=self._geom_settings.bankbits,
            nranks=self._phy.settings.nranks,
            databits=self._phy.settings.dfi_databits,
            nphases=self._phy.settings.nphases)

        self.controller = gramController(
            phy_settings=self._phy.settings,
            geom_settings=self._geom_settings,
            timing_settings=self._timing_settings,
            clk_freq=self._clk_freq,
            **self._kwargs)

        # Size in bytes
        self.size = 2**geom_settings.bankbits * 2**geom_settings.rowbits * 2**geom_settings.colbits

        self.crossbar = gramCrossbar(self.controller.interface)

        self._bridge = self.bridge(data_width=32, granularity=8, alignment=2)
        self.bus = self._bridge.bus
        self.irq = self._bridge.irq

    def elaborate(self, platform):
        m = Module()

        m.submodules.bridge = self._bridge

        m.submodules.dfii = self.dfii
        m.d.comb += self.dfii.master.connect(self._phy.dfi)

        m.submodules.controller = self.controller
        m.d.comb += self.controller.dfi.connect(self.dfii.slave)

        m.submodules.crossbar = self.crossbar

        return m
