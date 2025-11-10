

module bcd_to_seven_segment #(
    int unsigned Digits,
    int unsigned Width  = Digits * 4
) (
    input logic [Width-1:0] bcd,
    output logic [6:0] segments[Digits]
);
  always_comb begin
    for (int i = 0; i < Digits; i++) begin
      case (bcd[i*4+:4])
        4'd0: segments[i] = 7'b0111111;  // 0 → a b c d e f
        4'd1: segments[i] = 7'b0000110;  // 1 → b c
        4'd2: segments[i] = 7'b1011011;  // 2 → a b d e g
        4'd3: segments[i] = 7'b1001111;  // 3 → a b c d g
        4'd4: segments[i] = 7'b1100110;  // 4 → b c f g
        4'd5: segments[i] = 7'b1101101;  // 5 → a c d f g
        4'd6: segments[i] = 7'b1111101;  // 6 → a c d e f g
        4'd7: segments[i] = 7'b0000111;  // 7 → a b c
        4'd8: segments[i] = 7'b1111111;  // 8 → all segments
        4'd9: segments[i] = 7'b1101111;  // 9 → a b c d f g
        default: segments[i] = 7'b0000000;  // all off / blank
      endcase
    end
  end

endmodule
