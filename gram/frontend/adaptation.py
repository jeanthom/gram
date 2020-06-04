# This file is Copyright (c) 2016-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

from nmigen import *
from nmigen.compat import Case

from gram.common import *
import gram.stream as stream

# LiteDRAMNativePortCDC ----------------------------------------------------------------------------

class gramNativePortCDC(Elaboratable):
    def __init__(self, port_from, port_to,
                 cmd_depth   = 4,
                 wdata_depth = 16,
                 rdata_depth = 16):
        assert port_from.address_width == port_to.address_width
        assert port_from.data_width    == port_to.data_width
        assert port_from.mode          == port_to.mode

        self._port_from = port_from
        self._port_to = port_to
        self._cmd_depth = cmd_depth
        self._wdata_depth = wdata_depth
        self._rdata_depth = rdata_depth

    def elaborate(self, platform):
        m = Module()

        port_from = self._port_from
        port_to = self._port_to
        cmd_depth = self._cmd_depth
        wdata_depth = self._wdata_depth
        rdata_depth = self._rdata_depth

        address_width = port_from.address_width
        data_width = port_from.data_width
        mode = port_from.mode
        clock_domain_from = port_from.clock_domain
        clock_domain_to = port_to.clock_domain

        cmd_fifo = stream.AsyncFIFO(
            [("we", 1), ("addr", address_width)], cmd_depth)
        cmd_fifo = ClockDomainsRenamer(
            {"write": clock_domain_from,
             "read":  clock_domain_to})(cmd_fifo)
        m.submodules += cmd_fifo
        m.submodules += stream.Pipeline(
            port_from.cmd, cmd_fifo, port_to.cmd)

        if mode == "write" or mode == "both":
            wdata_fifo = stream.AsyncFIFO(
                [("data", data_width), ("we", data_width//8)], wdata_depth)
            wdata_fifo = ClockDomainsRenamer(
                {"write": clock_domain_from,
                 "read":  clock_domain_to})(wdata_fifo)
            m.submodules += wdata_fifo
            m.submodules += stream.Pipeline(
                port_from.wdata, wdata_fifo, port_to.wdata)

        if mode == "read" or mode == "both":
            rdata_fifo = stream.AsyncFIFO([("data", data_width)], rdata_depth)
            rdata_fifo = ClockDomainsRenamer(
                {"write": clock_domain_to,
                 "read":  clock_domain_from})(rdata_fifo)
            m.submodules += rdata_fifo
            m.submodules += stream.Pipeline(
                port_to.rdata, rdata_fifo, port_from.rdata)

        return m

# LiteDRAMNativePortDownConverter ------------------------------------------------------------------

class gramNativePortDownConverter(Elaboratable):
    """LiteDRAM port DownConverter

    This module reduces user port data width to fit controller data width.
    With N = port_from.data_width/port_to.data_width:
    - Address is adapted (multiplied by N + internal increments)
    - A write from the user is splitted and generates N writes to the
    controller.
    - A read from the user generates N reads to the controller and returned
      datas are regrouped in a single data presented to the user.
    """
    def __init__(self, port_from, port_to, reverse=False):
        assert port_from.clock_domain == port_to.clock_domain
        assert port_from.data_width    > port_to.data_width
        assert port_from.mode         == port_to.mode
        if port_from.data_width % port_to.data_width:
            raise ValueError("Ratio must be an int")

        self._port_from = port_from
        self._port_to = port_to
        self._reverse = reverse

    def elaborate(self, platform):
        m = Module()

        port_from = self._port_from
        port_to = self._port_to
        reverse = self._reverse

        ratio = port_from.data_width//port_to.data_width
        mode  = port_from.mode

        counter       = Signal(max=ratio)
        counter_reset = Signal()
        counter_ce    = Signal()

        with m.If(counter_reset):
            m.d.sync += counter.eq(0)
        with m.Elif(counter_ce):
            m.d.sync += counter.eq(counter+1)

        with m.FSM():
            with m.State("Idle"):
                m.d.comb += counter_reset.eq(1)
                with m.If(port_from.cmd.valid):
                    m.next = "Convert"

            with m.State("Convert"):
                m.d.comb += [
                    port_to.cmd.valid.eq(1),
                    port_to.cmd.we.eq(port_from.cmd.we),
                    port_to.cmd.addr.eq(port_from.cmd.addr*ratio + counter),
                ]
                with m.If(port_to.cmd.ready):
                    m.d.comb += counter_ce.eq(1)
                    with m.If(counter == ratio - 1):
                        m.d.comb += port_from.cmd.ready.eq(1)
                        m.next = "Idle"

        if mode == "write" or mode == "both":
            wdata_converter = stream.StrideConverter(
                port_from.wdata.description,
                port_to.wdata.description,
                reverse=reverse)
            m.submodules += wdata_converter
            m.submodules += stream.Pipeline(
                port_from.wdata, wdata_converter, port_to.wdata)

        if mode == "read" or mode == "both":
            rdata_converter = stream.StrideConverter(
                port_to.rdata.description,
                port_from.rdata.description,
                reverse=reverse)
            m.submodules += rdata_converter
            m.submodules += stream.Pipeline(
                port_to.rdata, rdata_converter, port_from.rdata)

        return m

# LiteDRAMNativeWritePortUpConverter ---------------------------------------------------------------

class gramNativeWritePortUpConverter(Elaboratable):
    # TODO: finish and remove hack
    """LiteDRAM write port UpConverter

    This module increase user port data width to fit controller data width.
    With N = port_to.data_width/port_from.data_width:
    - Address is adapted (divided by N)
    - N writes from user are regrouped in a single one to the controller
    (when possible, ie when consecutive and bursting)
    """
    def __init__(self, port_from, port_to, reverse=False):
        assert port_from.clock_domain == port_to.clock_domain
        assert port_from.data_width    < port_to.data_width
        assert port_from.mode         == port_to.mode
        assert port_from.mode         == "write"
        if port_to.data_width % port_from.data_width:
            raise ValueError("Ratio must be an int")

        self._port_from = port_from
        self._port_to = port_to
        self._reverse = reverse

    def elaborate(self, platform):
        m = Module()

        port_from = self._port_from
        port_to = self._port_to
        reverse = self._reverse

        ratio = port_to.data_width//port_from.data_width

        we      = Signal()
        address = Signal(port_to.address_width)

        counter       = Signal(max=ratio)
        counter_reset = Signal()
        counter_ce    = Signal()
        self.sync += \
            If(counter_reset,
                counter.eq(0)
            ).Elif(counter_ce,
                counter.eq(counter + 1)
            )

        with m.FSM():
            with m.State("Idle"):
                m.d.comb += port_from.cmd.ready.eq(1)
                with m.If(port_from.cmd.valid):
                    m.d.sync += [
                        we.eq(port_from.cmd.we),
                        address.eq(port_from.cmd.addr),
                    ]
                    m.next = "Receive"

            with m.State("Receive"):
                m.d.comb += port_from.cmd.ready.eq(1)
                with m.If(port_from.cmd.valid):
                    m.d.comb += counter_ce.eq(1)
                    with m.If(counter == ratio-1):
                        m.next = "Generate"

            with m.State("Generate"):
                m.d.comb += [
                    port_to.cmd.valid.eq(1),
                    port_to.cmd.we.eq(we),
                    port_to.cmd.addr.eq(address[log2_int(ratio):]),
                ]
                with m.If(port_to.cmd.ready):
                    m.next = "Idle"

        wdata_converter = stream.StrideConverter(
            port_from.wdata.description,
            port_to.wdata.description,
            reverse=reverse)
        m.submodules += wdata_converter
        m.submodules += stream.Pipeline(
            port_from.wdata,
            wdata_converter,
            port_to.wdata)

        return m

# LiteDRAMNativeReadPortUpConverter ----------------------------------------------------------------

class gramNativeReadPortUpConverter(Elaboratable):
    """LiteDRAM port UpConverter

    This module increase user port data width to fit controller data width.
    With N = port_to.data_width/port_from.data_width:
    - Address is adapted (divided by N)
    - N read from user are regrouped in a single one to the controller
    (when possible, ie when consecutive and bursting)
    """
    def __init__(self, port_from, port_to, reverse=False):
        assert port_from.clock_domain == port_to.clock_domain
        assert port_from.data_width    < port_to.data_width
        assert port_from.mode         == port_to.mode
        assert port_from.mode         == "read"
        if port_to.data_width % port_from.data_width:
            raise ValueError("Ratio must be an int")

        self._port_from = port_from
        self._port_to = port_to
        self._reverse = reverse

    def elaborate(self, platform):
        m = Module()

        port_from = self._port_from
        port_to = self._port_to
        reverse = self._reverse

        ratio = port_to.data_width//port_from.data_width

        # Command ----------------------------------------------------------------------------------

        cmd_buffer = stream.SyncFIFO([("sel", ratio)], 4)
        m.submodules += cmd_buffer

        counter = Signal(range(ratio))
        counter_ce = Signal()
        with m.If(counter_ce):
            m.d.sync += counter.eq(counter+1)

        with m.If(port_from.cmd.valid):
            with m.If(counter == 0):
                m.d.comb += [
                    port_to.cmd.valid.eq(1),
                    port_to.cmd.addr.eq(port_from.cmd.addr[log2_int(ratio):]),
                    port_from.cmd.ready.eq(port_to.cmd.ready),
                    counter_ce.eq(port_to.cmd.ready),
                ]
            with m.Else():
                m.d.comb += [
                    port_from.cmd.ready.eq(1),
                    counter_ce.eq(1),
                ]

        # TODO: fix sel
        with m.If(port_to.cmd.valid & port_to.cmd.ready):
            m.d.comb += [
                cmd_buffer.sink.valid.eq(1),
                cmd_buffer.sink.sel.eq(2**ratio-1),
            ]

        # Datapath ---------------------------------------------------------------------------------

        rdata_buffer    = stream.Buffer(port_to.rdata.description)
        rdata_converter = stream.StrideConverter(
            port_to.rdata.description,
            port_from.rdata.description,
            reverse=reverse)
        m.submodules +=  rdata_buffer, rdata_converter

        rdata_chunk       = Signal(ratio, reset=1)
        rdata_chunk_valid = Signal()
        with m.If(rdata_converter.source.valid & rdata_converter.source.ready):
            m.d.sync += rdata_chunk.eq(Cat(rdata_chunk[ratio-1], rdata_chunk[:ratio-1]))

        m.d.comb += [
            port_to.rdata.connect(rdata_buffer.sink),
            rdata_buffer.source.connect(rdata_converter.sink),
            rdata_chunk_valid.eq((cmd_buffer.source.sel & rdata_chunk) != 0),
            cmd_buffer.source.ready.eq(rdata_converter.source.ready & rdata_chunk[ratio-1]),
        ]

        with m.If(port_from.flush):
            m.d.comb += rdata_converter.source.ready.eq(1)
        with m.Elif(cmd_buffer.source.valid):
            with m.If(rdata_chunk_valid):
                m.d.comb += [
                    port_from.rdata.valid.eq(rdata_converter.source.valid),
                    port_from.rdata.data.eq(rdata_converter.source.data),
                    rdata_converter.source.ready.eq(port_from.rdata.ready),
                ]
            with m.Else():
                m.d.comb += rdata_converter.source.ready.eq(1)

        return m

# LiteDRAMNativePortConverter ----------------------------------------------------------------------

class LiteDRAMNativePortConverter(Elaboratable):
    def __init__(self, port_from, port_to, reverse=False):
        assert port_from.clock_domain == port_to.clock_domain
        assert port_from.mode         == port_to.mode

        self._port_from = port_from
        self._port_to = port_to
        self._reverse = reverse

    def elaborate(self, platform):
        m = Module()

        port_from = self._port_from
        port_to = self._port_to
        reverse = self._reverse

        mode = port_from.mode

        if port_from.data_width > port_to.data_width:
            converter = gramNativePortDownConverter(port_from, port_to, reverse)
            m.submodules += converter
        elif port_from.data_width < port_to.data_width:
            if mode == "write":
                converter = gramNativeWritePortUpConverter(port_from, port_to, reverse)
            elif mode == "read":
                converter = gramNativeReadPortUpConverter(port_from, port_to, reverse)
            else:
                raise NotImplementedError
            m.submodules += converter
        else:
            m.d.comb += [
                port_from.cmd.connect(port_to.cmd),
                port_from.wdata.connect(port_to.wdata),
                port_to.rdata.connect(port_from.rdata)
            ]

        return m
