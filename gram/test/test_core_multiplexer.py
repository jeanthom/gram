from nmigen import *

from gram.core.multiplexer import _AntiStarvation
from utils import *

class AntiStarvationTestCase(FHDLTestCase):
    def test_formal(self):
        def generic_test(timeout):
            dut = _AntiStarvation(timeout)
            self.assertFormal(dut, mode="bmc", depth=4)

        generic_test(0)
        #generic_test(1)
        generic_test(5)
        generic_test(10)
