#!/bin/bash
set -e

# Check for presence of the Diamond ECP5 verilog model files
LIB_DIR=./ecp5u
if [ ! -d "$LIB_DIR" ]; then
    LIB_DIR=/usr/local/diamond/3.11_x64/ispfpga/verilog/data/ecp5u
    if [ ! -d "$LIB_DIR" ]; then
        echo "Error: Could not find the ECP5 verilog models." >&2
        echo >&2
        echo "Please either install Diamond (in /usr/local), " >&2
        echo "or copy its ecp5u directory ($LIB_DIR) here." >&2
        exit 1
    fi
fi

python3 simsoc.py
yosys simsoc.ys
cp ${LIB_DIR}/DDRDLLA.v DDRDLLA.v
patch DDRDLLA.v < DDRDLLA.patch
iverilog -Wall -g2012 -s simsoctb -o simsoc simsoctb.v build_simsoc/top.v dram_model/ddr3.v ${LIB_DIR}/ECLKSYNCB.v ${LIB_DIR}/EHXPLLL.v ${LIB_DIR}/PUR.v ${LIB_DIR}/GSR.v \
	${LIB_DIR}/FD1S3AX.v ${LIB_DIR}/SGSR.v ${LIB_DIR}/ODDRX2F.v ${LIB_DIR}/ODDRX2DQA.v ${LIB_DIR}/DELAYG.v ${LIB_DIR}/BB.v ${LIB_DIR}/OB.v ${LIB_DIR}/IB.v \
	${LIB_DIR}/DQSBUFM.v ${LIB_DIR}/UDFDL5_UDP_X.v ${LIB_DIR}/TSHX2DQSA.v ${LIB_DIR}/TSHX2DQA.v ${LIB_DIR}/ODDRX2DQSB.v ${LIB_DIR}/IDDRX2DQA.v DDRDLLA.v \
	${LIB_DIR}/CLKDIVF.v
vvp -n simsoc -fst-speed
