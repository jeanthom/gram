from nmigen import *
from nmigen.hdl.ast import Past

from gram.common import DQSPattern
from utils import *

class DQSPatternTestCase(FHDLTestCase):
    def test_async(self):
        m = Module()
        m.d.sync += Signal().eq(0) # Workaround for nMigen#417
        m.submodules.dut = dut = DQSPattern(register=False)

        def process():
            yield dut.preamble.eq(1) # Preamble=1, Postamble=0
            yield
            self.assertEqual((yield dut.o), 0b00010101)

            yield dut.postamble.eq(1) # Preamble=1, Postamble=1
            yield
            self.assertEqual((yield dut.o), 0b00010101)

            yield dut.preamble.eq(0) # Preamble=0, Postamble=1
            yield
            self.assertEqual((yield dut.o), 0b01010100)

            yield dut.postamble.eq(0) # Preamble=1, Postamble=1
            yield
            self.assertEqual((yield dut.o), 0b01010101)

        runSimulation(m, process, "test_dqspattern_async.vcd")
