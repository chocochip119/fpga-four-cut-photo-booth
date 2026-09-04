# UART ROM 전송 테스트 구성

## Vivado Design Sources

1. `Image_ROM.sv`
2. `UART_ROM_Reader.sv`
3. `System_Controller.sv`
4. `Send_Control.sv`
5. `Baud_Generator.sv`
6. `UART_TX.sv`
7. `UART_Interface_Top.sv`
8. `TOP_UART_ROM.sv`

`TOP_UART_ROM`을 Top Module로 지정한다.

## Memory Initialization File

- `sunset.mem`

전체 320×240 ROM 전송 또는 웹 샘플 이미지 시험 시 프로젝트 루트에 추가한다.
현재 Git에는 생성 가능한 전체 샘플 데이터 대신 Simulation용 `sunset_2x2.mem`만 포함한다.

## Simulation Sources

- `tb_TOP_UART_ROM.sv`
- `sunset_2x2.mem`

테스트벤치는 시뮬레이션 시간을 줄이기 위해 이미지 크기를 2×2, Baud Rate를
10 Mbps로 재정의하고 `sunset_2x2.mem`의 첫 네 픽셀을 사용한다. 실제 합성
설정은 `TOP_UART_ROM`의 기본값인 320×240, 1 Mbps이다.

## Constraints

- `TOP_UART_ROM_Basys3.xdc`

Basys3 연결:

- 가운데 버튼: Reset
- 위 버튼: EXPORT 시작
- LED0: EXPORT 진행 중 HIGH
- PROG/UART Micro-USB: PC UART 수신

## State와 Byte 순서

- IDLE State: `4'h0`
- EXPORT State: `4'h1`
- State 위치: `status_data[31:28]`
- Status 및 Pixel의 여러 Byte 전송 순서: LSB Byte First
- UART 한 Byte 내부의 Bit 전송 순서: LSB Bit First

State 값이 프로젝트 전체 정의와 다르면 `TOP_UART_ROM.sv`의
`STATE_IDLE`, `STATE_EXPORT`만 변경한다. 이 Top이 같은 값을 Controller와
Send Control 양쪽에 전달하므로 두 모듈의 판별값이 서로 어긋나지 않는다.

## Python에서 사진 받기

먼저 Python 패키지를 설치한다.

```powershell
pip install -r requirements.txt
```

장치 관리자에서 Basys3의 COM 포트를 확인한 뒤 다음처럼 실행한다.

```powershell
python receive_uart_image.py --port COM5 --baud 1000000
```

또는 `run_receiver.bat`을 실행하고 COM 포트를 입력한다. 프로그램이 UART
수신 대기 상태가 된 뒤 Basys3의 위 버튼을 눌러 EXPORT를 시작한다. 기본적으로
한 장을 수신해 `received_images` 폴더에 PNG로 저장한 뒤 종료한다.

여러 장을 계속 받으려면 다음 옵션을 추가한다.

```powershell
python receive_uart_image.py --port COM5 --continuous
```

수신 데이터는 다음 순서로 해석한다.

1. Status 4Byte를 Little-endian으로 복원한다.
2. `status[31:28] == 4'h1`이면 EXPORT로 판단한다.
3. RGB444 Pixel 76,800개, 총 153,600Byte를 수신한다.
4. Pixel마다 `B0 | ((B1 & 0x0F) << 8)`로 RGB444를 복원한다.
5. 각 4bit 색상 채널을 8bit로 확장해 320×240 PNG로 저장한다.

현재 프로토콜에는 별도의 Frame Header가 없으므로 Python 프로그램을 먼저
실행하고 그다음 EXPORT 버튼을 누른다. Pixel 전송 중간에 프로그램을 실행하면
Byte 경계를 자동으로 다시 찾을 수 없다.

## 웹 화면과 QR 시험

```powershell
pip install -r requirements.txt
run_web.bat
```

기본 웹 주소:

```text
http://127.0.0.1:5000
```

웹 화면에서 다음 순서로 사용한다.

1. COM 포트 목록에서 Basys3 포트를 선택한다.
2. `연결`을 누른다.
3. Python 웹 화면을 먼저 UART 수신 대기 상태로 둔다.
4. Basys3의 EXPORT 시작 조건을 발생시킨다.
5. 들어오는 Status마다 현재 State와 수신 기록이 갱신된다.
6. EXPORT State 다음의 153,600Byte를 한 장의 완성 사진으로 복원한다.
7. PC 화면에 사진, QR, `사진 다운로드` 버튼을 표시한다.
8. 휴대폰으로 QR을 찍으면 사진 페이지와 `사진 저장하기` 버튼이 열린다.

웹 화면의 `sunset.mem으로 시험` 기능은 프로젝트 루트에 전체 `sunset.mem`이 있을 때 사용할 수 있다.

QR은 PC 안의 웹 서버 주소를 사용한다. PC와 휴대폰이 같은 네트워크에 있어야
하며 Windows 방화벽 창이 뜨면 개인 네트워크에서 Python 접근을 허용한다.

State 값이나 이미지 크기가 달라지면 `web_config.json`을 수정한다.

```json
{
  "baud_rate": 1000000,
  "image_width": 320,
  "image_height": 240,
  "export_state": 1,
  "web_port": 5000,
  "qr_host": "auto",
  "state_names": {
    "0": "IDLE",
    "1": "EXPORT"
  }
}
```

PC에 유선 LAN과 Wi-Fi가 동시에 연결돼 QR의 IP가 잘못 선택되면 `ipconfig`에서
휴대폰과 같은 네트워크의 IPv4 주소를 확인하고 `qr_host`에 직접 입력한다.

```json
"qr_host": "192.168.0.10"
```

현재 UART 프로토콜에는 Frame Header가 없으므로 Pixel 전송 중간에 UART를
연결하면 Byte 경계를 자동으로 복구할 수 없다. 반드시 웹에서 UART를 먼저
연결한 다음 EXPORT를 시작한다.
