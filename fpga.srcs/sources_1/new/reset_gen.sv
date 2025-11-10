

module reset_gen #(
    int unsigned ResetCycles = 32
) (
    input  logic clk,
    input  logic ext_rst_n,
    output logic rst
);

  localparam int unsigned Width = $clog2(ResetCycles);
  localparam logic [Width-1:0] CountMax = (ResetCycles == 0) ? 0 : ResetCycles - 1;

  reg [Width-1:0] counter = '0;
  reg rst_state = 1'b1;
  reg ext_rst_n0 = 1'b1;
  reg ext_rst_n1 = 1'b1;

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
      counter   <= 0;
      rst_state <= 1;
    end  // Both ext_rst_n and ext_rst_n1 need to be out of reset
    else if (!ext_rst_n1) begin
      counter   <= 0;
      rst_state <= 1;
    end else if (counter != CountMax) begin
      counter   <= counter + 1;
      rst_state <= 1;
    end else begin
      rst_state <= 0;
    end
  end

  assign rst = rst_state;

endmodule
