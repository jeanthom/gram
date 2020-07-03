from nmigen import *
from lambdasoc.periph import Peripheral

from gram.dfii import *
from gram.phy.dfi import Interface
from utils import *

# Phase injector CSR addresses
PI_COMMAND_ADDR = 0x00
PI_COMMAND_ISSUE_ADDR = 0x04
PI_ADDRESS_ADDR = 0x08
PI_BADDRESS_ADDR = 0x0C
PI_WRDATA_ADDR = 0x10
PI_RDDATA_ADDR = 0x14

# DFI injector CSR addresses
DFII_CONTROL_ADDR = 0x00

class CSRHost(Peripheral, Elaboratable):
    def __init__(self, name="csrhost"):
        super().__init__(name=name)
        self.bank = self.csr_bank()

    def init_bridge(self):
        self._bridge = self.bridge(data_width=32, granularity=8, alignment=2)
        self.bus = self._bridge.bus

    def elaborate(self, platform):
        m = Module()
        m.submodules += self._bridge
        return m

class PhaseInjectorTestCase(FHDLTestCase):
    def generate_phaseinjector(self):
        dfi = Interface(12, 8, 1, 8, 1)
        csrhost = CSRHost()
        dut = PhaseInjector(csrhost.bank, dfi.phases[0])
        csrhost.init_bridge()
        m = Module()
        m.submodules += csrhost
        m.submodules += dut

        return (m, dfi, csrhost)

    def test_initialstate(self):
        m, dfi, csrhost = self.generate_phaseinjector()

        def process():
            self.assertTrue((yield dfi.phases[0].cas_n))
            self.assertTrue((yield dfi.phases[0].ras_n))
            self.assertTrue((yield dfi.phases[0].we_n))
            self.assertTrue((yield dfi.phases[0].act_n))
            self.assertFalse((yield dfi.phases[0].wrdata_mask))
            self.assertFalse((yield dfi.phases[0].rddata_en))
            self.assertFalse((yield dfi.phases[0].wrdata_en))

        runSimulation(m, process, "test_phaseinjector.vcd")

    def test_setaddress(self):
        m, dfi, csrhost = self.generate_phaseinjector()

        def process():
            yield from wb_write(csrhost.bus, PI_ADDRESS_ADDR >> 2, 0xCDC, sel=0xF)
            self.assertEqual((yield dfi.phases[0].address), 0xCDC)

        runSimulation(m, process, "test_phaseinjector.vcd")

    def test_setbankaddress(self):
        m, dfi, csrhost = self.generate_phaseinjector()

        def process():
            yield from wb_write(csrhost.bus, PI_BADDRESS_ADDR >> 2, 0xA8, sel=0xF)
            self.assertEqual((yield dfi.phases[0].bank), 0xA8)

        runSimulation(m, process, "test_phaseinjector.vcd")

    def test_setwrdata(self):
        m, dfi, csrhost = self.generate_phaseinjector()

        def process():
            yield from wb_write(csrhost.bus, PI_WRDATA_ADDR >> 2, 0xCC, sel=0xF)
            self.assertEqual((yield dfi.phases[0].wrdata), 0xCC)

        runSimulation(m, process, "test_phaseinjector.vcd")

    def test_wrdata_en(self):
        m, dfi, csrhost = self.generate_phaseinjector()

        m.submodules.pc = pc = PulseCounter()
        m.d.comb += pc.i.eq(dfi.phases[0].wrdata_en)

        def process():
            yield from wb_write(csrhost.bus, PI_COMMAND_ADDR >> 2, (1 << 4), sel=0xF)
            yield
            yield from wb_write(csrhost.bus, PI_COMMAND_ISSUE_ADDR >> 2, 1, sel=0xF)
            self.assertEqual((yield pc.cnt), 1)
            yield
            yield from wb_write(csrhost.bus, PI_COMMAND_ISSUE_ADDR >> 2, 1, sel=0xF)
            self.assertEqual((yield pc.cnt), 2)

        runSimulation(m, process, "test_phaseinjector.vcd")

    def test_rddata_en(self):
        m, dfi, csrhost = self.generate_phaseinjector()

        m.submodules.pc = pc = PulseCounter()
        m.d.comb += pc.i.eq(dfi.phases[0].rddata_en)

        def process():
            yield from wb_write(csrhost.bus, PI_COMMAND_ADDR >> 2, (1 << 5), sel=0xF)
            yield
            yield from wb_write(csrhost.bus, PI_COMMAND_ISSUE_ADDR >> 2, 1, sel=0xF)
            self.assertEqual((yield pc.cnt), 1)
            yield
            yield from wb_write(csrhost.bus, PI_COMMAND_ISSUE_ADDR >> 2, 1, sel=0xF)
            self.assertEqual((yield pc.cnt), 2)

        runSimulation(m, process, "test_phaseinjector.vcd")

class DFIInjectorTestCase(FHDLTestCase):
    def generate_dfiinjector(self):
        csrhost = CSRHost()
        dut = DFIInjector(csrhost.bank, addressbits=14, bankbits=3, nranks=1, databits=16, nphases=1)
        csrhost.init_bridge()
        m = Module()
        m.submodules += csrhost
        m.submodules += dut

        return (m, dut, csrhost)

    def test_cke(self):
        m, dut, csrhost = self.generate_dfiinjector()

        def process():
            yield from wb_write(csrhost.bus, DFII_CONTROL_ADDR >> 2, (1 << 1), sel=0xF)
            yield
            self.assertTrue((yield dut.master.phases[0].cke[0]))

            yield from wb_write(csrhost.bus, DFII_CONTROL_ADDR >> 2, 0, sel=0xF)
            yield
            self.assertFalse((yield dut.master.phases[0].cke[0]))

        runSimulation(m, process, "test_dfiinjector.vcd")

    def test_odt(self):
        m, dut, csrhost = self.generate_dfiinjector()

        def process():
            yield from wb_write(csrhost.bus, DFII_CONTROL_ADDR >> 2, (1 << 2), sel=0xF)
            yield
            self.assertTrue((yield dut.master.phases[0].odt[0]))

            yield from wb_write(csrhost.bus, DFII_CONTROL_ADDR >> 2, 0, sel=0xF)
            yield
            self.assertFalse((yield dut.master.phases[0].odt[0]))

        runSimulation(m, process, "test_dfiinjector.vcd")

    def test_reset(self):
        m, dut, csrhost = self.generate_dfiinjector()

        def process():
            yield from wb_write(csrhost.bus, DFII_CONTROL_ADDR >> 2, (1 << 3), sel=0xF)
            yield
            self.assertTrue((yield dut.master.phases[0].reset_n))

            yield from wb_write(csrhost.bus, DFII_CONTROL_ADDR >> 2, 0, sel=0xF)
            yield
            self.assertFalse((yield dut.master.phases[0].reset_n))

        runSimulation(m, process, "test_dfiinjector.vcd")
