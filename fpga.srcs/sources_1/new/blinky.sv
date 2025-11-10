`include "config.svh"

module blinky #(
    int unsigned PeriodMs = 1000,
    int unsigned OnTimeMs = PeriodMs / 2  // 50 Mhz
) (
    input  logic clk,
    input  logic reset,
    output logic led
);
  // Parameters
  localparam int unsigned TickTime = `CLOCK_FREQ_HZ / 1000;
  localparam int unsigned Period = PeriodMs * TickTime;
  localparam int unsigned OnTime = OnTimeMs * TickTime;
  localparam int unsigned Width = $clog2(Period);
  localparam int unsigned CountMax = Period - 1;

  reg [Width-1:0] counter;
  reg led_state;

  always_ff @(posedge clk) begin
    if (reset == 1) begin
      counter   <= 0;
      led_state <= 0;
    end else begin
      if (counter == CountMax) begin
        counter <= 0;
      end else begin
        counter <= counter + 1;
      end

      led_state <= counter < OnTime ? 1 : 0;
    end
  end

  assign led = led_state;

endmodule
