`include "config.svh"

/***
* The classic hunt-the bit game, with a couple of additions.
* The bits are displayed on the 16 LEDs for the nexys board, the buttons are the 16 switches below them.
* The buttons are debounced (in top) and only rising edges are counted as pressed (these switches make awful buttons!).
* There is also a points counter that is displayed on 7 segment displays (also in top).
* When a button is pushed a "hit" or "miss" is detected. Hit is when any button (you could do more than one at a time...) is in
* the same position as an active LED. A miss is if any of the pressed buttons was in a position without an active led.
* For the first 3 hits, the LED where the hit occurred is removed from the pattern and the point counter increments.
* You could hit more than one LED at once, but you would still get only one point. If you hit all 4 leds, the game breaks,
* so I suggest you don'do that.
* Once there is only 1 led left, every subsequent hit speeds up the led movement, until you lose, at which all the LEDs start flashing.
***/
module hunt_the_bit #(
    int unsigned MaxPeriod = `CLOCK_FREQ_HZ / 4
) (
    input logic clk,
    input logic rst,
    input logic [15:0] button,
    output logic [15:0] led,
    output logic [(8*$clog2(10))-1:0] points
);
  localparam int unsigned CounterWidth = $clog2(MaxPeriod);
  localparam [CounterWidth-1:0] MaxCount = '1;

  localparam logic [15:0] GameStartPattern = 16'h0F00;
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


  state_t next_state;
  state_t current_state = GAME_START;
  logic [15:0] led_state = '0;
  logic [CounterWidth-1:0] counter = 0;
  logic [CounterWidth-1:0] period = MaxCount;
  logic hit;
  logic miss;
  logic [15:0] hit_mask;
  logic [15:0] button_state = '0;
  logic [15:0] last_button_state = '0;

  // State Change Detection
  always_comb begin
    next_state = current_state;
    case (current_state)
      GAME_START: next_state = WAITING;
      WAITING: begin
        if (hit) next_state = HIT;
        else if (miss) next_state = LOSE_A;
        else if (counter == period) next_state = ROTATE;
      end
      HIT: next_state = ROTATE;
      ROTATE: next_state = WAITING;
      LOSE_A: if (counter == MaxCount / 2) next_state = LOSE_B;
      LOSE_B: if (counter == MaxCount / 2) next_state = LOSE_A;
      default:;
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

  // Button state
  always_ff @(posedge clk) begin
    if (rst) begin
      button_state <= '0;
      last_button_state <= '0;
    end else begin
      case (current_state)
        ROTATE: last_button_state <= button_state;
        WAITING: button_state <= button;
        default:;
      endcase
    end
  end

  // Hit/Miss
  always_comb begin
    automatic logic [15:0] pressed_buttons = '0;
    hit_mask = '0;
    hit = 0;
    miss = 0;
    if (!rst) begin
      // we only care about buttons on the rising edge
      pressed_buttons = button_state & ~last_button_state;

      hit_mask = led_state & pressed_buttons;
      miss = |(~led_state & pressed_buttons);
      hit = !miss && |hit_mask;
    end
  end

  // Period
  always_ff @(posedge clk) begin
    if (rst) begin
      period <= MaxCount;
    end else begin
      case (current_state)
        HIT: begin
          if ($countbits(led_state, '1) == 1) begin
            period <= period >> 1;
          end
        end
        default:;
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
        default:;
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
