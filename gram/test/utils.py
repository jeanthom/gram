import os
import re
import shutil
import subprocess
import textwrap
import traceback
import unittest
import warnings
from contextlib import contextmanager

from nmigen import *
from nmigen.back.pysim import *
from nmigen.hdl.ir import Fragment
from nmigen.back import rtlil
from nmigen._toolchain import require_tool


__all__ = ["FHDLTestCase", "runSimulation", "wb_read", "wb_write", "PulseCounter"]

def runSimulation(module, process, vcd_filename="anonymous.vcd", clock=1e-6):
    sim = Simulator(module)
    with sim.write_vcd(vcd_filename):
        sim.add_clock(clock)
        sim.add_sync_process(process)
        sim.run()

class FHDLTestCase(unittest.TestCase):
    def assertRepr(self, obj, repr_str):
        if isinstance(obj, list):
            obj = Statement.cast(obj)
        def prepare_repr(repr_str):
            repr_str = re.sub(r"\s+",   " ",  repr_str)
            repr_str = re.sub(r"\( (?=\()", "(", repr_str)
            repr_str = re.sub(r"\) (?=\))", ")", repr_str)
            return repr_str.strip()
        self.assertEqual(prepare_repr(repr(obj)), prepare_repr(repr_str))

    @contextmanager
    def assertRaises(self, exception, msg=None):
        with super().assertRaises(exception) as cm:
            yield
        if msg is not None:
            # WTF? unittest.assertRaises is completely broken.
            self.assertEqual(str(cm.exception), msg)

    @contextmanager
    def assertRaisesRegex(self, exception, regex=None):
        with super().assertRaises(exception) as cm:
            yield
        if regex is not None:
            # unittest.assertRaisesRegex also seems broken...
            self.assertRegex(str(cm.exception), regex)

    @contextmanager
    def assertWarns(self, category, msg=None):
        with warnings.catch_warnings(record=True) as warns:
            yield
        self.assertEqual(len(warns), 1)
        self.assertEqual(warns[0].category, category)
        if msg is not None:
            self.assertEqual(str(warns[0].message), msg)

    def assertFormal(self, spec, mode="bmc", depth=1):
        caller, *_ = traceback.extract_stack(limit=2)
        spec_root, _ = os.path.splitext(caller.filename)
        spec_dir = os.path.dirname(spec_root)
        spec_name = "{}_{}".format(
            os.path.basename(spec_root).replace("test_", "spec_"),
            caller.name.replace("test_", "")
        )

        # The sby -f switch seems not fully functional when sby is
        # reading from stdin.
        if os.path.exists(os.path.join(spec_dir, spec_name)):
            shutil.rmtree(os.path.join(spec_dir, spec_name))

        config = textwrap.dedent("""\
        [options]
        mode {mode}
        depth {depth}
        wait on

        [engines]
        smtbmc

        [script]
        read_ilang top.il
        prep

        [file top.il]
        {rtlil}
        """).format(
            mode=mode,
            depth=depth,
            rtlil=rtlil.convert(Fragment.get(spec, platform="formal"))
        )
        with subprocess.Popen([require_tool("sby"), "-f", "-d", spec_name],
                              cwd=spec_dir,
                              universal_newlines=True,
                              stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE) as proc:
            stdout, stderr = proc.communicate(config)
            if proc.returncode != 0:
                self.fail("Formal verification failed:\n" + stdout)

def wb_read(bus, addr, sel, timeout=32):
    yield bus.cyc.eq(1)
    yield bus.stb.eq(1)
    yield bus.adr.eq(addr)
    yield bus.sel.eq(sel)
    yield
    cycles = 0
    while not (yield bus.ack):
        yield
        if cycles >= timeout:
            raise RuntimeError("Wishbone transaction timed out")
        cycles += 1
    data = (yield bus.dat_r)
    yield bus.cyc.eq(0)
    yield bus.stb.eq(0)
    return data

def wb_write(bus, addr, data, sel, timeout=32):
    yield bus.cyc.eq(1)
    yield bus.stb.eq(1)
    yield bus.adr.eq(addr)
    yield bus.we.eq(1)
    yield bus.sel.eq(sel)
    yield bus.dat_w.eq(data)
    yield
    cycles = 0
    while not (yield bus.ack):
        yield
        if cycles >= timeout:
            raise RuntimeError("Wishbone transaction timed out")
        cycles += 1
    yield bus.cyc.eq(0)
    yield bus.stb.eq(0)
    yield bus.we.eq(0)

class PulseCounter(Elaboratable):
    def __init__(self, max=16):
        self.i = Signal()
        self.rst = Signal()
        self.cnt = Signal(range(max))

    def elaborate(self, platform):
        m = Module()

        with m.If(self.rst):
            m.d.sync += self.cnt.eq(0)
        with m.Elif(self.i):
            m.d.sync += self.cnt.eq(self.cnt+1)

        return m
