# This file is Copyright (c) 2020 LambdaConcept <contact@lambdaconcept.com>

import unittest

from nmigen import *
from nmigen import tracer
from nmigen.compat import Case
from nmigen.back.pysim import *

__ALL__ = ["delayed_enter", "Timeline", "CSRPrefixProxy"]


def delayed_enter(m, src, dst, delay):
    assert delay > 0

    for i in range(delay):
        if i == 0:
            statename = src
        else:
            statename = "{}-{}".format(src, i)

        if i == delay-1:
            deststate = dst
        else:
            deststate = "{}-{}".format(src, i+1)

        with m.State(statename):
            m.next = deststate


class Timeline(Elaboratable):
    def __init__(self, events):
        self.trigger = Signal()
        self._events = events

    def elaborate(self, platform):
        m = Module()

        lastevent = max([e[0] for e in self._events])
        counter = Signal(range(lastevent+1))

        # Counter incrementation
        # (with overflow handling)
        if (lastevent & (lastevent + 1)) != 0:
            with m.If(counter == lastevent):
                m.d.sync += counter.eq(0)
            with m.Else():
                with m.If(counter != 0):
                    m.d.sync += counter.eq(counter+1)
                with m.Elif(self.trigger):
                    m.d.sync += counter.eq(1)
        else:
            with m.If(counter != 0):
                m.d.sync += counter.eq(counter+1)
            with m.Elif(self.trigger):
                m.d.sync += counter.eq(1)

        for e in self._events:
            if e[0] == 0:
                with m.If(self.trigger & (counter == 0)):
                    m.d.sync += e[1]
            else:
                with m.If(counter == e[0]):
                    m.d.sync += e[1]

        return m


class CSRPrefixProxy:
    def __init__(self, bank, prefix):
        self._bank = bank
        self._prefix = prefix

    def csr(self, width, access, *, addr=None, alignment=None, name=None,
            src_loc_at=0):
        if name is not None and not isinstance(name, str):
            raise TypeError("Name must be a string, not {!r}".format(name))
        name = name or tracer.get_var_name(depth=2 + src_loc_at).lstrip("_")

        prefixed_name = "{}_{}".format(self._prefix, name)
        return self._bank.csr(width=width, access=access, addr=addr,
                              alignment=alignment, name=prefixed_name)
