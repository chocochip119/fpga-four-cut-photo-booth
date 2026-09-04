# fpga-four-cut-photo-booth

Basys3 FPGA 기반 네컷 포토부스 프로젝트의 UART 이미지 전송 및 Python 웹 UI 통합 코드입니다.

## 현재 UART 통합 범위

- Basys3 100 MHz 기준 UART TX
- 1 Mbps 기본 Baud Rate
- `status_data[31:28]` 기반 State 전송
- EXPORT State에서 RGB444 12-bit Pixel을 2 Byte로 전송
- ROM 기반 320×240 이미지 전송 테스트 Top
- Vivado 통합 Testbench 및 Basys3 XDC
- Python `pyserial` 이미지 수신 및 PNG 저장
- Flask 웹 UI에서 COM 포트 연결, State 확인, 이미지 표시, QR 생성

## UART 데이터 형식

- IDLE State: `4'h0`
- EXPORT State: `4'h1`
- State 위치: `status_data[31:28]`
- Status: 4 Byte, LSB Byte First
- RGB444 Pixel: 2 Byte, LSB Byte First
- UART 한 Byte 내부 Bit: LSB Bit First

Pixel은 다음 순서로 전송됩니다.

```text
Byte 0 = pixel[7:0]
Byte 1 = {4'b0000, pixel[11:8]}
```

## Vivado 테스트

Design Sources:

```text
Image_ROM.sv
UART_ROM_Reader.sv
System_Controller.sv
Send_Control.sv
Baud_Generator.sv
UART_TX.sv
UART_Interface_Top.sv
TOP_UART_ROM.sv
```

Simulation Sources:

```text
tb_TOP_UART_ROM.sv
sunset_2x2.mem
```

Constraints:

```text
TOP_UART_ROM_Basys3.xdc
```

`TOP_UART_ROM`을 Top Module로 사용합니다.

전체 320×240 ROM 전송을 합성하거나 웹의 샘플 이미지 기능을 사용할 경우 프로젝트 루트에 `sunset.mem`을 추가합니다. `sunset.mem`은 생성 가능한 샘플 이미지 데이터이므로 현재 Git 커밋에는 포함하지 않았습니다.

## Python 실행

```powershell
pip install -r requirements.txt
python receive_uart_image.py --port COM5 --baud 1000000
```

웹 UI:

```powershell
run_web.bat
```

또는:

```powershell
python uart_photo_web.py
```

기본 웹 주소는 `http://127.0.0.1:5000`입니다.

상세 사용 순서는 [README_사용순서.md](README_사용순서.md)를 참고하세요.
