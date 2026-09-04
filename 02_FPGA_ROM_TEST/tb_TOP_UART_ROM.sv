`timescale 1ns / 1ps

module tb_TOP_UART_ROM;

    localparam int CLK_FREQ   = 100_000_000;
    localparam int BAUD_RATE  = 10_000_000;
    localparam int CLK_PERIOD = 10;
    localparam int BIT_PERIOD = 1_000_000_000 / BAUD_RATE;

    logic clk;
    logic rst;
    logic export_btn;
    logic uart_tx;
    logic export_led;

    logic [7:0] captured_bytes [0:31];
    logic [7:0] rx_byte;
    int captured_count;

    TOP_UART_ROM #(
        .IMG_W      (2),
        .IMG_H      (2),
        .CLK_FREQ   (CLK_FREQ),
        .BAUD_RATE  (BAUD_RATE),
        .MEM_FILE   ("sunset_2x2.mem")
    ) dut (
        .clk          (clk),
        .rst          (rst),
        .i_export_btn (export_btn),
        .o_uart_tx    (uart_tx),
        .o_export_led (export_led)
    );

    initial begin
        clk = 1'b0;
        forever #(CLK_PERIOD / 2) clk = ~clk;
    end

    task automatic receive_uart_byte(output logic [7:0] data);
        int bit_index;
        begin
            data = 8'h00;
            @(negedge uart_tx);
            #(BIT_PERIOD / 2);
            if (uart_tx !== 1'b0) $fatal(1, "UART start-bit error");
            #(BIT_PERIOD);
            for (bit_index = 0; bit_index < 8; bit_index++) begin
                data[bit_index] = uart_tx;
                #(BIT_PERIOD);
            end
            if (uart_tx !== 1'b1) $fatal(1, "UART stop-bit error");
        end
    endtask

    initial begin
        captured_count = 0;
        forever begin
            receive_uart_byte(rx_byte);
            captured_bytes[captured_count] = rx_byte;
            $display("[%0t] UART Byte[%0d] = %02h", $time, captured_count, rx_byte);
            captured_count = captured_count + 1;
        end
    end

    task automatic check_byte(input int index, input logic [7:0] expected);
        begin
            if (captured_bytes[index] !== expected)
                $fatal(1, "Byte %0d mismatch: expected=%02h actual=%02h", index, expected, captured_bytes[index]);
        end
    endtask

    initial begin
        rst        = 1'b1;
        export_btn = 1'b0;
        repeat (5) @(posedge clk);
        @(negedge clk);
        rst = 1'b0;

        wait (captured_count == 4);
        repeat (3) @(posedge clk);
        export_btn = 1'b1;
        repeat (4) @(posedge clk);
        export_btn = 1'b0;

        wait (captured_count == 20);
        repeat (3) @(posedge clk);

        check_byte(0, 8'h00); check_byte(1, 8'h00); check_byte(2, 8'h00); check_byte(3, 8'h00);

        // FINAL_EXPORT status = 32'h5000_0000, LSB byte first.
        check_byte(4, 8'h00); check_byte(5, 8'h00); check_byte(6, 8'h00); check_byte(7, 8'h50);

        // RGB565 16'h53FB -> RGB444 12'h57D -> 7D 05.
        check_byte(8, 8'h7D);  check_byte(9, 8'h05);
        check_byte(10, 8'h7D); check_byte(11, 8'h05);
        check_byte(12, 8'h7D); check_byte(13, 8'h05);
        check_byte(14, 8'h7D); check_byte(15, 8'h05);

        check_byte(16, 8'h00); check_byte(17, 8'h00); check_byte(18, 8'h00); check_byte(19, 8'h00);

        if (export_led !== 1'b0) $fatal(1, "Controller did not return to IDLE");

        $display("=====================================================");
        $display("PASS: TOP_UART_ROM integrated UART test");
        $display("=====================================================");
        #100;
        $finish;
    end

    initial begin
        #100_000;
        $fatal(1, "Simulation timeout");
    end

endmodule
