#!/bin/bash
set -e

LIB_DIR=./ecp5u

python3 simsoc.py
yosys simsoc.ys
cp ${LIB_DIR}/DDRDLLA.v DDRDLLA.v
patch DDRDLLA.v < DDRDLLA.patch
iverilog -Wall -g2012 -s simsoctb -o simsoc simsoctb.v build_simsoc/top.v dram_model/ddr3.v ${LIB_DIR}/ECLKSYNCB.v ${LIB_DIR}/EHXPLLL.v ${LIB_DIR}/PUR.v ${LIB_DIR}/GSR.v \
	${LIB_DIR}/FD1S3AX.v ${LIB_DIR}/SGSR.v ${LIB_DIR}/ODDRX2F.v ${LIB_DIR}/ODDRX2DQA.v ${LIB_DIR}/DELAYF.v ${LIB_DIR}/BB.v ${LIB_DIR}/OB.v ${LIB_DIR}/IB.v \
	${LIB_DIR}/DQSBUFM.v ${LIB_DIR}/UDFDL5_UDP_X.v ${LIB_DIR}/TSHX2DQSA.v ${LIB_DIR}/TSHX2DQA.v ${LIB_DIR}/ODDRX2DQSB.v ${LIB_DIR}/IDDRX2DQA.v DDRDLLA.v \
	${LIB_DIR}/CLKDIVF.v
vvp -n simsoc -fst-speed
