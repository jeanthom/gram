# This file is Copyright (c) 2020 LambdaConcept <contact@lambdaconcept.com>

from nmigen import *
from nmigen.hdl.rec import *
from nmigen.lib import fifo


__all__ = ["Endpoint", "SyncFIFO", "AsyncFIFO", "Buffer", "StrideConverter"]


def _make_fanout(layout):
    r = []
    for f in layout:
        if isinstance(f[1], (int, tuple)):
            r.append((f[0], f[1], DIR_FANOUT))
        else:
            r.append((f[0], _make_fanout(f[1])))
    return r


class EndpointDescription:
    def __init__(self, payload_layout):
        self.payload_layout = payload_layout

    def get_full_layout(self):
        reserved = {"valid", "ready", "first", "last", "payload"}
        attributed = set()
        for f in self.payload_layout:
            if f[0] in attributed:
                raise ValueError(
                    f[0] + " already attributed in payload layout")
            if f[0] in reserved:
                raise ValueError(f[0] + " cannot be used in endpoint layout")
            attributed.add(f[0])

        full_layout = [
            ("valid", 1, DIR_FANOUT),
            ("ready", 1, DIR_FANIN),
            ("first", 1, DIR_FANOUT),
            ("last",  1, DIR_FANOUT),
            ("payload", _make_fanout(self.payload_layout))
        ]
        return full_layout


class Endpoint(Record):
    def __init__(self, layout_or_description, **kwargs):
        if isinstance(layout_or_description, EndpointDescription):
            self.description = layout_or_description
        else:
            self.description = EndpointDescription(layout_or_description)
        super().__init__(self.description.get_full_layout(), src_loc_at=1, **kwargs)

    def __getattr__(self, name):
        try:
            return super().__getattr__(name)
        except AttributeError:
            return self.fields["payload"][name]


class _FIFOWrapper:
    def __init__(self, payload_layout):
        self.sink = Endpoint(payload_layout)
        self.source = Endpoint(payload_layout)

        self.layout = Layout([
            ("payload", self.sink.description.payload_layout),
            ("first",   1, DIR_FANOUT),
            ("last",    1, DIR_FANOUT)
        ])

    def elaborate(self, platform):
        m = Module()

        fifo = m.submodules.fifo = self.fifo
        fifo_din = Record(self.layout)
        fifo_dout = Record(self.layout)
        m.d.comb += [
            fifo.w_data.eq(fifo_din),
            fifo_dout.eq(fifo.r_data),

            self.sink.ready.eq(fifo.w_rdy),
            fifo.w_en.eq(self.sink.valid),
            fifo_din.first.eq(self.sink.first),
            fifo_din.last.eq(self.sink.last),
            fifo_din.payload.eq(self.sink.payload),

            self.source.valid.eq(fifo.r_rdy),
            self.source.first.eq(fifo_dout.first),
            self.source.last.eq(fifo_dout.last),
            self.source.payload.eq(fifo_dout.payload),
            fifo.r_en.eq(self.source.ready)
        ]

        return m


class SyncFIFO(Elaboratable, _FIFOWrapper):
    def __init__(self, layout, depth, fwft=True, buffered=False):
        super().__init__(layout)
        if buffered:
            self.fifo = fifo.SyncFIFOBuffered(
                width=len(Record(self.layout)), depth=depth, fwft=fwft)
        else:
            self.fifo = fifo.SyncFIFO(
                width=len(Record(self.layout)), depth=depth, fwft=fwft)
        self.depth = self.fifo.depth
        self.level = self.fifo.level


class AsyncFIFO(Elaboratable, _FIFOWrapper):
    def __init__(self, layout, depth, r_domain="read", w_domain="write"):
        super().__init__(layout)
        self.fifo = fifo.AsyncFIFO(width=len(Record(self.layout)), depth=depth,
                                   r_domain=r_domain, w_domain=w_domain)
        self.depth = self.fifo.depth


class PipeValid(Elaboratable):
    """Pipe valid/payload to cut timing path"""

    def __init__(self, layout):
        self.sink = Endpoint(layout)
        self.source = Endpoint(layout)

    def elaborate(self, platform):
        m = Module()

        # Pipe when source is not valid or is ready.
        with m.If(~self.source.valid | self.source.ready):
            m.d.sync += [
                self.source.valid.eq(self.sink.valid),
                self.source.first.eq(self.sink.first),
                self.source.last.eq(self.sink.last),
                self.source.payload.eq(self.sink.payload),
                # self.source.param.eq(self.sink.param), # TODO ensure this can be commented
            ]
        m.d.comb += self.sink.ready.eq(~self.source.valid | self.source.ready)

        return m


class Buffer(PipeValid):
    pass  # FIXME: Replace Buffer with PipeValid in codebase?


class _UpConverter(Elaboratable):
    def __init__(self, nbits_from, nbits_to, ratio, reverse,
                 report_valid_token_count):
        self.sink = sink = Endpoint([("data", nbits_from)])
        source_layout = [("data", nbits_to)]
        if report_valid_token_count:
            source_layout.append(("valid_token_count", bits_for(ratio)))
        self.source = source = Endpoint(source_layout)
        self.ratio = ratio
        self._nbits_from  = nbits_from

    def elaborate(self, platform):
        m = Module()

        # control path
        demux = Signal(max=ratio)
        load_part = Signal()
        strobe_all = Signal()
        m.d.comb += [
            self.sink.ack.eq(~strobe_all | self.source.ack),
            self.source.stb.eq(strobe_all),
            load_part.eq(self.sink.stb & self.sink.ack)
        ]

        demux_last = ((demux == (ratio - 1)) | self.sink.eop)

        with m.If(source.ack):
            m.d.sync += strobe_all.eq(0)

        with m.If(load_part):
            with m.If(demux_last):
                m.d.sync += [
                    demux.eq(0),
                    strobe_all.eq(1),
                ]
            with m.Else():
                m.d.sync += demux.eq(demux+1)

        with m.If(self.source.stb & self.source.ack):
            m.d.sync += self.source.eop.eq(self.sink.eop)
        with m.Elif(self.sink.stb & self.sink.ack):
            m.d.sync += self.source.eop.eq(self.sink.eop | self.source.eop)

        # data path
        cases = {}
        for i in range(ratio):
            n = ratio-i-1 if reverse else i
            cases[i] = source.data[n*self._nbits_from:(n+1)*self._nbits_from].eq(sink.data)
        m.d.sync += If(load_part, Case(demux, cases))

        if report_valid_token_count:
            with m.If(load_part):
                m.d.sync += self.source.valid_token_count.eq(demux + 1)

        return m


class _DownConverter(Elaboratable):
    def __init__(self, nbits_from, nbits_to, ratio, reverse,
                 report_valid_token_count):
        self.sink = sink = Endpoint([("data", nbits_from)])
        source_layout = [("data", nbits_to)]
        if report_valid_token_count:
            source_layout.append(("valid_token_count", 1))
        self.source = source = Endpoint(source_layout)
        self.ratio = ratio

    def elaborate(self, platform):
        m = Module()

        # control path
        mux = Signal(range(self.ratio))
        last = Signal()
        m.d.comb += [
            last.eq(mux == (self.ratio-1)),
            self.source.stb.eq(self.sink.stb),
            self.source.eop.eq(sink.eop & last),
            self.sink.ack.eq(last & self.source.ack)
        ]
        with m.If(self.source.stb & self.source.ack):
            with m.If(last):
                m.d.sync += mux.eq(0)
            with m.Else():
                m.d.sync += mux.eq(mux+1)

        # data path
        cases = {}
        for i in range(ratio):
            n = ratio-i-1 if reverse else i
            cases[i] = self.source.data.eq(self.sink.data[n*nbits_to:(n+1)*nbits_to])
        m.d.comb += Case(mux, cases).makedefault()

        if report_valid_token_count:
            m.d.comb += self.source.valid_token_count.eq(last)

        return m


class _IdentityConverter(Elaboratable):
    def __init__(self, nbits_from, nbits_to, ratio, reverse,
                 report_valid_token_count):
        self.sink = Endpoint([("data", nbits_from)])
        source_layout = [("data", nbits_to)]
        if report_valid_token_count:
            source_layout.append(("valid_token_count", 1))
        self.source = Endpoint(source_layout)
        assert ratio == 1
        self.ratio = ratio
        self._report_valid_token_count = report_valid_token_count

    def elaborate(self, platform):
        m = Module()

        m.d.comb += self.sink.connect(self.source)
        if self._report_valid_token_count:
            m.d.comb += self.source.valid_token_count.eq(1)

        return m


def _get_converter_ratio(nbits_from, nbits_to):
    if nbits_from > nbits_to:
        specialized_cls = _DownConverter
        if nbits_from % nbits_to:
            raise ValueError("Ratio must be an int")
        ratio = nbits_from//nbits_to
    elif nbits_from < nbits_to:
        specialized_cls = _UpConverter
        if nbits_to % nbits_from:
            raise ValueError("Ratio must be an int")
        ratio = nbits_to//nbits_from
    else:
        specialized_cls = _IdentityConverter
        ratio = 1

    return specialized_cls, ratio


class Converter(Elaboratable):
    def __init__(self, nbits_from, nbits_to, reverse=False,
                 report_valid_token_count=False):
        cls, ratio = _get_converter_ratio(nbits_from, nbits_to)
        self.specialized,_ = cls(nbits_from, nbits_to, ratio,
            reverse, report_valid_token_count)
        self.sink = self.specialized.sink
        self.source = self.specialized.source

    def elaborate(self, platform):
        m = Module()

        m.submodules += self.specialized

        return m


class StrideConverter(Elaboratable):
    def __init__(self, layout_from, layout_to, *args, **kwargs):
        self.sink = sink = Endpoint(layout_from)
        self.source = source = Endpoint(layout_to)

        nbits_from = len(sink.payload.lower())
        nbits_to = len(source.payload.lower())
        self.converter = Converter(nbits_from, nbits_to, *args, **kwargs)

    def elaborate(self, platform):
        m = Module()

        nbits_from = len(self.sink.payload.lower())
        nbits_to = len(self.source.payload.lower())
        
        m.d.submodules += self.converter

        # cast sink to converter.sink (user fields --> raw bits)
        m.d.comb += [
            self.converter.sink.stb.eq(self.sink.stb),
            self.converter.sink.eop.eq(self.sink.eop),
            sink.ack.eq(self.converter.sink.ack)
        ]
        if isinstance(self.converter.specialized, _DownConverter):
            ratio = self.converter.specialized.ratio
            for i in range(ratio):
                j = 0
                for name, width in layout_to:
                    src = getattr(self.sink, name)[i*width:(i+1)*width]
                    dst = self.converter.sink.data[i*nbits_to+j:i*nbits_to+j+width]
                    m.d.comb += dst.eq(src)
                    j += width
        else:
            m.d.comb += self.converter.sink.data.eq(self.sink.payload.lower())


        # cast converter.source to source (raw bits --> user fields)
        m.d.comb += [
            self.source.stb.eq(self.converter.source.stb),
            self.source.eop.eq(self.converter.source.eop),
            self.converter.source.ack.eq(self.source.ack)
        ]
        if isinstance(self.converter.specialized, _UpConverter):
            ratio = self.converter.specialized.ratio
            for i in range(ratio):
                j = 0
                for name, width in layout_from:
                    src = self.converter.source.data[i*nbits_from+j:i*nbits_from+j+width]
                    dst = getattr(self.source, name)[i*width:(i+1)*width]
                    m.d.comb += dst.eq(src)
                    j += width
        else:
            m.d.comb += self.source.payload.lower().eq(self.converter.source.data)

        return m

class Pipeline(Elaboratable):
    def __init__(self, *modules):
        self._modules = modules

        # expose sink of first module
        # if available
        if hasattr(modules[0], "sink"):
            self.sink = modules[0].sink

        # expose source of last module
        # if available
        if hasattr(modules[-1], "source"):
            self.source = modules[-1].source

    def elaborate(self, platform):
        m = Module()

        n = len(modules)
        mod = modules[0]
        
        for i in range(1, n):
            mod_n = self._modules[i]
            if isinstance(mod, Endpoint):
                source = mod
            else:
                source = mod.source
            if isinstance(m_n, Endpoint):
                sink = mod_n
            else:
                sink = mod_n.sink
            if mod is not mod_n:
                m.d.comb += source.connect(sink)
            mod = mod_n

        return m
