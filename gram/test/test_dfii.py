from nmigen import *
from nmigen.hdl.ast import Past
from nmigen.asserts import Assert, Assume
from lambdasoc.periph import Peripheral

from gram.dfii import *
from gram.phy.dfi import Interface
from utils import *

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

        runSimulation(m, process, "test_phaseinjector.vcd")

    def test_setaddress(self):
        m, dfi, csrhost = self.generate_phaseinjector()

        def process():
            yield from wb_write(csrhost.bus, 0x8 >> 2, 0xCDC, sel=0xF)
            self.assertEqual((yield dfi.phases[0].address), 0xCDC)

        runSimulation(m, process, "test_phaseinjector.vcd")

    def test_setbankaddress(self):
        m, dfi, csrhost = self.generate_phaseinjector()

        def process():
            yield from wb_write(csrhost.bus, 0xC >> 2, 0xA8, sel=0xF)
            self.assertEqual((yield dfi.phases[0].bank), 0xA8)

        runSimulation(m, process, "test_phaseinjector.vcd")
