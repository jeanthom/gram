# This file is Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2016-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2020 LambdaConcept <contact@lambdaconcept.com>
# License: BSD

"""LiteDRAM Controller."""

from nmigen import *
from nmigen.utils import log2_int

from gram.common import *
from gram.phy import dfi
from gram.core.refresher import Refresher
from gram.core.bankmachine import BankMachine
from gram.core.multiplexer import Multiplexer

# Settings -----------------------------------------------------------------------------------------
__ALL__ = ["gramController"]

class ControllerSettings(Settings):
    def __init__(self,
                 # Command buffers
                 cmd_buffer_depth=8,
                 cmd_buffer_buffered=False,

                 # Read/Write times
                 read_time=32,
                 write_time=16,

                 # Refresh
                 with_refresh=True,
                 refresh_cls=Refresher,
                 refresh_zqcs_freq=1e0,
                 refresh_postponing=1,

                 # Auto-Precharge
                 with_auto_precharge=True,

                 # Address mapping
                 address_mapping="ROW_BANK_COL"):
        self.set_attributes(locals())

# Controller ---------------------------------------------------------------------------------------


class gramController(Elaboratable):
    def __init__(self, phy_settings, geom_settings, timing_settings, clk_freq,
                 controller_settings=ControllerSettings()):
        self._address_align = log2_int(burst_lengths[phy_settings.memtype])

        # Settings ---------------------------------------------------------------------------------
        self.settings = controller_settings
        self.settings.phy = phy_settings
        self.settings.geom = geom_settings
        self.settings.timing = timing_settings

        # LiteDRAM Interface (User) ----------------------------------------------------------------
        self.interface = interface = gramInterface(
            self._address_align, self.settings)

        # DFI Interface (Memory) -------------------------------------------------------------------
        self.dfi = dfi.Interface(
            addressbits=geom_settings.addressbits,
            bankbits=geom_settings.bankbits,
            nranks=phy_settings.nranks,
            databits=phy_settings.dfi_databits,
            nphases=phy_settings.nphases)

        self._clk_freq = clk_freq

    def elaborate(self, platform):
        m = Module()

        nranks = self.settings.phy.nranks
        nbanks = 2**self.settings.geom.bankbits

        # Refresher --------------------------------------------------------------------------------
        m.submodules.refresher = Refresher(self.settings,
            clk_freq=self._clk_freq,
            zqcs_freq=self.settings.refresh_zqcs_freq,
            postponing=self.settings.refresh_postponing)

        # Bank Machines ----------------------------------------------------------------------------
        bank_machines = []
        for n in range(nranks*nbanks):
            bank_machine = BankMachine(n,
                                       address_width=self.interface.address_width,
                                       address_align=self._address_align,
                                       nranks=nranks,
                                       settings=self.settings)
            bank_machines.append(bank_machine)
            setattr(m.submodules, "bankmachine"+str(n), bank_machine)
            m.d.comb += getattr(self.interface, "bank" +
                                str(n)).connect(bank_machine.req)

        # Multiplexer ------------------------------------------------------------------------------
        m.submodules.multiplexer = Multiplexer(
            settings=self.settings,
            bank_machines=bank_machines,
            refresher=m.submodules.refresher,
            dfi=self.dfi,
            interface=self.interface)

        return m
