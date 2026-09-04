`timescale 1ns / 1ps

module TOP_UART_ROM #(
    parameter int IMG_W = 640,
    parameter int IMG_H = 480,
    parameter int CLK_FREQ = 100_000_000,
    parameter int BAUD_RATE = 1_000_000,
    parameter string MEM_FILE = "sunset.mem"
)(
    input  logic clk,
    input  logic rst,
    input  logic i_export_btn,
    output logic o_uart_tx,
    output logic o_export_led
);

    localparam logic [3:0] STATE_IDLE   = 4'h0;
    localparam logic [3:0] STATE_EXPORT = 4'h5;
    localparam int ADDR_WIDTH = (IMG_W * IMG_H <= 1)
                              ? 1 : $clog2(IMG_W * IMG_H);

    logic btn_meta;
    logic btn_sync;
    logic btn_sync_d;
    logic export_start;

    logic [31:0] status_data;
    logic        status_valid;
    logic        status_ready;
    logic        send_done;
    logic        export_active;

    logic [ADDR_WIDTH-1:0] rom_addr;
    logic [15:0]           rom_data;
    logic [11:0]           pixel_data;
    logic                  pixel_valid;
    logic                  pixel_ready;

    always_ff @(posedge clk) begin
        if (rst) begin
            btn_meta   <= 1'b0;
            btn_sync   <= 1'b0;
            btn_sync_d <= 1'b0;
        end
        else begin
            btn_meta   <= i_export_btn;
            btn_sync   <= btn_meta;
            btn_sync_d <= btn_sync;
        end
    end

    assign export_start = btn_sync && !btn_sync_d;
    assign o_export_led = export_active;

    System_Controller #(
        .STATE_IDLE   (STATE_IDLE),
        .STATE_EXPORT (STATE_EXPORT)
    ) U_System_Controller (
        .clk             (clk),
        .rst             (rst),
        .i_export_start  (export_start),
        .i_status_ready  (status_ready),
        .i_send_done     (send_done),
        .o_status_data   (status_data),
        .o_status_valid  (status_valid),
        .o_export_active (export_active)
    );

    UART_ROM_Reader #(
        .IMG_W      (IMG_W),
        .IMG_H      (IMG_H),
        .ADDR_WIDTH (ADDR_WIDTH)
    ) U_UART_ROM_Reader (
        .clk             (clk),
        .rst             (rst),
        .i_export_active (export_active),
        .o_rom_addr      (rom_addr),
        .i_rom_data      (rom_data),
        .o_pixel_data    (pixel_data),
        .o_pixel_valid   (pixel_valid),
        .i_pixel_ready   (pixel_ready)
    );

    Image_ROM #(
        .IMG_W      (IMG_W),
        .IMG_H      (IMG_H),
        .ADDR_WIDTH (ADDR_WIDTH),
        .MEM_FILE   (MEM_FILE)
    ) U_Image_ROM (
        .clk    (clk),
        .i_addr (rom_addr),
        .o_data (rom_data)
    );

    UART_Interface_Top #(
        .IMG_W        (IMG_W),
        .IMG_H        (IMG_H),
        .CLK_FREQ     (CLK_FREQ),
        .BAUD_RATE    (BAUD_RATE),
        .STATE_EXPORT (STATE_EXPORT)
    ) U_UART_Interface_Top (
        .clk            (clk),
        .rst            (rst),
        .i_status_data  (status_data),
        .i_status_valid (status_valid),
        .o_status_ready (status_ready),
        .o_send_done    (send_done),
        .i_pixel_data   (pixel_data),
        .i_pixel_valid  (pixel_valid),
        .o_pixel_ready  (pixel_ready),
        .o_uart_tx      (o_uart_tx)
    );

endmodule
