
module seven_segment #(
    int unsigned NumDisplays   = 1,
    int unsigned RefreshPeriod
) (
    input logic clk,
    input logic rst,
    input logic [6:0] displays[NumDisplays],
    input logic dots[NumDisplays],
    output logic [NumDisplays-1:0] annode,
    output logic [6:0] segments,
    output logic dot
);
  localparam int unsigned DisplayTime = (RefreshPeriod / NumDisplays);
  localparam int unsigned MaxCount = DisplayTime - 1;
  localparam int unsigned DisplayEnableInitBits = {{(NumDisplays - 1) {1'b1}}, 1'b0};

  logic [NumDisplays-1:0] display_enable = DisplayEnableInitBits;
  logic [$clog2(DisplayTime)-1:0] refresh_counter = '0;

  //Enable Displays
  always_ff @(posedge clk) begin
    if (rst) begin
      display_enable  <= DisplayEnableInitBits;
      refresh_counter <= 0;
    end else if (refresh_counter == MaxCount) begin
      display_enable  <= {display_enable, display_enable} >> 1;
      refresh_counter <= 0;
    end else begin
      refresh_counter <= refresh_counter + 1;
    end
  end

  //Route segments to enabled display
  always_comb begin
    if (rst) begin
      segments = '1;
      dot = 1;
    end else begin
      segments = '1;
      dot = 1;
      for (int i = 0; i < NumDisplays; i++) begin
        if (!display_enable[i]) begin
          segments = ~displays[i][6:0];
          dot = ~dots[i];
        end
      end
    end
  end

  assign annode = display_enable;

endmodule
