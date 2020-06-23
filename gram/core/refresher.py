# This file is Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2016-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2020 LambdaConcept <contact@lambdaconcept.com>
# License: BSD

"""LiteDRAM Refresher."""

from nmigen import *
from nmigen.utils import log2_int

from gram.core.multiplexer import *
from gram.compat import Timeline
import gram.stream as stream

# RefreshExecuter ----------------------------------------------------------------------------------


class RefreshExecuter(Elaboratable):
    """Refresh Executer

    Execute the refresh sequence to the DRAM:
    - Send a "Precharge All" command
    - Wait tRP
    - Send an "Auto Refresh" command
    - Wait tRFC
    """

    def __init__(self, abits, babits, trp, trfc):
        self.start = Signal()
        self.done = Signal()
        self._trp = trp
        self._trfc = trfc

        self.a = Signal(abits)
        self.ba = Signal(babits)
        self.cas = Signal()
        self.ras = Signal()
        self.we = Signal()

    def elaborate(self, platform):
        m = Module()

        trp = self._trp
        trfc = self._trfc

        tl = Timeline([
            # Precharge All
            (0, [
                self.a.eq(2**10),
                self.ba.eq(0),
                self.cas.eq(0),
                self.ras.eq(1),
                self.we.eq(1)
            ]),
            # Auto Refresh after tRP
            (trp, [
                self.a.eq(0),
                self.ba.eq(0),
                self.cas.eq(1),
                self.ras.eq(1),
                self.we.eq(0),
            ]),
            # Done after tRP + tRFC
            (trp + trfc, [
                self.a.eq(0),
                self.ba.eq(0),
                self.cas.eq(0),
                self.ras.eq(0),
                self.we.eq(0),
                self.done.eq(1),
            ]),
        ])
        m.submodules += tl
        m.d.comb += tl.trigger.eq(self.start)

        return m

# RefreshSequencer ---------------------------------------------------------------------------------


class RefreshSequencer(Elaboratable):
    """Refresh Sequencer

    Sequence N refreshs to the DRAM.
    """

    def __init__(self, abits, babits, trp, trfc, postponing=1):
        self.start = Signal()
        self.done = Signal()

        self._trp = trp
        self._trfc = trfc
        self._postponing = postponing
        self._abits = abits
        self._babits = babits

        self.a = Signal(abits)
        self.ba = Signal(babits)
        self.cas = Signal()
        self.ras = Signal()
        self.we = Signal()

    def elaborate(self, platform):
        m = Module()

        executer = RefreshExecuter(self._abits, self._babits, self._trp, self._trfc)
        m.submodules += executer
        m.d.comb += [
            self.a.eq(executer.a),
            self.ba.eq(executer.ba),
            self.cas.eq(executer.cas),
            self.ras.eq(executer.ras),
            self.we.eq(executer.we),
        ]

        count = Signal(range(self._postponing), reset=self._postponing-1)
        with m.If(self.start):
            m.d.sync += count.eq(count.reset)
        with m.Elif(executer.done):
            with m.If(count != 0):
                m.d.sync += count.eq(count-1)

        m.d.comb += [
            executer.start.eq(self.start | (count != 0)),
            self.done.eq(executer.done & (count == 0)),
        ]

        return m

# RefreshTimer -------------------------------------------------------------------------------------


class RefreshTimer(Elaboratable):
    """Refresh Timer

    Generate periodic pulses (tREFI period) to trigger DRAM refresh.
    """

    def __init__(self, trefi):
        self.wait = Signal()
        self.done = Signal()
        self.count = Signal(range(trefi))
        self._trefi = trefi

    def elaborate(self, platform):
        m = Module()

        trefi = self._trefi

        done = Signal()
        count = Signal(range(trefi), reset=trefi-1)

        with m.If(self.wait & ~self.done):
            m.d.sync += count.eq(count-1)
        with m.Else():
            m.d.sync += count.eq(count.reset)

        m.d.comb += [
            done.eq(count == 0),
            self.done.eq(done),
            self.count.eq(count)
        ]

        return m

# RefreshPostponer -------------------------------------------------------------------------------


class RefreshPostponer(Elaboratable):
    """Refresh Postponer

    Postpone N Refresh requests and generate a request when N is reached.
    """

    def __init__(self, postponing=1):
        self.req_i = Signal()
        self.req_o = Signal(reset=0)
        self._postponing = postponing

    def elaborate(self, platform):
        m = Module()

        count = Signal(range(self._postponing), reset=self._postponing-1)

        with m.If(self.req_i):
            with m.If(count == 0):
                m.d.sync += [
                    count.eq(count.reset),
                    self.req_o.eq(1),
                ]
            with m.Else():
                m.d.sync += count.eq(count-1)

        return m

# ZQCSExecuter ----------------------------------------------------------------------------------


class ZQCSExecuter(Elaboratable):
    """ZQ Short Calibration Executer

    Execute the ZQCS sequence to the DRAM:
    - Send a "Precharge All" command
    - Wait tRP
    - Send an "ZQ Short Calibration" command
    - Wait tZQCS
    """

    def __init__(self, abits, babits, trp, tzqcs):
        self.start = Signal()
        self.done = Signal()
        self._trp = trp
        self._tzqcs = tzqcs

        self.a = Signal(abits)
        self.ba = Signal(babits)
        self.cas = Signal()
        self.ras = Signal()
        self.we = Signal()

    def elaborate(self, platform):
        m = Module()

        trp = self._trp
        tzqcs = self._tzqcs

        tl = Timeline([
            # Precharge All
            (0, [
                self.a.eq(2**10),
                self.ba.eq(0),
                self.cas.eq(0),
                self.ras.eq(1),
                self.we.eq(1),
                self.done.eq(0)
            ]),
            # ZQ Short Calibration after tRP
            (trp, [
                self.a.eq(0),
                self.ba.eq(0),
                self.cas.eq(0),
                self.ras.eq(0),
                self.we.eq(1),
                self.done.eq(0),
            ]),
            # Done after tRP + tZQCS
            (trp + tzqcs, [
                self.a.eq(0),
                self.ba.eq(0),
                self.cas.eq(0),
                self.ras.eq(0),
                self.we.eq(0),
                self.done.eq(1)
            ]),
        ])
        m.submodules += tl
        m.d.comb += tl.trigger.eq(self.start)

        return m

# Refresher ----------------------------------------------------------------------------------------


class Refresher(Elaboratable):
    """Refresher

    Manage DRAM refresh.

    The DRAM needs to be periodically refreshed with a tREFI period to avoid data corruption. During
    a refresh, the controller send a "Precharge All" command to close and precharge all rows and then
    send a "Auto Refresh" command.

    Before executing the refresh, the Refresher advertises the Controller that a refresh should occur,
    this allows the Controller to finish the current transaction and block next transactions. Once all
    transactions are done, the Refresher can execute the refresh Sequence and release the Controller.

    """

    def __init__(self, settings, clk_freq, zqcs_freq=1e0, postponing=1):
        assert postponing <= 8
        self._abits = settings.geom.addressbits
        self._babits = settings.geom.bankbits + log2_int(settings.phy.nranks)
        self.cmd = cmd = stream.Endpoint(
            cmd_request_rw_layout(a=self._abits, ba=self._babits))
        self._postponing = postponing
        self._settings = settings
        self._clk_freq = clk_freq
        self._zqcs_freq = zqcs_freq

    def elaborate(self, platform):
        m = Module()

        wants_refresh = Signal()
        wants_zqcs = Signal()

        settings = self._settings

        # Refresh Timer ----------------------------------------------------------------------------
        timer = RefreshTimer(settings.timing.tREFI)
        m.submodules.timer = timer
        m.d.comb += timer.wait.eq(~timer.done)

        # Refresh Postponer ------------------------------------------------------------------------
        postponer = RefreshPostponer(self._postponing)
        m.submodules.postponer = postponer
        m.d.comb += [
            postponer.req_i.eq(timer.done),
            wants_refresh.eq(postponer.req_o),
        ]

        # Refresh Sequencer ------------------------------------------------------------------------
        sequencer = RefreshSequencer(
            self._abits, self._babits, settings.timing.tRP, settings.timing.tRFC, self._postponing)
        m.submodules.sequencer = sequencer

        if settings.timing.tZQCS is not None:
            # ZQCS Timer ---------------------------------------------------------------------------
            zqcs_timer = RefreshTimer(int(self._clk_freq/self._zqcs_freq))
            m.submodules.zqcs_timer = zqcs_timer
            m.d.comb += wants_zqcs.eq(zqcs_timer.done)

            # ZQCS Executer ------------------------------------------------------------------------
            zqcs_executer = ZQCSExecuter(
                self._abits, self._babits, settings.timing.tRP, settings.timing.tZQCS)
            m.submodules.zqs_executer = zqcs_executer
            m.d.comb += zqcs_timer.wait.eq(~zqcs_executer.done)

        # Refresh FSM ------------------------------------------------------------------------------
        with m.FSM():
            with m.State("Idle"):
                with m.If(settings.with_refresh & wants_refresh):
                    m.next = "Wait-Bank-Machines"

            with m.State("Wait-Bank-Machines"):
                m.d.comb += self.cmd.valid.eq(1)
                with m.If(self.cmd.ready):
                    m.d.comb += sequencer.start.eq(1)
                    m.next = "Do-Refresh"

            if settings.timing.tZQCS is None:
                with m.State("Do-Refresh"):
                    m.d.comb += self.cmd.valid.eq(1)
                    with m.If(sequencer.done):
                        m.d.comb += [
                            self.cmd.valid.eq(0),
                            self.cmd.last.eq(1),
                        ]
                        m.next = "Idle"
            else:
                with m.State("Do-Refresh"):
                    m.d.comb += self.cmd.valid.eq(1)
                    with m.If(sequencer.done):
                        with m.If(wants_zqcs):
                            m.d.comb += zqcs_executer.start.eq(1)
                            m.next = "Do-Zqcs"
                        with m.Else():
                            m.d.comb += [
                                self.cmd.valid.eq(0),
                                self.cmd.last.eq(1),
                            ]
                            m.next = "Idle"

                with m.State("Do-Zqcs"):
                    m.d.comb += self.cmd.valid.eq(1)
                    with m.If(zqcs_executer.done):
                        m.d.comb += [
                            self.cmd.valid.eq(0),
                            self.cmd.last.eq(1),
                        ]
                        m.next = "Idle"

        if settings.timing.tZQCS is None:
            m.d.comb += [
                self.cmd.a.eq(sequencer.a),
                self.cmd.ba.eq(sequencer.ba),
                self.cmd.cas.eq(sequencer.cas),
                self.cmd.ras.eq(sequencer.ras),
                self.cmd.we.eq(sequencer.we),
            ]
        else:
            m.d.comb += [
                self.cmd.a.eq(zqcs_executer.a),
                self.cmd.ba.eq(zqcs_executer.ba),
                self.cmd.cas.eq(zqcs_executer.cas),
                self.cmd.ras.eq(zqcs_executer.ras),
                self.cmd.we.eq(zqcs_executer.we),
            ]


        return m
