from nmigen import *

from gram.core.multiplexer import _AntiStarvation
from utils import *

class AntiStarvationTestCase(FHDLTestCase):
    def test_duration(self):
        def generic_test(timeout):
            m = Module()
            m.submodules = dut = _AntiStarvation(timeout)

            def process():
                yield dut.en.eq(1)
                yield
                yield dut.en.eq(0)
                yield

                for i in range(timeout):
                    self.assertFalse((yield dut.max_time))
                    yield

                self.assertTrue((yield dut.max_time))

            runSimulation(m, process, "test_core_multiplexer_antistarvation.vcd")

    def test_formal(self):
        def generic_test(timeout):
            dut = _AntiStarvation(timeout)
            self.assertFormal(dut, mode="bmc", depth=4)

        generic_test(0)
        #generic_test(1)
        generic_test(5)
        generic_test(10)
        generic_test(0x20)
