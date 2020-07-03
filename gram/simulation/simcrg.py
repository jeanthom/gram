# This file is Copyright (c) 2020 LambdaConcept <contact@lambdaconcept.com>

from nmigen import *
from icarusecpix5platform import IcarusECPIX5Platform
from crg import *
from nmigen.build import *

class Top(Elaboratable):
    def __init__(self):
        self.dramsync = Signal()
        self.dramsync_reset = Signal()
        self.sync = Signal()
        self.sync2x = Signal()

    def elaborate(self, platform):
        m = Module()

        m.submodules.crg = crg = ECPIX5CRG()

        resources = [
            Resource("clock_conn", 0, Pins("1 2 3 4", conn=("pmod", 5,), dir="o"), Attrs(IO_TYPE="LVCMOS33", PULLMODE="UP")),
        ]
        platform.add_resources(resources)

        clock_conn = platform.request("clock_conn", 0)
        m.d.comb += [
            self.dramsync.eq(ClockSignal("dramsync")),
            self.dramsync_reset.eq(ResetSignal("dramsync")),
            self.sync.eq(ClockSignal("sync")),
            self.sync2x.eq(ClockSignal("sync2x")),

            clock_conn[0].eq(ClockSignal("dramsync")),
            clock_conn[1].eq(ResetSignal("dramsync")),
            clock_conn[2].eq(ClockSignal("sync")),
            clock_conn[3].eq(ClockSignal("sync2x")),
        ]

        return m

if __name__ == "__main__":
    top = Top()
    IcarusECPIX5Platform().build(top, build_dir="build_simcrg")
