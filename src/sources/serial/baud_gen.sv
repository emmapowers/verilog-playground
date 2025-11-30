
module baud_gen (
  input logic clk,
  input logic rst,
  input logic [17:0] baud_rate,
  input logic oversample,
  output logic baud_en
);

localparam int unsigned MaxBaud = 115200;
logic [$clog2(MaxBaud)-1:0] baud_period;
logic [$clog2(MaxBaud)-1:0] counter;

function logic [$clog2(MaxBaud)-1:0] calculate_baud_period(logic [17:0] baud, logic oversample_16x);
  logic [$clog2(MaxBaud)-1:0] period;
  case (baud_rate)
    300:    period = (CLOCK_FREQ_HZ / 300);
    1200:   period = (CLOCK_FREQ_HZ / 1200);
    2400:   period = (CLOCK_FREQ_HZ / 2400);
    4800:   period = (CLOCK_FREQ_HZ / 4800);
    9600:   period = (CLOCK_FREQ_HZ / 9600);
    14400:  period = (CLOCK_FREQ_HZ / 14400);
    19200:  period = (CLOCK_FREQ_HZ / 19200);
    38400:  period = (CLOCK_FREQ_HZ / 38400);
    57600:  period = (CLOCK_FREQ_HZ / 57600);
    115200: period = (CLOCK_FREQ_HZ / 115200);
    default: period = (CLOCK_FREQ_HZ / 9600);  // Default to 9600
  endcase

  if (oversample_16x) period = period >> 4;
  return period;
endfunction

// Update baud rate on reset
always_ff @(posedge clk) begin
  if(rst) begin
    baud_period <= calculate_baud_period(baud_rate, oversample);
  end
end

always_ff @(posedge clk) begin
  if(rst) begin
    counter <= 0;
    baud_en <= 0;
  end else if (counter == (baud_period-1)) begin
    counter <= 0;
    baud_en <= 1;  
  end else begin
    baud_en <= 0;
    counter <= counter + 1;
  end
end

endmodule