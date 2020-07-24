#nmigen: UnusedElaboratable=no
from nmigen import *
from nmigen.hdl.ast import Past

from gram.common import tXXDController, tFAWController
from utils import *

class tXXDControllerTestCase(FHDLTestCase):
    def test_formal(self):
        def generic_test(txxd):
            dut = tXXDController(txxd)
            self.assertFormal(dut, mode="bmc", depth=txxd+1 if txxd is not None else 10)

        generic_test(None)
        generic_test(0)
        generic_test(1)
        generic_test(5)
        generic_test(10)

class tFAWControllerTestCase(FHDLTestCase):
    def test_strobe_3(self):
        dut = tFAWController(10)
        def process():
            yield dut.valid.eq(1)
            
            for i in range(3):
                self.assertTrue((yield dut.ready))
                yield

            yield dut.valid.eq(0)
            yield

            self.assertFalse((yield dut.valid))

        runSimulation(dut, process, "test_common.vcd")
