// --------------------------------------------------------------------
// >>>>>>>>>>>>>>>>>>>>>>>>> COPYRIGHT NOTICE <<<<<<<<<<<<<<<<<<<<<<<<<
// --------------------------------------------------------------------
// Copyright (c) 2007 by Lattice Semiconductor Corporation
// --------------------------------------------------------------------
//
//
//                     Lattice Semiconductor Corporation
//                     5555 NE Moore Court
//                     Hillsboro, OR 97214
//                     U.S.A.
//
//                     TEL: 1-800-Lattice  (USA and Canada)
//                          1-408-826-6000 (other locations)
//
//                     web: http://www.latticesemi.com/
//                     email: techsupport@latticesemi.com
//
// --------------------------------------------------------------------
//
// Simulation Library File for DDRDLLA in ECP5U/M, LIFMD
//
// $Header:  
//

`celldefine 
`timescale 1 ns / 1 ps
module DDRDLLA (CLK, RST, UDDCNTLN, FREEZE, DDRDEL, LOCK, DCNTL7, DCNTL6, DCNTL5, DCNTL4,
                DCNTL3, DCNTL2, DCNTL1, DCNTL0);

parameter FORCE_MAX_DELAY = "NO";
parameter GSR = "ENABLED";

parameter   LOCK_CYC   = 200;

localparam PHASE_SHIFT = 90;
input  CLK, RST, UDDCNTLN, FREEZE;
output LOCK, DDRDEL, DCNTL7, DCNTL6, DCNTL5, DCNTL4, DCNTL3, DCNTL2, DCNTL1, DCNTL0;

wire RST_int, UDDCNTL_int, UDDCNTL_buf;
reg  LOCK_int, DDRDEL_int;
wire clkin_in, FREEZEB, clkin_out;
reg last_clkin_in, freeze_clk_sync, freeze_clk_sync2n;
reg SRN, clock_valid;
integer cntl_ratio;
wire [7:0] cntl_reg;
reg  [7:0] cntl_reg_final;
reg  [7:0] cntl_reg_update;
realtime next_clock_edge, last_clock_edge;
realtime t_in_clk, t_in_clk1, t_in_clk2;
realtime t_90, t_45, t_57, t_68, t_79;
realtime t_101, t_112, t_123, t_135;
realtime delta;

initial
begin
   cntl_reg_update = 8'b000000;
   cntl_ratio = 0;
   delta = 0.025;
   clock_valid = 1'b0;
end

//  tri1 GSR_sig = GSR_INST.GSRNET;
//  tri1 PUR_sig = PUR_INST.PURNET;
tri1 GSR_sig, PUR_sig;
`ifndef mixed_hdl
   assign GSR_sig = GSR_INST.GSRNET;
   assign PUR_sig = PUR_INST.PURNET;
`else
   gsr_pur_assign gsr_pur_assign_inst (GSR_sig, PUR_sig);
`endif

buf buf_clkin (clkin_in, CLK);
buf buf_rst  (RSTB1, RST);
buf buf_uddcntl (UDDCNTL_buf, UDDCNTLN);
buf buf_freeze (FREEZEB, FREEZE);

buf buf_lock (LOCK, LOCK_int);
buf buf_ddrdel (DDRDEL, DDRDEL_int);
buf U4 (DCNTL0, cntl_reg_final[0]);
buf U5 (DCNTL1, cntl_reg_final[1]);
buf U6 (DCNTL2, cntl_reg_final[2]);
buf U7 (DCNTL3, cntl_reg_final[3]);
buf U8 (DCNTL4, cntl_reg_final[4]);
buf U9 (DCNTL5, cntl_reg_final[5]);
buf U10 (DCNTL6, cntl_reg_final[6]);
buf U11 (DCNTL7, cntl_reg_final[7]);

integer clk_rising_edge_count;

assign UDDCNTL_int = ~UDDCNTL_buf;

initial
begin
   clk_rising_edge_count = 0;
   freeze_clk_sync = 1'b0;
   freeze_clk_sync2n = 1'b1;
   last_clkin_in = 1'b0;
end

  always @ (GSR_sig or PUR_sig ) begin
    if (GSR == "ENABLED")
      SRN = GSR_sig & PUR_sig ;
    else if (GSR == "DISABLED")
      SRN = PUR_sig;
  end

  not (SR, SRN);
  or INST1 (RST_int, RSTB1, SR);

always @ (clkin_in)
begin
   last_clkin_in <= clkin_in;
end

always @ (clkin_in or RST_int)     // neg edge
begin
   if (RST_int == 1'b1)
   begin
      freeze_clk_sync <= 1'b0;
      freeze_clk_sync2n <= 1'b1;
   end 
   else if (clkin_in === 1'b0 && last_clkin_in === 1'b1)
   begin
         freeze_clk_sync <= FREEZEB;
         freeze_clk_sync2n <= ~freeze_clk_sync;
   end
end

and INST2 (clkin_out, clkin_in, freeze_clk_sync2n);

always @(posedge clkin_out or posedge RST_int) 
begin
   if (RST_int)
       clk_rising_edge_count = 0;
   else
       clk_rising_edge_count = clk_rising_edge_count + 1;
end

always @(clk_rising_edge_count or RST_int)
begin
    if (RST_int)
         LOCK_int = 1'b0;
    else if (clk_rising_edge_count > LOCK_CYC)
         LOCK_int = 1'b1;
end

always @(LOCK_int or UDDCNTL_int or RST_int)
begin
  if (RST_int)
      DDRDEL_int = 1'b0;
  else if (UDDCNTL_int == 1'b1)
      DDRDEL_int = LOCK_int;
  else
      DDRDEL_int = DDRDEL_int;
end

  always @(posedge clkin_in)
   begin
   last_clock_edge=next_clock_edge;
   next_clock_edge=$realtime;
                                                                                                       
    if (last_clock_edge > 0)
        begin
        t_in_clk <= next_clock_edge - last_clock_edge;
        t_in_clk1 <= t_in_clk;
        end
                                                                                                       
    if (t_in_clk > 0)
        begin
         if ( ((t_in_clk - t_in_clk1) < 0.0001) && ((t_in_clk - t_in_clk1) > -0.0001))
//         if (t_in_clk == t_in_clk1)
            clock_valid = 1;
         else
            clock_valid = 0;
        end

    if (t_in_clk > 0)
    begin
        t_45 = (t_in_clk / 8 );
        t_57 = ((t_in_clk * 5) / 32 );
        t_68 = ((t_in_clk * 3) / 16 );
        t_79 = ((t_in_clk * 7) / 32 );
        t_90 = (t_in_clk / 4 );
        t_101 = ((t_in_clk * 9) / 32 );
        t_112 = ((t_in_clk * 5) / 16 );
        t_123 = ((t_in_clk * 11) / 32 );
        t_135 = ((t_in_clk * 3) / 8 );
     end
                                                                                                       
     if (PHASE_SHIFT == 90)
     begin
        if (t_90 > 0)
        begin
           cntl_ratio = (t_90 / delta);
        end
     end
   end

  assign cntl_reg = cntl_ratio;

  always @(cntl_reg or UDDCNTL_int or clock_valid)
  begin
     if (clock_valid == 1'b1)
     begin
        if (UDDCNTL_int == 1'b1)
        begin
           cntl_reg_update <= cntl_reg;
        end
     end
  end

  always @(RST_int or cntl_reg_update)
  begin
     if (RST_int == 1'b1)
        cntl_reg_final <= 8'b00000000;
     else
        cntl_reg_final <= cntl_reg_update;
  end

/* specify 
 
(CLK => LOCK) =  0:0:0, 0:0:0;
(CLK => DDRDEL) =  0:0:0, 0:0:0;
(RST => LOCK) =  0:0:0, 0:0:0;
(RST => DDRDEL) =  0:0:0, 0:0:0;
(UDDCNTLN => LOCK) =  0:0:0, 0:0:0;
(UDDCNTLN => DDRDEL) =  0:0:0, 0:0:0;
 
endspecify */

endmodule

`endcelldefine 
