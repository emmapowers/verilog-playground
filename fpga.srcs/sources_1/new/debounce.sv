
`include "config.svh"

module debounce #(
  int unsigned DebouncePeriod
) (
    input logic clk,
    input logic rst,
    input logic button,
    output logic debounced
);
  logic button1;
  logic button_final;
  logic last_state;
  logic [$clog2(DebouncePeriod)-1:0] counter;


  always_ff @(posedge clk) begin
    if (rst) begin
      button1 <= 0;
      button_final <= 0;
    end else begin
      button1 <= button;
      button_final <= button1;
    end
  end

  always_ff @(posedge clk) begin
    if (rst) begin
      counter <= '0;
      debounced <= 0;
      last_state <= 0;
    end else begin
      if (button_final != last_state) begin
        counter <= '0;
      end
      else if(counter == (DebouncePeriod - 1)) begin
        debounced <= button_final;
      end else begin
        counter <= counter + 1;
      end
      last_state <= button_final;
    end
  end


endmodule
