from nmigen import *

from gram.core.multiplexer import _AntiStarvation, _CommandChooser
from gram.common import cmd_request_rw_layout
import gram.stream as stream
from gram.test.utils import *

class CommandChooserTestCase(FHDLTestCase):
    def prepare_testbench(self):
        a = 16
        ba = 3
        requests = []
        for i in range(10):
            requests += [stream.Endpoint(cmd_request_rw_layout(a, ba))]
        dut = _CommandChooser(requests)

        return (requests, dut)

    def test_wants(self):
        requests, dut = self.prepare_testbench()

        def process():
            for i in range(10):
                yield requests[i].a.eq(i)

            # Fake requests, non valid requests shouldn't be picked
            yield requests[5].is_read.eq(1)
            yield requests[5].valid.eq(1)
            yield requests[6].is_read.eq(1)
            yield requests[6].valid.eq(0)
            yield requests[7].is_write.eq(1)
            yield requests[7].valid.eq(1)
            yield requests[8].is_write.eq(1)
            yield requests[8].valid.eq(0)

            # want_writes
            yield dut.want_writes.eq(1)
            yield; yield Delay(1e-8)
            self.assertEqual((yield dut.cmd.a), 7)

            # want_reads
            yield dut.want_writes.eq(0)
            yield dut.want_reads.eq(1)
            yield; yield Delay(1e-8)
            self.assertEqual((yield dut.cmd.a), 5)

        runSimulation(dut, process, "test_core_multiplexer_commandchooser.vcd")

    def test_helpers(self):
        requests, dut = self.prepare_testbench()

        def process():
            for i in range(10):
                yield requests[i].a.eq(i)

            # Fake requests
            yield requests[5].is_read.eq(1)
            yield requests[5].valid.eq(1)
            yield requests[6].is_read.eq(1)
            yield requests[6].valid.eq(0)
            yield requests[7].is_write.eq(1)
            yield requests[7].valid.eq(1)
            yield requests[8].is_write.eq(1)
            yield requests[8].valid.eq(0)

            # want_writes
            yield dut.want_writes.eq(1)
            yield; yield Delay(1e-8)
            self.assertTrue((yield dut.write()))
            self.assertFalse((yield dut.read()))

            # want_reads
            yield dut.want_writes.eq(0)
            yield dut.want_reads.eq(1)
            yield; yield Delay(1e-8)
            self.assertTrue((yield dut.read()))
            self.assertFalse((yield dut.write()))

        runSimulation(dut, process, "test_core_multiplexer_commandchooser.vcd")

class AntiStarvationTestCase(FHDLTestCase):
    def test_duration(self):
        def generic_test(timeout):
            dut = _AntiStarvation(timeout)

            def process():
                yield dut.en.eq(1)
                yield
                yield dut.en.eq(0)
                yield

                for i in range(timeout):
                    self.assertFalse((yield dut.max_time))
                    yield

                self.assertTrue((yield dut.max_time))

            runSimulation(dut, process, "test_core_multiplexer_antistarvation.vcd")

    def test_formal(self):
        def generic_test(timeout):
            dut = _AntiStarvation(timeout)
            self.assertFormal(dut, mode="bmc", depth=timeout+1)

        generic_test(5)
        generic_test(10)
        generic_test(0x20)
