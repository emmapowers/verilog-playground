`timescale 1ns / 1ps

module tb_blinky;
  localparam int unsigned Period = 10;
  localparam int unsigned OnTime = 2;
  localparam int unsigned Ms = 10_000_000 / 100;

  logic clk = 0;
  logic led = 0;
  logic reset = 1;

  blinky #(
      .PeriodMs(Period),
      .OnTimeMs(OnTime)
  ) dut (
      .clk  (clk),
      .reset(reset),
      .led  (led)
  );

  always #5 clk = ~clk;

  initial begin
    repeat (32) @(posedge clk);
    reset = 0;
    repeat (10 * Ms) @(posedge clk);
    reset = 1;
    repeat (32) @(posedge clk);
    reset = 0;
    repeat (10 * Ms) @(posedge clk);
  end

endmodule
