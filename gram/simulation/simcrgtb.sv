// This file is Copyright (c) 2020 LambdaConcept <contact@lambdaconcept.com>

`timescale 1 ns / 1 ns

module simcrgtb;
  // GSR & PUR init required for Lattice models
  GSR GSR_INST (
    .GSR(1'b1)
  );
  PUR PUR_INST (
    .PUR (1'b1)
  );

  reg clkin;

  // Generate 100 Mhz clock
  always 
    begin
      clkin = 1'b1; 
      #5;
      clkin = 1'b0;
      #5;
    end
  
  top top (
    .clk100_0__io(clkin),
    .rst_0__io(1'b0)
  );

  initial
    begin
      $dumpfile("simcrg.fst");
      $dumpvars(0, top);
      #1000000 $finish;
    end

  initial
    begin
      assert (top.crg_dramsync_rst == 1'b1) else $error("DRAM clock domain is not reset at t=0");
    end

  always @(negedge top.crg_dramsync_rst)
    begin
      assert($time > 600000) else $error("DRAM sync got out of reset before 600us (too early)");
      assert($time < 700000) else $error("DRAM sync got out of reset after 700us (too late)");
    end

  time last_dramsync_tick;
  always @(posedge top.crg_dramsync_clk)
    begin
      if (top.crg_dramsync_rst == 1'b0)
        begin
          assert ($time - last_dramsync_tick == 10) else $error("dramsync isn't running at 100Mhz"); 
        end

      last_dramsync_tick = $time;
    end

  time last_sync2x_tick;
  always @(posedge top.crg_sync2x_clk)
    begin
      if (top.crg_dramsync_rst == 1'b0)
        begin
          assert ($time - last_sync2x_tick == 5) else $error("sync2x isn't running at 200Mhz"); 
        end

      last_sync2x_tick = $time;
    end

  always @(posedge top.crg_dramsync_clk)
    begin
      if (top.crg_dramsync_clk && $time > 700000)
        begin
          assert(top.crg_sync2x_clk == 1) else $error("dramsync and sync2x are out of sync");
        end
    end
endmodule
