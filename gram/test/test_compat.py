#nmigen: UnusedElaboratable=no
from nmigen import *
from nmigen.hdl.ast import Past
from nmigen.asserts import Assert, Assume

from gram.compat import *
from gram.test.utils import *

class DelayedEnterTestCase(FHDLTestCase):
    def test_sequence(self):
        def sequence(expected_delay):
            m = Module()

            before = Signal()
            end = Signal()

            with m.FSM():
                with m.State("Before-Delayed-Enter"):
                    m.d.comb += before.eq(1)
                    m.next = "Delayed-Enter"

                delayed_enter(m, "Delayed-Enter", "End-Delayed-Enter", expected_delay)

                with m.State("End-Delayed-Enter"):
                    m.d.comb += end.eq(1)

            def process():
                while (yield before):
                    yield

                delay = 0
                while not (yield end):
                    yield
                    delay += 1

                self.assertEqual(delay, expected_delay)

            runSimulation(m, process, "test_delayedenter.vcd")

        with self.assertRaises(ValueError):
            sequence(0)
        sequence(1)
        sequence(2)
        sequence(10)
        sequence(100)
        sequence(1000)

class TimelineTestCase(FHDLTestCase):
    def test_sequence(self):
        sigA = Signal()
        sigB = Signal()
        sigC = Signal()
        timeline = Timeline([
            (1, sigA.eq(1)),
            (5, sigA.eq(1)),
            (7, sigA.eq(0)),
            (10, sigB.eq(1)),
            (11, sigB.eq(0)),
        ])

        def process():
            # Test default value for unset signals
            self.assertFalse((yield sigA))
            self.assertFalse((yield sigB))

            # Ensure that the sequence isn't triggered without the trigger signal
            for i in range(100):
                yield
                self.assertFalse((yield sigA))
                self.assertFalse((yield sigB))

            yield timeline.trigger.eq(1)
            yield
            yield timeline.trigger.eq(0)

            for i in range(11+1):
                yield

                if i == 1:
                    self.assertTrue((yield sigA))
                    self.assertFalse((yield sigB))
                elif i == 5:
                    self.assertTrue((yield sigA))
                    self.assertFalse((yield sigB))
                elif i == 7:
                    self.assertFalse((yield sigA))
                    self.assertFalse((yield sigB))
                elif i == 10:
                    self.assertFalse((yield sigA))
                    self.assertTrue((yield sigB))
                elif i == 11:
                    self.assertFalse((yield sigA))
                    self.assertFalse((yield sigB))

            # Ensure no changes happen once the sequence is done
            for i in range(100):
                yield
                self.assertFalse((yield sigA))
                self.assertFalse((yield sigB))

        runSimulation(timeline, process, "test_timeline.vcd")
