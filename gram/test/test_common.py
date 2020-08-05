#nmigen: UnusedElaboratable=no
from nmigen import *
from nmigen.hdl.ast import Past

from gram.common import tXXDController, tFAWController
from gram.test.utils import *

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

    def test_delay(self):
        def generic_test(txxd):
            dut = tXXDController(txxd)

            yield dut.valid.eq(1)
            yield; yield Delay(1e-8)
            self.assertFalse((yield dut.ready))

            yield dut.valid.eq(0)

            for i in range(txxd):
                self.assertFalse((yield dut.ready))
                yield

            self.assertTrue((yield dut.ready))

            runSimulation(dut, process, "test_common_txxdcontroller.vcd")

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
