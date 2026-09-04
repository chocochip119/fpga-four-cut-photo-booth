`timescale 1ns / 1ps

module System_Controller #(
    parameter logic [3:0] STATE_IDLE   = 4'h0,
    parameter logic [3:0] STATE_EXPORT = 4'h5
)(
    input  logic        clk,
    input  logic        rst,
    input  logic        i_export_start,

    input  logic        i_status_ready,
    input  logic        i_send_done,

    output logic [31:0] o_status_data,
    output logic        o_status_valid,
    output logic        o_export_active
);

    typedef enum logic [2:0] {
        C_SEND_INITIAL_IDLE,
        C_IDLE,
        C_SEND_EXPORT,
        C_WAIT_EXPORT_DONE,
        C_SEND_RETURN_IDLE
    } controller_state_t;

    controller_state_t state, next_state;

    always_ff @(posedge clk) begin
        if (rst) begin
            state <= C_SEND_INITIAL_IDLE;
        end
        else begin
            state <= next_state;
        end
    end

    always_comb begin
        next_state = state;

        case (state)
            C_SEND_INITIAL_IDLE: begin
                if (i_status_ready) begin
                    next_state = C_IDLE;
                end
            end

            C_IDLE: begin
                if (i_export_start) begin
                    next_state = C_SEND_EXPORT;
                end
            end

            C_SEND_EXPORT: begin
                if (i_status_ready) begin
                    next_state = C_WAIT_EXPORT_DONE;
                end
            end

            C_WAIT_EXPORT_DONE: begin
                if (i_send_done) begin
                    next_state = C_SEND_RETURN_IDLE;
                end
            end

            C_SEND_RETURN_IDLE: begin
                if (i_status_ready) begin
                    next_state = C_IDLE;
                end
            end

            default: begin
                next_state = C_SEND_INITIAL_IDLE;
            end
        endcase
    end

    always_comb begin
        o_status_data   = {STATE_IDLE, 28'h000_0000};
        o_status_valid  = 1'b0;
        o_export_active = 1'b0;

        case (state)
            C_SEND_INITIAL_IDLE: begin
                o_status_data  = {STATE_IDLE, 28'h000_0000};
                o_status_valid = 1'b1;
            end

            C_IDLE: begin
                o_status_data = {STATE_IDLE, 28'h000_0000};
            end

            C_SEND_EXPORT: begin
                o_status_data   = {STATE_EXPORT, 28'h000_0000};
                o_status_valid  = 1'b1;
                o_export_active = 1'b1;
            end

            C_WAIT_EXPORT_DONE: begin
                o_status_data   = {STATE_EXPORT, 28'h000_0000};
                o_export_active = 1'b1;
            end

            C_SEND_RETURN_IDLE: begin
                o_status_data  = {STATE_IDLE, 28'h000_0000};
                o_status_valid = 1'b1;
            end

            default: begin
                // Keep default outputs.
            end
        endcase
    end

endmodule
