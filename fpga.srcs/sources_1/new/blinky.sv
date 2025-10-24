`timescale 1ns / 1ps


module blinky(
    input logic clk,
    input logic reset,
    output logic led
    );
    // Parameters
    localparam int unsigned MAX = 50_000_000; // 100 MHz
    localparam int unsigned HALF = MAX / 2; // 50 Mhz
    localparam int unsigned WIDTH = $clog2(MAX);

    reg [WIDTH-1:0] counter;
    reg led_state;

    always_ff @( posedge clk) begin
        if (reset == 1) begin
            counter <= 0;
            led_state <= 0;
        end
        else begin
            if (counter == MAX) begin
                counter <= 0;
            end
            else begin
                counter <= counter + 1;
            end

            led_state <= counter >= HALF ? 1'b1 : 0'b0;
        end
        
    end

    assign led = led_state;


endmodule
