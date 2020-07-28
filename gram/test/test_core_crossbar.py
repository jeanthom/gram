from nmigen import *
from nmigen.hdl.ast import Sample
from nmigen.asserts import Assert, Assume

from gram.core.crossbar import _DelayLine
from utils import *

class DelayLineSpec(Elaboratable):
    def __init__(self, delay):
        self.delay = delay

    def elaborate(self, platform):
        m = Module()

        m.submodules.dut = dut = _DelayLine(self.delay)
        m.d.comb += Assume(~ResetSignal("sync"))
        m.d.comb += Assert(dut.o == Sample(expr=dut.i, clocks=self.delay, domain="sync"))

        return m

class DelayLineTestCase(FHDLTestCase):
    def test_delay_one(self):
        spec = DelayLineSpec(1)
        self.assertFormal(spec, depth=2)

    def test_delay_many(self):
        spec = DelayLineSpec(10)
        self.assertFormal(spec, depth=11)
