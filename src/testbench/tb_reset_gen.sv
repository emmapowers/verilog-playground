`timescale 1ns / 1ps

module tb_reset_gen;
  localparam int unsigned ResetCycles = 32;

  logic clk = 0;
  logic ext_rst_n = 1;
  logic reset;

  reset_gen #(
      .ResetCycles(ResetCycles)
  ) dut (
      .clk(clk),
      .ext_rst_n(ext_rst_n),
      .rst(reset)
  );

  always #5 clk = ~clk;

  initial begin
    repeat (20) @(posedge clk);
    ext_rst_n = 0;
    repeat (3) @(posedge clk);
    ext_rst_n = 1;
    repeat (20) @(posedge clk);
    ext_rst_n = 0;
    repeat (3) @(posedge clk);
    ext_rst_n = 1;
    repeat (20) @(posedge clk);
  end

endmodule
