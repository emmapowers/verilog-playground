`include "config.svh"

module hunt_the_bit #(
    int unsigned MaxPeriod = `CLOCK_FREQ_HZ
) (
    input logic clk,
    input logic rst,
    input logic [15:0] button,
    output logic [15:0] led,
    output logic [7:0] score,
    output logic [(8*$clog2(10))-1:0] points
);
  localparam int unsigned MaxCount = MaxPeriod - 1;
  localparam int unsigned CounterWidth = $clog2(MaxPeriod);

  localparam logic [15:0] GameStartPattern = 16'h0700;
  localparam logic [15:0] LoseAPattern = 16'hFFFF;
  localparam logic [15:0] LoseBPattern = 16'h0000;

  typedef enum logic [4:0] {
    GAME_START,
    WAITING,
    ROTATE,
    HIT,
    LOSE_A,
    LOSE_B
  } state_t;


  state_t next_state = GAME_START;
  state_t current_state = GAME_START;
  logic [15:0] led_state = '0;
  logic [CounterWidth-1:0] counter = 0;
  logic [CounterWidth-1:0] period = MaxCount;
  logic hit;
  logic miss;
  logic [15:0] hit_mask;

  // State Change Detection
  always_comb begin
    next_state = current_state;
    case (current_state)
      GAME_START: next_state = WAITING;
      WAITING: begin
        if (counter == period) next_state = ROTATE;
        if (hit) next_state = HIT;
        if (miss) next_state = LOSE_A;
      end
      HIT: next_state = ROTATE;
      ROTATE: next_state = WAITING;
      LOSE_A: if (counter == MaxCount / 2) next_state = LOSE_A;
      LOSE_B: if (counter == MaxCount / 2) next_state = LOSE_A;
      default: next_state = current_state;
    endcase
  end

  // State transition
  always_ff @(posedge clk) begin
    if (rst) begin
      current_state <= GAME_START;
    end else begin
      current_state <= next_state;
    end
  end

  // Counter
  always_ff @(posedge clk) begin
    if (rst) begin
      counter <= 0;
    end else if (next_state != current_state) begin
      counter <= '0;
    end else begin
      counter <= counter + 1;
    end
  end

  // LED State
  always_ff @(posedge clk) begin
    if (rst) begin
      led_state <= '0;
    end else begin
      case (current_state)
        GAME_START: led_state <= GameStartPattern;
        HIT: begin
          if ($countbits(led_state, '1) != 1) begin
            led_state <= led_state & ~hit_mask;
          end
        end
        ROTATE: led_state <= ({led_state, led_state} >> 1);
        default: ;
      endcase
    end
  end

  // Hit/Miss
  always_comb begin
    hit_mask = '0;
    hit = 0;
    miss = 0;
    if (!rst) begin
      hit_mask = led_state & button;
      miss = |(~led_state & button);
      hit = !miss && |hit_mask;
    end
  end

  // Period
  always_ff @(posedge clk) begin
    if (rst) begin
      period <= MaxPeriod;
    end else begin
      case (current_state)
        HIT: begin
          if ($countbits(led_state, '1) == 1) begin
            period <= period >> 1;
          end
        end
        default: ;
      endcase
    end
  end

  // Point Counter
  always_ff @(posedge clk) begin
    if (rst) begin
      points <= '0;
    end else begin
      case (current_state)
        HIT: points <= points + 1;
      endcase
    end
  end

  // LED output
  always_comb begin
    led = '0;
    case (current_state)
      GAME_START: led = GameStartPattern;
      WAITING: led = led_state;
      ROTATE: led = led_state;
      LOSE_A: led = LoseAPattern;
      LOSE_B: led = LoseBPattern;
      default: led = '0;
    endcase
  end

endmodule
