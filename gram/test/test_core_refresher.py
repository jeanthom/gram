from nmigen import *
from nmigen.hdl.ast import Past
from nmigen.asserts import Assert, Assume

from gram.core.refresher import RefreshExecuter, RefreshSequencer, RefreshTimer, RefreshPostponer, Refresher, ZQCSExecuter
from gram.compat import *
from gram.test.utils import *

class RefreshExecuterTestCase(FHDLTestCase):
    def test_executer(self):
        def generic_test(abits, babits, trp, trfc):
            dut = RefreshExecuter(abits=abits, babits=babits, trp=trp, trfc=trfc)

            def process():
                yield dut.start.eq(1)
                yield; yield Delay(1e-9)
                self.assertEqual((yield dut.a), 2**10)
                for i in range(trp):
                    yield
                yield Delay(1e-9)
                self.assertEqual((yield dut.a), 0)

            runSimulation(dut, process, "test_refreshexecuter.vcd")

        generic_test(20, 20, 5, 5)
        generic_test(20, 20, 100, 5)

class RefreshSequencerTestCase(FHDLTestCase):
    def test_formal(self):
        trp = 5; trfc = 5
        dut = RefreshSequencer(abits=14, babits=3, trp=trp, trfc=trfc, postponing=1)
        self.assertFormal(dut, mode="bmc", depth=trp+trfc+1)

class RefreshTimerTestCase(FHDLTestCase):
    def test_formal(self):
        def generic_test(tREFI):
            dut = RefreshTimer(tREFI)
            self.assertFormal(dut, mode="bmc", depth=tREFI+1)
        [generic_test(_) for _ in [2, 5, 10]]

class RefreshPostponerTestCase(FHDLTestCase):
    def test_init(self):
        dut = RefreshPostponer(1)

        def process():
            self.assertFalse((yield dut.req_o))

        runSimulation(dut, process, "test_refreshpostponer.vcd")

    def test_delay(self):
        def generic_test(delay):
            dut = RefreshPostponer(delay)

            def process():
                yield dut.req_i.eq(1)
                yield

                for i in range(delay):
                    self.assertFalse((yield dut.req_o))
                    yield

                self.assertTrue((yield dut.req_o))

            runSimulation(dut, process, "test_refreshpostponer.vcd")

        [generic_test(_) for _ in [1, 5, 10]]

    def test_req_not_stuck(self):
        def generic_test(delay):
            dut = RefreshPostponer(delay)

            def process():
                yield dut.req_i.eq(1)
                yield

                for i in range(delay):
                    yield

                yield dut.req_i.eq(0)
                yield; yield Delay(1e-9)

                self.assertFalse((yield dut.req_o))

            runSimulation(dut, process, "test_refreshpostponer.vcd")

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
            dut = Refresher(self.settings, 100e6, postponing)

            def process():
                self.assertFalse((yield dut.cmd.valid))

            runSimulation(dut, process, "test_refresher.vcd")

        [generic_test(_) for _ in [1, 2, 4, 8]]

class ZQCSExecuterTestCase(FHDLTestCase):
    abits = 12
    babits = 3
    trp = 5
    tzqcs = 5    

    def test_sequence(self):
        dut = ZQCSExecuter(self.abits, self.babits, self.trp, self.tzqcs)

        def process():
            yield dut.start.eq(1)
            yield
            yield dut.start.eq(0)
            yield

            # Check for Precharge ALL command
            for i in range(self.trp):
                self.assertEqual((yield dut.a), 2**10)
                self.assertEqual((yield dut.ba), 0)
                self.assertFalse((yield dut.cas))
                self.assertTrue((yield dut.ras))
                self.assertTrue((yield dut.we))
                self.assertFalse((yield dut.done))
                yield

            # Check for ZQCS command
            for i in range(self.tzqcs):
                self.assertFalse((yield dut.a[10]))
                self.assertFalse((yield dut.cas))
                self.assertFalse((yield dut.ras))
                self.assertTrue((yield dut.we))
                self.assertFalse((yield dut.done))
                yield

            self.assertTrue((yield dut.done))

        runSimulation(dut, process, "test_core_refresher_zqcsexecuter.vcd")