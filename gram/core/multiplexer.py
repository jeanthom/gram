# This file is Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2016-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2018 John Sully <john@csquare.ca>
# This file is Copyright (c) 2020 LambdaConcept <contact@lambdaconcept.com>
# License: BSD

"""LiteDRAM Multiplexer."""

import math

from nmigen import *
from nmigen.asserts import Assert, Assume
from nmigen.lib.scheduler import RoundRobin

from gram.common import *
import gram.stream as stream
from gram.compat import delayed_enter

__ALL__ = ["Multiplexer"]

class _CommandChooser(Elaboratable):
    """Arbitrates between requests, filtering them based on their type

    Uses RoundRobin to choose current request, filters requests based on
    `want_*` signals.

    Parameters
    ----------
    requests : [Endpoint(cmd_request_rw_layout), ...]
        Request streams to consider for arbitration

    Attributes
    ----------
    want_reads : Signal, in
        Consider read requests
    want_writes : Signal, in
        Consider write requests
    want_cmds : Signal, in
        Consider command requests (without ACT)
    want_activates : Signal, in
        Also consider ACT commands
    cmd : Endpoint(cmd_request_rw_layout)
        Currently selected request stream (when ~cmd.valid, cas/ras/we are 0)
    """

    def __init__(self, requests):
        self.want_reads = Signal()
        self.want_writes = Signal()
        self.want_cmds = Signal()
        self.want_activates = Signal()

        self._requests = requests
        a = len(requests[0].a)
        ba = len(requests[0].ba)

        # cas/ras/we are 0 when valid is inactive
        self.cmd = stream.Endpoint(cmd_request_rw_layout(a, ba))
        self.ready = Signal(len(requests))

    def elaborate(self, platform):
        m = Module()

        n = len(self._requests)

        valids = Signal(n)
        for i, request in enumerate(self._requests):
            is_act_cmd = request.ras & ~request.cas & ~request.we
            command = request.is_cmd & self.want_cmds & (~is_act_cmd | self.want_activates)
            read = request.is_read == self.want_reads
            write = request.is_write == self.want_writes
            m.d.comb += valids[i].eq(request.valid & (command | (read & write)))

        # Arbitrate if a command is being accepted or if the command is not valid to ensure a valid
        # command is selected when cmd.ready goes high.
        m.submodules.arbiter = arbiter = EnableInserter(self.cmd.ready | ~self.cmd.valid)(RoundRobin(count=n))
        choices = Array(valids[i] for i in range(n))
        m.d.comb += [
            arbiter.requests.eq(valids),
            self.cmd.valid.eq(choices[arbiter.grant])
        ]

        for name in ["a", "ba", "is_read", "is_write", "is_cmd"]:
            choices = Array(getattr(req, name) for req in self._requests)
            m.d.comb += getattr(self.cmd, name).eq(choices[arbiter.grant])

        for name in ["cas", "ras", "we"]:
            # we should only assert those signals when valid is 1
            choices = Array(getattr(req, name) for req in self._requests)
            with m.If(self.cmd.valid):
                m.d.comb += getattr(self.cmd, name).eq(choices[arbiter.grant])

        for i, request in enumerate(self._requests):
            with m.If(self.cmd.valid & self.cmd.ready & (arbiter.grant == i)):
                m.d.comb += self.ready[i].eq(1)

        return m

    # helpers
    def accept(self):
        return self.cmd.valid & self.cmd.ready

    def activate(self):
        return self.cmd.ras & ~self.cmd.cas & ~self.cmd.we

    def write(self):
        return self.cmd.is_write

    def read(self):
        return self.cmd.is_read

# _Steerer -----------------------------------------------------------------------------------------


(STEER_NOP, STEER_CMD, STEER_REQ, STEER_REFRESH) = range(4)


class _Steerer(Elaboratable):
    """Connects selected request to DFI interface

    cas/ras/we/is_write/is_read are connected only when `cmd.valid & cmd.ready`.
    Rank bits are decoded and used to drive cs_n in multi-rank systems,
    STEER_REFRESH always enables all ranks.

    Parameters
    ----------
    commands : [Endpoint(cmd_request_rw_layout), ...]
        Command streams to choose from. Must be of len=4 in the order:
            NOP, CMD, REQ, REFRESH
        NOP can be of type Record(cmd_request_rw_layout) instead, so that it is
        always considered invalid (because of lack of the `valid` attribute).
    dfi : dfi.Interface
        DFI interface connected to PHY

    Attributes
    ----------
    sel : [Signal(range(len(commands))), ...], in
        Signals for selecting which request gets connected to the corresponding
        DFI phase. The signals should take one of the values from STEER_* to
        select given source.
    """

    def __init__(self, commands, dfi):
        if len(commands) != 4:
            raise ValueError("Commands is not the right size")

        self._commands = commands
        self._dfi = dfi
        self.sel = [Signal(range(len(commands))) for i in range(len(dfi.phases))]

    def elaborate(self, platform):
        m = Module()

        commands = self._commands
        dfi = self._dfi

        def valid_and(cmd, attr):
            if not hasattr(cmd, "valid"):
                return 0
            else:
                return cmd.valid & cmd.ready & getattr(cmd, attr)

        for i, (phase, sel) in enumerate(zip(dfi.phases, self.sel)):
            nranks = len(phase.cs)
            rankbits = log2_int(nranks)
            if hasattr(phase, "reset"):
                m.d.comb += phase.reset.eq(0)
            m.d.comb += phase.clk_en.eq(Repl(Signal(reset=1), nranks))
            if hasattr(phase, "odt"):
                # FIXME: add dynamic drive for multi-rank (will be needed for high frequencies)
                m.d.comb += phase.odt.eq(Repl(Signal(reset=1), nranks))
            if rankbits:
                rank_decoder = Decoder(nranks)
                m.submodules += rank_decoder
                m.d.comb += rank_decoder.i.eq(
                    (Array(cmd.ba[-rankbits:] for cmd in commands)[sel]))
                if i == 0:  # Select all ranks on refresh.
                    with m.If(sel == STEER_REFRESH):
                        m.d.sync += phase.cs.eq(1)
                    with m.Else():
                        m.d.sync += phase.cs.eq(rank_decoder.o)
                else:
                    m.d.sync += phase.cs.eq(rank_decoder.o)
                m.d.sync += phase.bank.eq(Array(cmd.ba[:-rankbits]
                                                for cmd in commands)[sel])
            else:
                m.d.sync += [
                    phase.cs.eq(1),
                    phase.bank.eq(Array(cmd.ba[:] for cmd in commands)[sel]),
                ]

            m.d.sync += [
                phase.address.eq(Array(cmd.a for cmd in commands)[sel]),
                phase.cas.eq(Array(valid_and(cmd, "cas") for cmd in commands)[sel]),
                phase.ras.eq(Array(valid_and(cmd, "ras") for cmd in commands)[sel]),
                phase.we.eq(Array(valid_and(cmd, "we") for cmd in commands)[sel])
            ]

            rddata_ens = Array(valid_and(cmd, "is_read") for cmd in commands)
            wrdata_ens = Array(valid_and(cmd, "is_write") for cmd in commands)
            m.d.sync += [
                phase.rddata_en.eq(rddata_ens[sel]),
                phase.wrdata_en.eq(wrdata_ens[sel])
            ]

        return m

class _AntiStarvation(Elaboratable):
    def __init__(self, timeout):
        self.en = Signal()
        self.max_time = Signal(reset=1)
        self._timeout = timeout

    def elaborate(self, platform):
        m = Module()

        # TODO: timeout=1 fails formal checks
        assert self._timeout != 1

        if self._timeout > 0:
            time = Signal(range(self._timeout))
            with m.If(~self.en):
                m.d.sync += [
                    time.eq(self._timeout-1),
                    self.max_time.eq(0),
                ]
            with m.Elif(time != 0):
                m.d.sync += time.eq(time-1)
                with m.If(time == 1):
                    m.d.sync += self.max_time.eq(1)
                with m.Else():
                    m.d.sync += self.max_time.eq(0)
        else:
            m.d.comb += self.max_time.eq(0)

        if platform == "formal" and self._timeout > 0:
            m.d.comb += Assert(self.max_time == (time == 0))

        return m

class Multiplexer(Elaboratable):
    """Multplexes requets from BankMachines to DFI

    This module multiplexes requests from BankMachines (and Refresher) and
    connects them to DFI. Refresh commands are coordinated between the Refresher
    and BankMachines to ensure there are no conflicts. Enforces required timings
    between commands (some timings are enforced by BankMachines).

    Parameters
    ----------
    settings : ControllerSettings
        Controller settings (with .phy, .geom and .timing settings)
    bank_machines : [BankMachine, ...]
        Bank machines that generate command requests to the Multiplexer
    refresher : Refresher
        Generates REFRESH command requests
    dfi : dfi.Interface
        DFI connected to the PHY
    interface : LiteDRAMInterface
        Data interface connected directly to LiteDRAMCrossbar
    """

    def __init__(self,
                 settings,
                 bank_machines,
                 refresher,
                 dfi,
                 interface):
        assert(settings.phy.nphases == len(dfi.phases))
        self._settings = settings
        self._bank_machines = bank_machines
        self._refresher = refresher
        self._dfi = dfi
        self._interface = interface

    def elaborate(self, platform):
        m = Module()

        settings = self._settings
        bank_machines = self._bank_machines
        refresher = self._refresher
        dfi = self._dfi
        interface = self._interface

        ras_allowed = Signal(reset=1)
        cas_allowed = Signal(reset=1)

        # Command choosing -------------------------------------------------------------------------
        requests = [bm.cmd for bm in bank_machines]
        m.submodules.choose_cmd = choose_cmd = _CommandChooser(requests)
        m.submodules.choose_req = choose_req = _CommandChooser(requests)
        for i, request in enumerate(requests):
            m.d.comb += request.ready.eq(
                choose_cmd.ready[i] | choose_req.ready[i])
        if settings.phy.nphases == 1:
            # When only 1 phase, use choose_req for all requests
            choose_cmd = choose_req
            m.d.comb += choose_req.want_cmds.eq(1)
            m.d.comb += choose_req.want_activates.eq(ras_allowed)

        # Command steering -------------------------------------------------------------------------
        nop = Record(cmd_request_layout(settings.geom.addressbits,
                                        log2_int(len(bank_machines))))
        # nop must be 1st
        commands = [nop, choose_cmd.cmd, choose_req.cmd, refresher.cmd]
        m.submodules.steerer = steerer = _Steerer(commands, dfi)

        # tRRD timing (Row to Row delay) -----------------------------------------------------------
        m.submodules.trrdcon = trrdcon = tXXDController(settings.timing.tRRD)
        m.d.comb += trrdcon.valid.eq(choose_cmd.accept() & choose_cmd.activate())

        # tFAW timing (Four Activate Window) -------------------------------------------------------
        m.submodules.tfawcon = tfawcon = tFAWController(settings.timing.tFAW)
        m.d.comb += tfawcon.valid.eq(choose_cmd.accept() & choose_cmd.activate())

        # RAS control ------------------------------------------------------------------------------
        m.d.comb += ras_allowed.eq(trrdcon.ready & tfawcon.ready)

        # tCCD timing (Column to Column delay) -----------------------------------------------------
        m.submodules.tccdcon = tccdcon = tXXDController(settings.timing.tCCD)
        m.d.comb += tccdcon.valid.eq(choose_req.accept() & (choose_req.write() | choose_req.read()))

        # CAS control ------------------------------------------------------------------------------
        m.d.comb += cas_allowed.eq(tccdcon.ready)

        # tWTR timing (Write to Read delay) --------------------------------------------------------
        write_latency = math.ceil(settings.phy.cwl / settings.phy.nphases)
        m.submodules.twtrcon = twtrcon = tXXDController(
            settings.timing.tWTR + write_latency +
            # tCCD must be added since tWTR begins after the transfer is complete
            settings.timing.tCCD if settings.timing.tCCD is not None else 0)
        m.d.comb += twtrcon.valid.eq(choose_req.accept() & choose_req.write())

        # Read/write turnaround --------------------------------------------------------------------
        reads = Signal(len(requests))
        m.d.comb += reads.eq(Cat([req.valid & req.is_read for req in requests]))
        writes = Signal(len(requests))
        m.d.comb += writes.eq(Cat([req.valid & req.is_write for req in requests]))

        # Anti Starvation --------------------------------------------------------------------------
        m.submodules.read_antistarvation = read_antistarvation = _AntiStarvation(settings.read_time)
        m.submodules.write_antistarvation = write_antistarvation = _AntiStarvation(settings.write_time)

        # Refresh ----------------------------------------------------------------------------------
        m.d.comb += [bm.refresh_req.eq(refresher.cmd.valid) for bm in bank_machines]
        bm_refresh_gnts = Signal(len(bank_machines))
        m.d.comb += bm_refresh_gnts.eq(Cat([bm.refresh_gnt for bm in bank_machines]))

        # Datapath ---------------------------------------------------------------------------------
        all_rddata = [p.rddata for p in dfi.phases]
        all_wrdata = [p.wrdata for p in dfi.phases]
        all_wrdata_mask = [p.wrdata_mask for p in dfi.phases]
        m.d.comb += [
            interface.rdata.eq(Cat(*all_rddata)),
            Cat(*all_wrdata).eq(interface.wdata),
            Cat(*all_wrdata_mask).eq(~interface.wdata_we)
        ]

        def steerer_sel(steerer, r_w_n):
            r = []
            for i in range(settings.phy.nphases):
                s = steerer.sel[i].eq(STEER_NOP)
                if r_w_n == "read":
                    if i == settings.phy.rdphase:
                        s = steerer.sel[i].eq(STEER_REQ)
                    elif i == settings.phy.rdcmdphase:
                        s = steerer.sel[i].eq(STEER_CMD)
                elif r_w_n == "write":
                    if i == settings.phy.wrphase:
                        s = steerer.sel[i].eq(STEER_REQ)
                    elif i == settings.phy.wrcmdphase:
                        s = steerer.sel[i].eq(STEER_CMD)
                else:
                    raise ValueError
                r.append(s)
            return r

        # Control FSM ------------------------------------------------------------------------------
        with m.FSM():
            with m.State("Read"):
                m.d.comb += [
                    read_antistarvation.en.eq(1),
                    choose_req.want_reads.eq(1),
                    steerer_sel(steerer, "read"),
                ]

                with m.If(settings.phy.nphases == 1):
                    m.d.comb += choose_req.cmd.ready.eq(
                        cas_allowed & (~choose_req.activate() | ras_allowed))
                with m.Else():
                    m.d.comb += [
                        choose_cmd.want_activates.eq(ras_allowed),
                        choose_cmd.cmd.ready.eq(
                            ~choose_cmd.activate() | ras_allowed),
                        choose_req.cmd.ready.eq(cas_allowed),
                    ]

                with m.If(writes.any()):
                    # TODO: switch only after several cycles of ~reads.any()?
                    with m.If(~reads.any() | read_antistarvation.max_time):
                        m.next = "RTW"

                with m.If(bm_refresh_gnts.all()):
                    m.next = "Refresh"

            with m.State("Write"):
                m.d.comb += [
                    write_antistarvation.en.eq(1),
                    choose_req.want_writes.eq(1),
                    steerer_sel(steerer, "write"),
                ]

                with m.If(settings.phy.nphases == 1):
                    m.d.comb += choose_req.cmd.ready.eq(
                        cas_allowed & (~choose_req.activate() | ras_allowed))
                with m.Else():
                    m.d.comb += [
                        choose_cmd.want_activates.eq(ras_allowed),
                        choose_cmd.cmd.ready.eq(
                            ~choose_cmd.activate() | ras_allowed),
                        choose_req.cmd.ready.eq(cas_allowed),
                    ]

                with m.If(reads.any()):
                    with m.If(~writes.any() | write_antistarvation.max_time):
                        m.next = "WTR"

                with m.If(bm_refresh_gnts.all()):
                    m.next = "Refresh"

            with m.State("Refresh"):
                m.d.comb += [
                    steerer.sel[0].eq(STEER_REFRESH),
                    refresher.cmd.ready.eq(1),
                ]
                with m.If(refresher.cmd.last):
                    m.next = "Read"

            with m.State("WTR"):
                with m.If(twtrcon.ready):
                    m.next = "Read"

            # TODO: reduce this, actual limit is around (cl+1)/nphases
            delayed_enter(m, "RTW", "Write", settings.phy.read_latency-1)

        return m
