`include "config.svh"

module top (
    input rst_n,
    input clk,
    output [15:0] led,
    input [15:0] sw,
    output [6:0] seg,
    output dp,
    output [7:0] an
);
  localparam int unsigned NumDigits = 8;
  localparam int unsigned DecimalWidth = $rtoi($ceil(NumDigits * $clog2(10)));
  logic [DecimalWidth-1:0] points;
  logic [(NumDigits*4)-1:0] bcd;
  logic [6:0] segment_digits[NumDigits];
  logic dots[NumDigits] = '{default: '0};
  logic [15:0] buttons;
  logic rst;
  
  reset_gen rgen (
      .clk(clk),
      .ext_rst_n(rst_n),
      .rst(rst)
  );

  generate
    for (genvar i = 0; i < 16; i++) begin : debouncers
      debounce #(
        .DebouncePeriod(`MS * 10)
      ) bd (
        .clk(clk),
        .rst(rst),
        .button(sw[i]),
        .debounced(buttons[i])
      );
    end
  endgenerate

  hunt_the_bit #(
      .MaxPeriod(100_000_000 / 4)
  ) hunt (
      .clk(clk),
      .rst(rst),
      .led(led),
      .button(buttons),
      .points(points)
  );

  bcd_encoder #(
      .DecimalWidth(DecimalWidth),
      .MaxDigits(NumDigits)
  ) bcd_it (
      .decimal(points),
      .bcd(bcd)
  );

  bcd_to_seven_segment #(
      .Digits(NumDigits)
  ) segmenter (
      .bcd(bcd),
      .segments(segment_digits)
  );

  seven_segment #(
      .NumDisplays  (NumDigits),
      .RefreshPeriod(1 * `MS)
  ) display (
      .clk(clk),
      .rst(rst),
      .displays(segment_digits),
      .dots(dots),
      .annode(an),
      .segments(seg),
      .dot(dp)
  );
endmodule
