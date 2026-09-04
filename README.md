# UART 사진 전송 패키지 파일 구분

이 패키지는 실제 UART RTL, ROM 연동 시험용 FPGA 코드, PC Python 프로그램을
서로 섞이지 않도록 세 폴더로 분리했다.

## 1. `01_FPGA_UART_RTL` — 실제 프로젝트에 사용하는 UART RTL

| 파일 | 역할 |
|---|---|
| `Send_Control.sv` | Status 4Byte 및 RGB444 Pixel 2Byte 전송 순서 제어 |
| `UART_Interface_Top.sv` | Send Control, Baud Generator, UART TX 연결 |
| `Baud_Generator.sv` | UART Baud tick 생성 |
| `UART_TX.sv` | 8bit 데이터를 UART 1bit TX 신호로 송신 |

이 네 파일이 사용자가 담당한 실제 UART 전송 블록이다. 최종 팀 프로젝트에서는
`UART_Interface_Top`의 Status와 Pixel 포트를 보드 외부 핀으로 빼지 말고,
System Controller와 이미지 처리 블록의 내부 신호에 연결해야 한다.

## 2. `02_FPGA_ROM_TEST` — UART 단독 검증용 코드

| 파일 | 역할 |
|---|---|
| `Image_ROM.sv` | `sunset.mem` RGB565 시험 이미지 저장 |
| `UART_ROM_Reader.sv` | ROM RGB565를 RGB444로 잘라 Pixel valid/ready로 전달 |
| `System_Controller.sv` | IDLE/EXPORT 상태를 만드는 시험용 Controller |
| `TOP_UART_ROM.sv` | 시험용 Controller, ROM, UART RTL을 연결한 Basys3 Top |
| `TOP_UART_ROM_Basys3.xdc` | 시험용 버튼, LED, UART TX 핀 설정 |
| `tb_TOP_UART_ROM.sv` | 전체 UART ROM 전송 시뮬레이션 |
| `sunset.mem` | 실제 보드 시험용 640×480 RGB565 데이터 |
| `sunset_2x2.mem` | 빠른 시뮬레이션용 2×2 데이터 |

이 폴더의 파일은 UART 전송을 실제 보드에서 단독 시험하기 위해 추가한 것이며,
최종 팀 설계의 Controller, Frame Buffer 또는 이미지 처리 블록을 대신하지 않는다.

현재 ROM 시험 비트스트림을 다시 만들 때는 다음 파일을 Vivado Design Sources에
함께 추가한다.

- `01_FPGA_UART_RTL`의 `.sv` 네 파일
- `02_FPGA_ROM_TEST`의 `Image_ROM.sv`, `UART_ROM_Reader.sv`,
  `System_Controller.sv`, `TOP_UART_ROM.sv`
- Memory Initialization File: `sunset.mem`
- Constraints: `TOP_UART_ROM_Basys3.xdc`
- Simulation Sources: `tb_TOP_UART_ROM.sv`, `sunset_2x2.mem`

Top Module은 `TOP_UART_ROM`이다.

## 3. `03_PC_PYTHON_WEB` — PC 수신·웹·QR 프로그램

| 파일/폴더 | 역할 |
|---|---|
| `uart_photo_web.py` | UART 수신, 사진 복원, 로컬 관리 화면, Cloudflare 실행 |
| `receive_uart_image.py` | UART Byte 해석 및 RGB444 PNG 변환 공통 코드 |
| `run_web.bat` | 웹 화면과 Cloudflare Tunnel 실행 |
| `run_settings.bat` | COM 포트와 서버를 설정하는 관리자 화면 열기 |
| `run_receiver.bat` | 웹 없이 UART 사진 파일만 받는 실행 파일 |
| `web_config.json` | Baud Rate, 해상도, State, 포트, 만료 시간 설정 |
| `requirements.txt` | Python 패키지 목록 |
| `templates/user.html` | 사용자에게 표시되는 State, 사진, QR 전용 화면 |
| `templates/dashboard.html` | COM, 서버 상태, 기록, 시험용 관리자 화면 |
| `templates/photo.html` | QR을 촬영한 휴대폰의 사진 저장 화면 |

### 실행 순서

1. Basys3에 준비된 시험 비트스트림을 Program한다.
2. `03_PC_PYTHON_WEB/run_web.bat`을 실행하면 사용자 화면이 열린다.
3. 관리자는 `run_settings.bat`을 실행해 별도의 설정 화면을 연다.
4. 설정 화면에서 `휴대폰 공개 주소 준비 완료`를 확인한다.
5. Basys3 COM 포트를 선택하고 `연결`을 누른다.
6. 설정 탭은 닫아도 되며 사용자 화면은 계속 유지한다.
7. FPGA의 EXPORT 버튼을 누른다.
8. 사진 수신 완료 후 사용자 화면에 표시되는 QR을 휴대폰으로 촬영한다.

### 화면 주소 구분

- 사용자 화면 `http://127.0.0.1:5000/`: 현재 State, 진행 상태, 사진, QR만 표시
- 관리자 설정 `http://127.0.0.1:5000/settings`: COM 연결, Cloudflare 상태,
  State 기록, 시험 기능 표시
- 휴대폰 공개 페이지: 사진과 다운로드 버튼만 표시

사용자 화면에는 COM 포트, 서버 주소, UART 기록, 시험 버튼이 나타나지 않는다.

`sunset.mem으로 시험` 버튼은 FPGA 없이 웹과 QR만 점검할 때 사용한다. 이 버튼은
`02_FPGA_ROM_TEST/sunset.mem`을 읽는다.

## QR 만료 동작

기본 공개 시간은 `web_config.json`의 `photo_expire_minutes` 값인 10분이다.
만료되면 사진과 QR을 숨기고 `QR 링크가 만료되었습니다`라고 표시한다. 시간을
바꾸려면 예를 들어 다음과 같이 수정한다.

```json
"photo_expire_minutes": 30
```

BAT 창을 닫으면 Cloudflare 공개 주소도 종료된다. FPGA RTL이나 비트스트림을
바꾸지 않고 Python 파일만 다시 실행해도 웹 화면 변경 사항은 적용된다.

## 실행 전 설치 확인

`03_PC_PYTHON_WEB` 폴더에서 `check_requirements.bat`을 실행하면 Python, pyserial, Pillow, Flask, qrcode, cloudflared 설치 여부를 확인할 수 있습니다.

PowerShell에서 직접 확인하려면:

```powershell
python --version
python -c "import serial, PIL, flask, qrcode; print('Python packages OK')"
cloudflared --version
```

Python 패키지가 빠졌다면:

```powershell
cd 03_PC_PYTHON_WEB
python -m pip install -r requirements.txt
```

## 640×480 기준

- 한 프레임: `640 × 480 = 307,200 Pixel`
- RGB444 UART payload: `2 Byte/Pixel`
- 한 프레임 Pixel payload: `614,400 Byte`
- Status는 별도 `4 Byte`
- 최종 이미지 전송 State: `FINAL_EXPORT = 5`
