#!/bin/bash
set -e

LIB_DIR=/usr/local/diamond/3.11_x64/ispfpga/verilog/data/ecp5u

python simcrg.py generate simcrg.v
iverilog -Wall -o simcrg simcrgtb.v simcrg.v ${LIB_DIR}/ECLKSYNCB.v ${LIB_DIR}/CLKDIVF.v ${LIB_DIR}/EHXPLLL.v ${LIB_DIR}/PUR.v ${LIB_DIR}/GSR.v
vvp -n simcrg -vcd
