from nmigen import *
from nmigen.hdl.ast import Past
from nmigen.asserts import Assert, Assume

from gram.core.refresher import RefreshExecuter, RefreshSequencer, RefreshTimer, RefreshPostponer, Refresher
from gram.compat import *
from utils import *

class RefreshExecuterTestCase(FHDLTestCase):
    def test_executer(self):
        def generic_test(abits, babits, trp, trfc):
            m = Module()
            m.submodules.dut = dut = RefreshExecuter(abits=abits, babits=babits, trp=trp, trfc=trfc)

            def process():
                yield dut.start.eq(1)
                yield
                yield
                self.assertEqual((yield dut.a), 2**10)
                for i in range(trp):
                    yield
                self.assertEqual((yield dut.a), 0)

            runSimulation(m, process, "test_refreshexecuter.vcd")

        generic_test(20, 20, 5, 5)
        generic_test(20, 20, 100, 5)

class RefreshSequencerTestCase(FHDLTestCase):
    def test_formal(self):
        dut = RefreshSequencer(abits=14, babits=3, trp=5, trfc=5, postponing=1)
        self.assertFormal(dut, mode="bmc", depth=4)

class RefreshTimerTestCase(FHDLTestCase):
    def test_formal(self):
        def generic_test(tREFI):
            dut = RefreshTimer(tREFI)
            self.assertFormal(dut, mode="bmc", depth=4)
        [generic_test(_) for _ in [2, 5, 10]]

class RefreshPostponerTestCase(FHDLTestCase):
    def test_init(self):
        m = Module()
        m.submodules.dut = dut = RefreshPostponer(1)

        def process():
            self.assertFalse((yield dut.req_o))

        runSimulation(m, process, "test_refreshpostponer.vcd")

    def test_delay(self):
        def generic_test(delay):
            m = Module()
            m.submodules.dut = dut = RefreshPostponer(delay)

            def process():
                yield dut.req_i.eq(1)
                yield

                for i in range(delay):
                    self.assertFalse((yield dut.req_o))
                    yield

                self.assertTrue((yield dut.req_o))

            runSimulation(m, process, "test_refreshpostponer.vcd")

        [generic_test(_) for _ in [1, 5, 10]]

    def test_req_not_stuck(self):
        def generic_test(delay):
            m = Module()
            m.submodules.dut = dut = RefreshPostponer(delay)

            def process():
                yield dut.req_i.eq(1)
                yield

                for i in range(delay):
                    yield

                yield dut.req_i.eq(0)
                yield
                yield

                self.assertFalse((yield dut.req_o))

            runSimulation(m, process, "test_refreshpostponer.vcd")

        [generic_test(_) for _ in [1, 5, 10]]

class RefresherTestCase(FHDLTestCase):
    class Obj:
        pass

    settings = Obj()
    settings.with_refresh = True
    settings.refresh_zqcs_freq = 1e0
    settings.timing = Obj()
    settings.timing.tREFI = 64
    settings.timing.tRP   = 1
    settings.timing.tRFC  = 2
    settings.timing.tZQCS = 64
    settings.geom = Obj()
    settings.geom.addressbits = 16
    settings.geom.bankbits    = 3
    settings.phy = Obj()
    settings.phy.nranks = 1

    def test_init(self):
        def generic_test(postponing):
            m = Module()
            m.submodules.dut = dut = Refresher(self.settings, 100e6, postponing)

            def process():
                self.assertFalse((yield dut.cmd.valid))

            runSimulation(m, process, "test_refresher.vcd")

        [generic_test(_) for _ in [1, 2, 4, 8]]
