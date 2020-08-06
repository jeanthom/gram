from nmigen import *

from gram.phy.ecp5ddrphy import _DQSBUFMSettingManager
from gram.test.utils import *

class DQSBUFMSettingManagerTestCase(FHDLTestCase):
    class MockCSR:
        def __init__(self):
            self.w_stb = Signal()
            self.w_data = Signal(3)

    def test_pause_timing(self):
        csr = self.MockCSR()
        dut = _DQSBUFMSettingManager(csr)

        def process():
            self.assertFalse((yield dut.pause))

            yield csr.w_stb.eq(1)
            yield
            yield csr.w_stb.eq(0)
            yield

            self.assertTrue((yield dut.pause))
            yield
            self.assertTrue((yield dut.pause))
            yield
            self.assertFalse((yield dut.pause))

        runSimulation(dut, process, "test_phy_ecp5ddrphy.vcd")

    def test_value(self):
        csr = self.MockCSR()
        dut = _DQSBUFMSettingManager(csr)

        def process():
            # Check default value
            self.assertEqual((yield dut.readclksel), 0)

            yield csr.w_data.eq(0b101)
            yield csr.w_stb.eq(1)
            yield
            yield csr.w_stb.eq(0)
            yield 

            # Ensure value isn't being changed at that point
            self.assertEqual((yield dut.readclksel), 0)
            yield; yield Delay(1e-9)

            # Ensure value is changed after the second clock cycle
            self.assertEqual((yield dut.readclksel), 0b101)

        runSimulation(dut, process, "test_phy_ecp5ddrphy.vcd")
