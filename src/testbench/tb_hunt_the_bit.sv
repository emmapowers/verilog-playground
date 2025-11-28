`timescale 1ns / 1ps

module tb_hunt_the_bit;
  localparam int unsigned MaxPeriod = 10;

  logic clk = 0;
  logic reset = 1;
  logic [15:0] led = '0;
  logic [15:0] button = '0;
  logic [15:0] temp = '0;

  hunt_the_bit #(
  // .MaxPeriod(MaxPeriod)
  ) dut (
      .clk(clk),
      .reset(reset),
      .led(led),
      .button(temp)
  );

  always #5 clk = ~clk;

  initial begin
    repeat (32) @(posedge clk);
    reset = 0;
    repeat (200) @(posedge clk);
    button <= 16'h08;
  end

endmodule
