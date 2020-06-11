# This file is Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2016-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2020 LambdaConcept <contact@lambdaconcept.com>
# License: BSD

"""LiteDRAM BankMachine (Rows/Columns management)."""

import math

from nmigen import *

from gram.common import *
from gram.core.multiplexer import *
from gram.compat import delayed_enter
import gram.stream as stream

__ALL__ = ["BankMachine"]

# AddressSlicer ------------------------------------------------------------------------------------


class _AddressSlicer:
    """Helper for extracting row/col from address

    Column occupies lower bits of the address, row - higher bits. Address has
    a forced alignment, so column does not contain alignment bits.
    """

    def __init__(self, colbits, address_align):
        self.colbits = colbits
        self.address_align = address_align

    def row(self, address):
        split = self.colbits - self.address_align
        return address[split:]

    def col(self, address):
        split = self.colbits - self.address_align
        return Cat(Repl(0, self.address_align), address[:split])

# BankMachine --------------------------------------------------------------------------------------


class BankMachine(Elaboratable):
    """Converts requests from ports into DRAM commands

    BankMachine abstracts single DRAM bank by keeping track of the currently
    selected row. It converts requests from LiteDRAMCrossbar to targetted
    to that bank into DRAM commands that go to the Multiplexer, inserting any
    needed activate/precharge commands (with optional auto-precharge). It also
    keeps track and enforces some DRAM timings (other timings are enforced in
    the Multiplexer).

    BankMachines work independently from the data path (which connects
    LiteDRAMCrossbar with the Multiplexer directly).

    Stream of requests from LiteDRAMCrossbar is being queued, so that reqeust
    can be "looked ahead", and auto-precharge can be performed (if enabled in
    settings).

    Lock (cmd_layout.lock) is used to synchronise with LiteDRAMCrossbar. It is
    being held when:
     - there is a valid command awaiting in `cmd_buffer_lookahead` - this buffer
       becomes ready simply when the next data gets fetched to the `cmd_buffer`
     - there is a valid command in `cmd_buffer` - `cmd_buffer` becomes ready
       when the BankMachine sends wdata_ready/rdata_valid back to the crossbar

    Parameters
    ----------
    n : int
        Bank number
    address_width : int
        LiteDRAMInterface address width
    address_align : int
        Address alignment depending on burst length
    nranks : int
        Number of separate DRAM chips (width of chip select)
    settings : ControllerSettings
        LiteDRAMController settings

    Attributes
    ----------
    req : Record(cmd_layout)
        Stream of requests from LiteDRAMCrossbar
    refresh_req : Signal(), in
        Indicates that refresh needs to be done, connects to Refresher.cmd.valid
    refresh_gnt : Signal(), out
        Indicates that refresh permission has been granted, satisfying timings
    cmd : Endpoint(cmd_request_rw_layout)
        Stream of commands to the Multiplexer
    """

    def __init__(self, n, address_width, address_align, nranks, settings):
        self.settings = settings
        self.req = req = Record(cmd_layout(address_width))
        self.refresh_req = refresh_req = Signal()
        self.refresh_gnt = refresh_gnt = Signal()

        a = settings.geom.addressbits
        ba = settings.geom.bankbits + log2_int(nranks)
        self.cmd = stream.Endpoint(cmd_request_rw_layout(a, ba))

        self._address_align = address_align
        self._n = n

    def elaborate(self, platform):
        m = Module()

        auto_precharge = Signal()

        # Command buffer ---------------------------------------------------------------------------
        cmd_buffer_layout = [("we", 1), ("addr", len(self.req.addr))]
        cmd_buffer_lookahead = stream.SyncFIFO(
            cmd_buffer_layout, self.settings.cmd_buffer_depth,
            buffered=self.settings.cmd_buffer_buffered)
        # 1 depth buffer to detect row change
        cmd_buffer = stream.Buffer(cmd_buffer_layout)
        m.submodules += cmd_buffer_lookahead, cmd_buffer
        m.d.comb += [
            cmd_buffer_lookahead.sink.valid.eq(self.req.valid),
            self.req.ready.eq(cmd_buffer_lookahead.sink.ready),
            cmd_buffer_lookahead.sink.payload.we.eq(self.req.we),
            cmd_buffer_lookahead.sink.payload.addr.eq(self.req.addr),

            cmd_buffer_lookahead.source.connect(cmd_buffer.sink),
            cmd_buffer.source.ready.eq(
                self.req.wdata_ready | self.req.rdata_valid),
            self.req.lock.eq(cmd_buffer_lookahead.source.valid |
                             cmd_buffer.source.valid),
        ]

        slicer = _AddressSlicer(
            self.settings.geom.colbits, self._address_align)

        # Row tracking -----------------------------------------------------------------------------
        row = Signal(self.settings.geom.rowbits)
        row_opened = Signal()
        row_hit = Signal()
        row_open = Signal()
        row_close = Signal()
        m.d.comb += row_hit.eq(row == slicer.row(cmd_buffer.source.addr))
        with m.If(row_close):
            m.d.sync += row_opened.eq(0)
        with m.Elif(row_open):
            m.d.sync += [
                row_opened.eq(1),
                row.eq(slicer.row(cmd_buffer.source.addr)),
            ]

        # Address generation -----------------------------------------------------------------------
        row_col_n_addr_sel = Signal()
        m.d.comb += self.cmd.ba.eq(self._n)
        with m.If(row_col_n_addr_sel):
            m.d.comb += self.cmd.a.eq(slicer.row(cmd_buffer.source.addr))
        with m.Else():
            m.d.comb += self.cmd.a.eq((auto_precharge << 10)
                                      | slicer.col(cmd_buffer.source.addr))

        # tWTP (write-to-precharge) controller -----------------------------------------------------
        write_latency = math.ceil(
            self.settings.phy.cwl / self.settings.phy.nphases)
        precharge_time = write_latency + self.settings.timing.tWR + \
            self.settings.timing.tCCD  # AL=0
        m.submodules.twtpcon = twtpcon = tXXDController(precharge_time)
        m.d.comb += twtpcon.valid.eq(self.cmd.valid &
                                     self.cmd.ready & self.cmd.is_write)

        # tRC (activate-activate) controller -------------------------------------------------------
        m.submodules.trccon = trccon = tXXDController(self.settings.timing.tRC)
        m.d.comb += trccon.valid.eq(self.cmd.valid & self.cmd.ready & row_open)

        # tRAS (activate-precharge) controller -----------------------------------------------------
        m.submodules.trascon = trascon = tXXDController(
            self.settings.timing.tRAS)
        m.d.comb += trascon.valid.eq(self.cmd.valid &
                                     self.cmd.ready & row_open)

        # Auto Precharge generation ----------------------------------------------------------------
        # generate auto precharge when current and next cmds are to different rows
        if self.settings.with_auto_precharge:
            with m.If(cmd_buffer_lookahead.source.valid & cmd_buffer.source.valid):
                with m.If(slicer.row(cmd_buffer_lookahead.source.addr) != slicer.row(cmd_buffer.source.addr)):
                    m.d.comb += auto_precharge.eq(row_close == 0)

        # Control and command generation FSM -------------------------------------------------------
        # Note: tRRD, tFAW, tCCD, tWTR timings are enforced by the multiplexer
        with m.FSM():
            with m.State("Regular"):
                with m.If(self.refresh_req):
                    m.next = "Refresh"
                with m.Elif(cmd_buffer.source.valid):
                    with m.If(row_opened):
                        with m.If(row_hit):
                            m.d.comb += [
                                self.cmd.valid.eq(1),
                                self.cmd.cas.eq(1),
                            ]
                            with m.If(cmd_buffer.source.we):
                                m.d.comb += [
                                    self.req.wdata_ready.eq(self.cmd.ready),
                                    self.cmd.is_write.eq(1),
                                    self.cmd.we.eq(1),
                                ]
                            with m.Else():
                                m.d.comb += [
                                    self.req.rdata_valid.eq(self.cmd.ready),
                                    self.cmd.is_read.eq(1),
                                ]
                            with m.If(self.cmd.ready & auto_precharge):
                                m.next = "Autoprecharge"
                        with m.Else():
                            m.next = "Precharge"
                    with m.Else():
                        m.next = "Activate"

            with m.State("Precharge"):
                m.d.comb += row_close.eq(1)

                with m.If(twtpcon.ready & trascon.ready):
                    m.d.comb += [
                        self.cmd.valid.eq(1),
                        self.cmd.ras.eq(1),
                        self.cmd.we.eq(1),
                        self.cmd.is_cmd.eq(1),
                    ]

                    with m.If(self.cmd.ready):
                        m.next = "tRP"

            with m.State("Autoprecharge"):
                m.d.comb += row_close.eq(1)

                with m.If(twtpcon.ready & trascon.ready):
                    m.next = "tRP"

            with m.State("Activate"):
                with m.If(trccon.ready):
                    m.d.comb += [
                        row_col_n_addr_sel.eq(1),
                        row_open.eq(1),
                        self.cmd.valid.eq(1),
                        self.cmd.is_cmd.eq(1),
                        self.cmd.ras.eq(1),
                    ]
                    with m.If(self.cmd.ready):
                        m.next = "tRCD"

            with m.State("Refresh"):
                m.d.comb += [
                    row_close.eq(1),
                    self.cmd.is_cmd.eq(1),
                ]

                with m.If(twtpcon.ready):
                    m.d.comb += self.refresh_gnt.eq(1)
                with m.If(~self.refresh_req):
                    m.next = "Regular"

            delayed_enter(m, "tRP", "Activate", self.settings.timing.tRP - 1)
            delayed_enter(m, "tRCD", "Regular", self.settings.timing.tRCD - 1)

        return m
