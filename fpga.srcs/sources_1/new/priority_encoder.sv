

module priority_encoder #(
    int N
) (
    input logic [N-1:0] onehot,
    output logic [$clog2(N)-1:0] index
);

  always_comb begin
    for (int i = 0; i < N; i++) begin
      if (onehot[i]) index = i;
    end
  end

endmodule
