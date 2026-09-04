## 100 MHz oscillator
set_property PACKAGE_PIN W5 [get_ports clk]
set_property IOSTANDARD LVCMOS33 [get_ports clk]
create_clock -add -name sys_clk_pin -period 10.000 -waveform {0 5.000} [get_ports clk]

## Center button: active-high reset
set_property PACKAGE_PIN U18 [get_ports rst]
set_property IOSTANDARD LVCMOS33 [get_ports rst]

## Up button: begin EXPORT
set_property PACKAGE_PIN T18 [get_ports i_export_btn]
set_property IOSTANDARD LVCMOS33 [get_ports i_export_btn]

## USB-UART TX to PC
set_property PACKAGE_PIN A18 [get_ports o_uart_tx]
set_property IOSTANDARD LVCMOS33 [get_ports o_uart_tx]

## LED0: stays high while the frame is being exported
set_property PACKAGE_PIN U16 [get_ports o_export_led]
set_property IOSTANDARD LVCMOS33 [get_ports o_export_led]
