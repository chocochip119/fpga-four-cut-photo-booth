`timescale 1ns / 1ps

module Image_ROM #(
    parameter int IMG_W = 640,
    parameter int IMG_H = 480,
    parameter int ADDR_WIDTH = (IMG_W * IMG_H <= 1)
                             ? 1 : $clog2(IMG_W * IMG_H),
    parameter string MEM_FILE = "sunset.mem"
)(
    input  logic                  clk,
    input  logic [ADDR_WIDTH-1:0] i_addr,
    output logic [15:0]           o_data
);

    logic [15:0] mem [0:IMG_W * IMG_H - 1];

    initial begin
        $readmemh(MEM_FILE, mem);
    end

    // Synchronous ROM read: o_data is updated one clock after i_addr is read.
    always_ff @(posedge clk) begin
        o_data <= mem[i_addr];
    end

endmodule
