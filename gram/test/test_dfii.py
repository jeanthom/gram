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

        self._bridge = self.bridge(data_width=32, granularity=8, alignment=2)
        self.bus = self._bridge.bus

    def elaborate(self, platform):
        m = Module()
        m.submodules += self._bridge
        return m

class PhaseInjectorTestCase(FHDLTestCase):
    def test_initialstate(self):
        dfi = Interface(12, 8, 1, 8, 1)
        m = Module()
        m.submodules.csrhost = csrhost = CSRHost()
        m.submodules.dut = dut = PhaseInjector(csrhost.bank, dfi.phases[0])

        def process():
            self.assertTrue((yield dut.phases[0].cas_n))
            self.assertTrue((yield dut.phases[0].ras_n))
            self.assertTrue((yield dut.phases[0].we_n))
            self.assertTrue((yield dut.phases[0].act_n))

        runSimulation(m, process, "test_phaseinjector.vcd")
