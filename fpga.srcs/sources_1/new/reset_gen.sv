

module reset_gen #(
        int unsigned RESET_CYCLES = 32
    ) (
        input logic clk,
        input logic ext_rst_n,
        output logic reset
    );

    localparam int unsigned WIDTH = $clog2(RESET_CYCLES);

    reg [WIDTH-1:0] counter;
    reg reset_state;
    reg ext_rst_n0;
    reg ext_rst_n1;

    always_ff @(posedge clk) begin
        ext_rst_n0 <= ext_rst_n;
        ext_rst_n1 <= ext_rst_n0;
    end

    always_ff @(posedge clk) begin
        if (ext_rst_n1 == 0) begin
            counter <= 0;
            reset_state = 0;
        end
        else if (counter < RESET_CYCLES) begin
            count <= counter + 1
            reset_state <= 1
        end
    end

    assign reset = reset_state;

endmodule