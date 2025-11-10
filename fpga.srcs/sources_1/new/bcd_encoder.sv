

module bcd_encoder #(
    int unsigned DecimalWidth,
    int unsigned MaxDigits
) (
    input logic [DecimalWidth-1:0] decimal,
    output logic [(MaxDigits * 4)-1:0] bcd
);
  localparam int unsigned WorkingDigits = $rtoi($ceil(DecimalWidth * $log10(2)));
  logic [(WorkingDigits * 4):0] bcd_tmp;

  always_comb begin
    bcd_tmp = '0;

    for (int bitNum = DecimalWidth - 1; bitNum >= 0; bitNum--) begin
      for (int d = 0; d < WorkingDigits; d++) begin
        if (bcd_tmp[d*4+:4] >= 5) bcd_tmp[d*4+:4] = bcd_tmp[d*4+:4] + 3;
      end

      bcd_tmp = bcd_tmp << 1;
      bcd_tmp[0] = decimal[bitNum];
    end
  end

  assign bcd = bcd_tmp[(MaxDigits*4)-1:0];

endmodule
