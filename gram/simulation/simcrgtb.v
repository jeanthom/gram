// This file is Copyright (c) 2020 LambdaConcept <contact@lambdaconcept.com>

`timescale 1 ns / 10 fs

module top;
  // GSR & PUR init requires for Lattice models
  GSR GSR_INST (
    .GSR(1'b0)
  );
  PUR PUR_INST (
    .PUR (1'b0)
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
  
  simcrgtop simcrgtop (
    .clkin(clkin),
    .sync(sync),
    .sync2x(sync2x),
    .dramsync(dramsync),
    .init(init)
  );

  initial
  begin
    $dumpfile("simcrg.vcd");
    $dumpvars(0, clkin);
    $dumpvars(0, sync);
    $dumpvars(0, sync2x);
    $dumpvars(0, dramsync);
    $dumpvars(0, init);
    $dumpvars(0, simcrgtop);

    #10000 $finish;
  end
endmodule
