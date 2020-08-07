#nmigen: UnusedElaboratable=no
import types, math

from nmigen import *
from nmigen.asserts import Assert, Assume

from gram.core.bankmachine import _AddressSlicer, BankMachine
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

class BankMachineRequestGrantSpec(Elaboratable):
    def __init__(self, dut):
        self.dut = dut

    def elaborate(self, platform):
        m = Module()
        m.d.comb += Assume(~dut.request_req)
        m.d.comb += Assert(~dut.request_gnt)
        return m

class BankMachineTestCase(FHDLTestCase):
    settings = types.SimpleNamespace()
    settings.cmd_buffer_depth = 1
    settings.cmd_buffer_buffered = False
    settings.with_auto_precharge = False
    settings.geom = types.SimpleNamespace()
    settings.geom.addressbits = 20
    settings.geom.colbits = 8
    settings.geom.rowbits = 12
    settings.geom.bankbits = 3
    settings.timing = types.SimpleNamespace()
    settings.timing.tWR = 5
    settings.timing.tCCD = 4
    settings.timing.tRC = 6
    settings.timing.tRAS = 7
    settings.timing.tRP = 10
    settings.timing.tRCD = 8
    settings.phy = types.SimpleNamespace()
    settings.phy.cwl = 6
    settings.phy.nphases = 2

    def test_no_request_grant(self):
        dut = BankMachine(0, 20, 2, 1, self.settings)
        self.assertFormal(dut, "bmc", depth=21)
