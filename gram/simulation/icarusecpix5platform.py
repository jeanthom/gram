import os
import subprocess

from nmigen.build import *
from nmigen.vendor.lattice_ecp5 import *
from nmigen_boards.resources import *


__all__ = ["IcarusECPIX5Platform"]


class IcarusECPIX5Platform(LatticeECP5Platform):
    device = "LFE5UM5G-85F"
    package = "BG554"
    speed = "8"
    default_clk = "clk100"
    default_rst = "rst"

    resources = [
        Resource("rst", 0, PinsN("AB1", dir="i"), Attrs(IO_TYPE="LVCMOS33")),
        Resource("clk100", 0, Pins("K23", dir="i"),
                 Clock(100e6), Attrs(IO_TYPE="LVCMOS33")),

        UARTResource(0,
                     rx="R26", tx="R24",
                     attrs=Attrs(IO_TYPE="LVCMOS33", PULLMODE="UP")
                     ),

        Resource("ddr3", 0,
                 Subsignal("clk", Pins("H3", dir="o")),
                 #Subsignal("clk", DiffPairs("H3", "J3", dir="o"), Attrs(IO_TYPE="SSTL135D_I")),
                 Subsignal("clk_en", Pins("P1", dir="o")),
                 Subsignal("we", PinsN("R3", dir="o")),
                 Subsignal("ras", PinsN("T3", dir="o")),
                 Subsignal("cas", PinsN("P2", dir="o")),
                 Subsignal("a", Pins("T5 M3 L3 V6 K2 W6 K3 L1 H2 L2 N1 J1 M1 K1", dir="o")),
                 Subsignal("ba", Pins("U6 N3 N4", dir="o")),
                 Subsignal("dqs", DiffPairs("V4 V1", "U5 U2", dir="io"), Attrs(IO_TYPE="SSTL135D_I")),
                 Subsignal("dq", Pins("T4 W4 R4 W5 R6 P6 P5 P4 R1 W3 T2 V3 U3 W1 T1 W2", dir="io")),
                 Subsignal("dm", Pins("U4 U1", dir="o")),
                 Subsignal("odt", Pins("P3", dir="o")),
                 Attrs(IO_TYPE="SSTL135_I")
                 ),
    ]

    connectors = [
        Connector("pmod", 0, "T25 U25 U24 V24 - - T26 U26 V26 W26 - -"),
        Connector("pmod", 1, "U23 V23 U22 V21 - - W25 W24 W23 W22 - -"),
        Connector("pmod", 2, "J24 H22 E21 D18 - - K22 J21 H21 D22 - -"),
        Connector("pmod", 3, " E4  F4  E6  H4 - -  F3  D4  D5  F5 - -"),
        Connector("pmod", 4, "E26 D25 F26 F25 - - A25 A24 C26 C25 - -"),
        Connector("pmod", 5, "D19 C21 B21 C22 - - D21 A21 A22 A23 - -"),
        Connector("pmod", 6, "C16 B17 C18 B19 - - A17 A18 A19 C19 - -"),
        Connector("pmod", 7, "D14 B14 E14 B16 - - C14 A14 A15 A16 - -"),
    ]

    @property
    def required_tools(self):
        return ["yosys"]

    @property
    def file_templates(self):
        return {
            **TemplatedPlatform.build_script_templates,
            "{{name}}.il": r"""
            # {{autogenerated}}
            {{emit_rtlil()}}
            """,
        }

    @property
    def command_templates(self):
        return []
