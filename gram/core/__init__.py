from nmigen import *

from lambdasoc.periph import Peripheral

from gram.dfii import DFIInjector
from gram.core.controller import ControllerSettings, gramController
from gram.core.crossbar import gramCrossbar

# Core ---------------------------------------------------------------------------------------------

class gramCore(Peripheral, Elaboratable):
    def __init__(self, phy, geom_settings, timing_settings, clk_freq, **kwargs):
        self._phy = phy
        self._geom_settings = geom_settings
        self._timing_settings = timing_settings
        self._clk_freq = clk_freq
        self._kwargs = kwargs

    def elaborate(self, platform):
        m = Module()

        m.submodules.dfii = dfii = DFIInjector(
            addressbits = self._geom_settings.addressbits,
            bankbits    = self._geom_settings.bankbits,
            nranks      = self._phy.settings.nranks,
            databits    = self._phy.settings.dfi_databits,
            nphases     = self._phy.settings.nphases)
        m.d.comb += dfii.master.connect(self._phy.dfi)

        m.submodules.controller = controller = gramController(
            phy_settings    = self._phy.settings,
            geom_settings   = self._geom_settings,
            timing_settings = self._timing_settings,
            clk_freq        = self._clk_freq,
            **self._kwargs)
        m.d.comb += controller.dfi.connect(dfii.slave)

        m.submodules.crossbar = gramCrossbar(controller.interface)

        return m
