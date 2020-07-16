// This file is Copyright (c) 2020 LambdaConcept <contact@lambdaconcept.com>

`timescale 1 ns / 1 ns

module simsoctb;
  //parameter simticks = 70000;
  parameter simticks = 60000000;

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
      clkin = 1;
      #5;
      clkin = 0;
      #5;
    end

  // UART
  reg uart_rx;
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
  reg dram_rst;

  ddr3 #(
    .check_strict_timing(0)
  ) ram_chip (
    .rst_n(~dram_rst),
    .ck(dram_ck),
    .ck_n(~dram_ck),
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
  //defparam ram_chip.
  
  top simsoctop (
    .ddr3_0__dq__io(dram_dq),
    .ddr3_0__dqs__io(dram_dqs),
    .ddr3_0__clk__io(dram_ck),
    .ddr3_0__clk_en__io(dram_cke),
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
      $dumpvars(0, ram_chip);

      #simticks $finish;
    end

  // UART
  reg [31:0] tmp;
  initial
    begin
      uart_rx <= 1'b1;
      dram_rst = 1;
      #350; // Wait for RESET and POR

      // Software control
      dram_rst = 0;

      #10;

      $display("Release RESET_N");
      wishbone_write(32'h0000900c >> 2, 32'h0); // p0 address
      wishbone_write(32'h00009010 >> 2, 32'h0); // p0 baddress
      wishbone_write(32'h00009000 >> 2, 8'h0C); // DFII_CONTROL_ODT|DFII_CONTROL_RESET_N
      $display("Enable CKE");
      wishbone_write(32'h00009000 >> 2, 8'h0E); // DFII_CONTROL_ODT|DFII_CONTROL_RESET_N|DFI_CONTROL_CKE
      if (dram_cke != 1)
        begin
          $display("CKE activation failure");
          $finish;
        end

      // Set MR2
      $display("Set MR2");
      wishbone_write(32'h0000900c >> 2, 32'h200); // p0 address
      wishbone_write(32'h00009010 >> 2, 32'h2); // p0 baddress
      wishbone_write(32'h00009004 >> 2, 8'h0F); // RAS|CAS|WE|CS
      wishbone_write(32'h00009008 >> 2, 8'h01); // Command issue strobe

      // Set MR3
      $display("Set MR3");
      wishbone_write(32'h0000900c >> 2, 32'h0); // p0 address
      wishbone_write(32'h00009010 >> 2, 32'h3); // p0 baddress
      wishbone_write(32'h00009004 >> 2, 8'h0F); // RAS|CAS|WE|CS
      wishbone_write(32'h00009008 >> 2, 8'h01); // Command issue strobe

      // Set MR1
      $display("Set MR1");
      wishbone_write(32'h0000900c >> 2, 32'h6); // p0 address
      wishbone_write(32'h00009010 >> 2, 32'h1); // p0 baddress
      wishbone_write(32'h00009004 >> 2, 8'h0F); // RAS|CAS|WE|CS
      wishbone_write(32'h00009008 >> 2, 8'h01); // Command issue strobe

      // Set MR0
      $display("Set MR0");
      wishbone_write(32'h0000900c >> 2, 32'h320); // p0 address
      wishbone_write(32'h00009010 >> 2, 32'h0); // p0 baddress
      wishbone_write(32'h00009004 >> 2, 8'h0F); // RAS|CAS|WE|CS
      wishbone_write(32'h00009008 >> 2, 8'h01); // Command issue strobe
      wishbone_write(32'h0000900c >> 2, 32'h220); // p0 address
      wishbone_write(32'h00009010 >> 2, 32'h0); // p0 baddress
      wishbone_write(32'h00009004 >> 2, 8'h0F); // RAS|CAS|WE|CS
      wishbone_write(32'h00009008 >> 2, 8'h01); // Command issue strobe
      #6000; // tDLLK

      // ZQ calibration
      $display("Start ZQ calibration");
      wishbone_write(32'h0000900c >> 2, 32'h400); // p0 address (A10=1)
      wishbone_write(32'h00009010 >> 2, 32'h0); // p0 baddress
      wishbone_write(32'h00009004 >> 2, 8'h03); // WE|CS
      wishbone_write(32'h00009008 >> 2, 8'h01); // Command issue strobe
      #6000; // tZQinit

      // Hardware control
      wishbone_write(32'h00009000 >> 2, 8'h01); // DFII_CONTROL_SEL
      #2000;

      wishbone_read(32'h10000000 >> 2, tmp);
      #2000 assert_equal_32(tmp, 32'hFACECA8C);

      // Write
      wishbone_write(32'h10000000 >> 2, 32'h12345678);
      #10000;
      wishbone_write(32'h10000100 >> 2, 32'h00000000);
      #10000;
      wishbone_read(32'h10000000 >> 2, tmp);
    end

  task wishbone_write;
    input [31:0] address;
    input [31:0] value;

    begin
      uart_send(8'h01); // Write command
      uart_send(8'h01); // Length
      uart_send(address[31:24]); // Address
      uart_send(address[23:16]);
      uart_send(address[15:8]);
      uart_send(address[7:0]);
      uart_send(value[31:24]);
      uart_send(value[23:16]);
      uart_send(value[15:8]);
      uart_send(value[7:0]);
      #100;
    end
  endtask

  task wishbone_read;
    input [31:0] address;
    output [31:0] value;

    begin
      uart_send(8'h02); // Read command
      uart_send(8'h01); // Length
      uart_send(address[31:24]); // Address
      uart_send(address[23:16]);
      uart_send(address[15:8]);
      uart_send(address[7:0]);
      uart_read(value[31:24]);
      uart_read(value[23:16]);
      uart_read(value[15:8]);
      uart_read(value[7:0]);
    end
  endtask

  task uart_send;
    input [7:0] data;
    integer i;

    begin
      uart_rx = 0;
      #50;
      for (i = 0; i < 8; i = i + 1)
        begin
          uart_rx <= data[i];
          #50;
        end
      uart_rx = 1;
      #50;
    end
  endtask

  task uart_read;
    output [7:0] data;
    integer i;

    begin
      while (uart_tx)
        begin
          #1;
        end

      for (i = 0; i < 8; i = i+1)
        begin
          #50 data[i] = uart_tx;
        end

      #50;
    end
  endtask

  task assert_equal_32;
    input [31:0] inA;
    input [31:0] inB;

    begin
      if (inA != inB)
        begin
          $display("%m at %t: Assertion failed (32-bit) equality: %08x != %08x", $time, inA, inB);
          $finish;
        end
    end
  endtask
endmodule
