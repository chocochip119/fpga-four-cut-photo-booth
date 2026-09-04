`timescale 1ns / 1ps

module UART_ROM_Reader #(
    parameter int IMG_W = 320,
    parameter int IMG_H = 240,
    parameter int ADDR_WIDTH = (IMG_W * IMG_H <= 1)
                             ? 1 : $clog2(IMG_W * IMG_H)
)(
    input  logic                  clk,
    input  logic                  rst,
    input  logic                  i_export_active,

    output logic [ADDR_WIDTH-1:0] o_rom_addr,
    input  logic [15:0]           i_rom_data,

    output logic [11:0]           o_pixel_data,
    output logic                  o_pixel_valid,
    input  logic                  i_pixel_ready
);

    localparam int PIXEL_COUNT = IMG_W * IMG_H;
    localparam logic [ADDR_WIDTH-1:0] LAST_ADDR = PIXEL_COUNT - 1;

    typedef enum logic [2:0] {
        R_IDLE,
        R_ROM_WAIT,
        R_LOAD_PIXEL,
        R_HOLD_PIXEL,
        R_WAIT_END
    } reader_state_t;

    reader_state_t state;

    always_ff @(posedge clk) begin
        if (rst) begin
            state         <= R_IDLE;
            o_rom_addr    <= '0;
            o_pixel_data  <= 12'h000;
            o_pixel_valid <= 1'b0;
        end
        else begin
            case (state)
                R_IDLE: begin
                    o_pixel_valid <= 1'b0;

                    if (i_export_active) begin
                        o_rom_addr <= '0;
                        state      <= R_ROM_WAIT;
                    end
                end

                // Image_ROM is synchronous. After changing the address,
                // wait until the requested data reaches i_rom_data.
                R_ROM_WAIT: begin
                    state <= R_LOAD_PIXEL;
                end

                R_LOAD_PIXEL: begin
                    // RGB565 -> RGB444
                    o_pixel_data <= {
                        i_rom_data[15:12],
                        i_rom_data[10:7],
                        i_rom_data[4:1]
                    };
                    o_pixel_valid <= 1'b1;
                    state         <= R_HOLD_PIXEL;
                end

                R_HOLD_PIXEL: begin
                    // Hold both data and valid until the UART side accepts them.
                    if (o_pixel_valid && i_pixel_ready) begin
                        o_pixel_valid <= 1'b0;

                        if (o_rom_addr == LAST_ADDR) begin
                            state <= R_WAIT_END;
                        end
                        else begin
                            o_rom_addr <= o_rom_addr + 1'b1;
                            state      <= R_ROM_WAIT;
                        end
                    end
                end

                R_WAIT_END: begin
                    o_pixel_valid <= 1'b0;

                    // Do not restart at address 0 while send_done is pending.
                    if (!i_export_active) begin
                        state <= R_IDLE;
                    end
                end

                default: begin
                    state         <= R_IDLE;
                    o_rom_addr    <= '0;
                    o_pixel_valid <= 1'b0;
                end
            endcase
        end
    end

endmodule
