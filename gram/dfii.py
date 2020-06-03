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
        bank = self.csr_bank()
        self._command = bank.csr(6, "rw")
        self._command_issue = bank.csr(1, "rw")
        self._address = bank.csr(len(phase.address), "rw", reset_less=True)
        self._baddress = bank.csr(len(phase.bank), "rw", reset_less=True)
        self._wrdata = bank.csr(len(phase.wrdata), "rw", reset_less=True)
        self._rddata = bank.csr(len(phase.rddata))

    def elaborate(self, platform):
        m = Module()

        m.d.comb += [
            phase.address.eq(self._address.storage),
            phase.bank.eq(self._baddress.storage),
            phase.wrdata_en.eq(self._command_issue.re & self._command.storage[4]),
            phase.rddata_en.eq(self._command_issue.re & self._command.storage[5]),
            phase.wrdata.eq(self._wrdata.storage),
            phase.wrdata_mask.eq(0)
        ]

        with m.If(self._command_issue.re):
            m.d.comb += [
                phase.cs_n.eq(Replicate(~self._command.storage[0], len(phase.cs_n))),
                phase.we_n.eq(~self._command.storage[1]),
                phase.cas_n.eq(~self._command.storage[2]),
                phase.ras_n.eq(~self._command.storage[3]),
            ]
        with m.Else():
            m.d.comb += [
                phase.cs_n.eq(Replicate(1, len(phase.cs_n))),
                phase.we_n.eq(1),
                phase.cas_n.eq(1),
                phase.ras_n.eq(1),
            ]

        with m.If(phase.rddata_valid):
            m.d.sync += self._rddata.status.eq(phase.rddata)

        return m

# DFIInjector --------------------------------------------------------------------------------------

class DFIInjector(Peripheral, Elaboratable):
    def __init__(self, addressbits, bankbits, nranks, databits, nphases=1):
        self._inti  = dfi.Interface(addressbits, bankbits, nranks, databits, nphases)
        self.slave  = dfi.Interface(addressbits, bankbits, nranks, databits, nphases)
        self.master = dfi.Interface(addressbits, bankbits, nranks, databits, nphases)

        bank = self.csr_bank()
        self._control = bank.csr(4)  # sel, cke, odt, reset_n

        #for n, phase in enumerate(inti.phases):
        #    setattr(self.submodules, "pi" + str(n), PhaseInjector(phase)) TODO

        # # #

    def elaborate(self, platform):
        m = Module()

        with m.If(self._control.storage[0]):
            m.d.comb += self.slave.connect(self.master)
        with m.Else():
            m.d.comb += self._inti.connect(self.master)

        for i in range(nranks):
            m.d.comb += [phase.cke[i].eq(self._control.storage[1]) for phase in self._inti.phases]
            m.d.comb += [phase.odt[i].eq(self._control.storage[2]) for phase in self._inti.phases if hasattr(phase, "odt")]
        m.d.comb += [phase.reset_n.eq(self._control.storage[3]) for phase in self._inti.phases if hasattr(phase, "reset_n")]

        return m
