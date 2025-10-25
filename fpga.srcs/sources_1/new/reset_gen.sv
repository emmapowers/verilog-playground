

module reset_gen #(
    int unsigned ResetCycles = 32
) (
    input  logic clk,
    input  logic ext_rst_n,
    output logic reset
);

  localparam int unsigned Width = $clog2(ResetCycles);
  localparam logic [Width-1:0] CountMax = (ResetCycles == 0) ? 0 : ResetCycles - 1;

  reg [Width-1:0] counter;
  reg reset_state;
  reg ext_rst_n0;
  reg ext_rst_n1;

  always_ff @(posedge clk or negedge ext_rst_n) begin
    if (!ext_rst_n) begin
      ext_rst_n0 <= 0;
      ext_rst_n1 <= 0;
    end else begin
      ext_rst_n0 <= ext_rst_n;
      ext_rst_n1 <= ext_rst_n0;
    end
  end

  always_ff @(posedge clk or negedge ext_rst_n) begin
    if (!ext_rst_n) begin
      counter <= 0;
      reset_state <= 1;
    end  // Both ext_rst_n and ext_rst_n1 need to be out of reset
    else if (!ext_rst_n1) begin
      counter <= 0;
      reset_state <= 1;
    end else if (counter != ResetCycles) begin
      counter <= counter + 1;
      reset_state <= 1;
    end else begin
      reset_state <= 0;
    end
  end

  assign reset = reset_state;

endmodule
