#nmigen: UnusedElaboratable=no
from nmigen import *
from nmigen.hdl.ast import Past

from gram.common import DQSPattern, tXXDController
from utils import *

class tXXDControllerTestCase(FHDLTestCase):
    def test_formal(self):
        def generic_test(txxd):
            dut = tXXDController(txxd)
            self.assertFormal(dut, mode="bmc", depth=4)

        generic_test(None)
        generic_test(0)
        generic_test(1)
        generic_test(5)
        generic_test(10)