# This file is Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2016-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2020 LambdaConcept <contact@lambdaconcept.com>
# License: BSD

from nmigen import *

from gram.phy import dfi
from lambdasoc.periph import Peripheral

# PhaseInjector ------------------------------------------------------------------------------------

class PhaseInjector(Peripheral, Elaboratable):
    def __init__(self, phase):
        super().__init__(name = "phaseinjector")

        bank = self.csr_bank()
        self._command = bank.csr(6, "rw")
        self._command_issue = bank.csr(1, "rw")
        self._address = bank.csr(len(phase.address), "rw")
        self._baddress = bank.csr(len(phase.bank), "rw")
        self._wrdata = bank.csr(len(phase.wrdata), "rw")
        self._rddata = bank.csr(len(phase.rddata), "rw")

        self._phase = phase

    def elaborate(self, platform):
        m = Module()

        m.d.comb += [
            self._phase.address.eq(self._address.r_data),
            self._phase.bank.eq(self._baddress.r_data),
            self._phase.wrdata_en.eq(self._command_issue.r_stb & self._command.r_data[4]),
            self._phase.rddata_en.eq(self._command_issue.r_stb & self._command.r_data[5]),
            self._phase.wrdata.eq(self._wrdata.r_data),
            self._phase.wrdata_mask.eq(0)
        ]

        with m.If(self._command_issue.r_stb):
            m.d.comb += [
                self._phase.cs_n.eq(Repl(value=~self._command.r_data[0], count=len(self._phase.cs_n))),
                self._phase.we_n.eq(~self._command.r_data[1]),
                self._phase.cas_n.eq(~self._command.r_data[2]),
                self._phase.ras_n.eq(~self._command.r_data[3]),
            ]
        with m.Else():
            m.d.comb += [
                self._phase.cs_n.eq(Repl(value=1, count=len(self._phase.cs_n))),
                self._phase.we_n.eq(1),
                self._phase.cas_n.eq(1),
                self._phase.ras_n.eq(1),
            ]

        with m.If(self._phase.rddata_valid):
            m.d.sync += self._rddata.w_data.eq(self._phase.rddata)

        return m

# DFIInjector --------------------------------------------------------------------------------------

class DFIInjector(Peripheral, Elaboratable):
    def __init__(self, addressbits, bankbits, nranks, databits, nphases=1):
        super().__init__(name = "dfii")

        self._nranks = nranks

        self._inti  = dfi.Interface(addressbits, bankbits, nranks, databits, nphases)
        self.slave  = dfi.Interface(addressbits, bankbits, nranks, databits, nphases)
        self.master = dfi.Interface(addressbits, bankbits, nranks, databits, nphases)

        bank = self.csr_bank()
        self._control = bank.csr(4, "rw")  # sel, cke, odt, reset_n

    def elaborate(self, platform):
        m = Module()

        for n, phase in enumerate(self._inti.phases):
            m.submodules += PhaseInjector(phase)

        with m.If(self._control.r_data[0]):
            m.d.comb += self.slave.connect(self.master)
        with m.Else():
            m.d.comb += self._inti.connect(self.master)

        for i in range(self._nranks):
            m.d.comb += [phase.cke[i].eq(self._control.r_data[1]) for phase in self._inti.phases]
            m.d.comb += [phase.odt[i].eq(self._control.r_data[2]) for phase in self._inti.phases if hasattr(phase, "odt")]
        m.d.comb += [phase.reset_n.eq(self._control.r_data[3]) for phase in self._inti.phases if hasattr(phase, "reset_n")]

        return m
