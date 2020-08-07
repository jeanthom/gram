#nmigen: UnusedElaboratable=no
from nmigen import *
from nmigen.asserts import Assert, Assume

from gram.core.bankmachine import _AddressSlicer
from gram.test.utils import *

class AddressSlicerBijectionSpec(Elaboratable):
    def __init__(self, dut1, dut2):
        self.dut1 = dut1
        self.dut2 = dut2

    def elaborate(self, platform):
        m = Module()
        m.submodules.dut1 = dut1 = self.dut1
        m.submodules.dut2 = dut2 = self.dut2

        m.d.comb += Assert((dut1.address != dut2.address) == (Cat(dut1.row, dut1.col) != Cat(dut2.row, dut2.col)))
        return m

class AddressSlicerTestCase(FHDLTestCase):
    addrbits = 12
    colbits = 5
    address_align = 1

    def test_parameters(self):
        dut = _AddressSlicer(self.addrbits, self.colbits, self.address_align)
        self.assertEqual(dut.col.width, self.colbits)
        self.assertEqual(dut.address.width, self.addrbits)

    def test_bijection(self):
        dut1 = _AddressSlicer(self.addrbits, self.colbits, self.address_align)
        dut2 = _AddressSlicer(self.addrbits, self.colbits, self.address_align)
        spec = AddressSlicerBijectionSpec(dut1, dut2)
        self.assertFormal(spec, "bmc", depth=1)
