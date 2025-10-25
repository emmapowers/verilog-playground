`timescale 1ns / 1ps  ////////////////////////////////////////////////////////////////////////


module top (
    input rst_n,
    input clk,
    output [0:0] led
);
  logic reset;
  reset_gen rgen (
      .clk(clk),
      .ext_rst_n(rst_n),
      .reset(reset)
  );

  blinky #(
      .PeriodMs(2000),
      .OnTimeMs(250)
  ) blinkMe (
      .clk  (clk),
      .reset(reset),
      .led  (led[0])
  );
endmodule
