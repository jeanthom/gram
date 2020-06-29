// This file is Copyright (c) 2020 LambdaConcept <contact@lambdaconcept.com>

`timescale 1 ns / 1 ps

module simsoctb;
  // GSR & PUR init requires for Lattice models
  GSR GSR_INST (
    .GSR(1'b1)
  );
  PUR PUR_INST (
    .PUR (1'b1)
  );

  reg clkin;
  wire sync;
  wire sync2x;
  wire dramsync;
  wire init;

  // Generate 100 Mhz clock
  always 
  begin
    clkin = 1'b1; 
    #5;
    clkin = 1'b0;
    #5;
  end

  // UART
  wire uart_rx;
  wire uart_tx;

  // DDR3 init
  wire dram_ck;
  wire dram_cke;
  wire dram_we_n;
  wire dram_ras_n;
  wire dram_cas_n;
  wire [15:0] dram_dq;
  wire [1:0] dram_dqs;
  wire [1:0] dram_dqs_n;
  wire [13:0] dram_a;
  wire [2:0] dram_ba;
  wire [1:0] dram_dm;
  wire dram_odt;
  wire [1:0] dram_tdqs_n;

  ddr3 ram_chip (
    .rst_n(1'b1),
    .ck(dram_ck),
    .ck_n(1'b0),
    .cke(dram_cke),
    .cs_n(1'b0),
    .ras_n(dram_ras_n),
    .cas_n(dram_cas_n),
    .we_n(dram_we_n),
    .dm_tdqs(dram_dm),
    .ba(dram_ba),
    .addr(dram_a),
    .dq(dram_dq),
    .dqs(dram_dqs),
    .dqs_n(dram_dqs_n),
    .tdqs_n(dram_tdqs_n),
    .odt(dram_odt)
  );
  
  top simsoctop (
    .ddr3_0__dq__io(dram_dq),
    .ddr3_0__dqs__io(dram_dqs),
    .ddr3_0__clk__io(dram_ck),
    .ddr3_0__cke__io(dram_cke),
    .ddr3_0__we_n__io(dram_we_n),
    .ddr3_0__ras_n__io(dram_ras_n),
    .ddr3_0__cas_n__io(dram_cas_n),
    .ddr3_0__a__io(dram_a),
    .ddr3_0__ba__io(dram_ba),
    .ddr3_0__dm__io(dram_dm),
    .ddr3_0__odt__io(dram_odt),
    .clk100_0__io(clkin),
    .rst_0__io(1'b0),
    .uart_0__rx__io(uart_rx),
    .uart_0__tx__io(uart_tx)
  );

  assign uart_rx = 1'b1;

  initial
  begin
    $dumpfile("simsoc.fst");
    $dumpvars(0, clkin);
    $dumpvars(0, dram_dq);
    $dumpvars(0, dram_dqs);
    $dumpvars(0, dram_ck);
    $dumpvars(0, dram_cke);
    $dumpvars(0, dram_we_n);
    $dumpvars(0, dram_ras_n);
    $dumpvars(0, dram_cas_n);
    $dumpvars(0, dram_a);
    $dumpvars(0, dram_ba);
    $dumpvars(0, dram_dm);
    $dumpvars(0, dram_odt);
    $dumpvars(0, uart_rx);
    $dumpvars(0, uart_tx);
    $dumpvars(0, simsoctop);

    // Wait for power-on reset
    //#700000; // 700us
    #70000;

    $finish;
  end
endmodule
