# PC Python 웹 프로그램

`run_web.bat`을 실행하면 로컬 관리 화면, 사진 전용 서버, Cloudflare Tunnel이
함께 실행된다. 첫 화면은 사용자용 화면이며 COM 포트와 서버 설정은
`run_settings.bat`으로 별도 관리자 화면을 열어 처리한다. FPGA 없이 확인할
때만 관리자 화면의 `sunset.mem으로 시험` 버튼을 사용한다.

현재 기본 이미지 크기는 **640×480**이며 `web_config.json`, UART CLI 기본값,
FPGA UART RTL 기본 파라미터가 동일하게 맞춰져 있다.

## 처음 한 번 설치

가장 간단한 방법은 다음 파일을 실행하는 것이다.

```text
install_requirements.bat
```

이 파일은 다음을 한 번에 처리한다.

- `requirements.txt`의 Python 패키지 설치
  - pyserial
  - Pillow
  - qrcode
  - Flask
- `cloudflared`가 없으면 `winget`으로 Cloudflare Tunnel 실행파일 설치

`cloudflared`는 Python 패키지가 아니므로 `pip install -r requirements.txt`만으로는
설치되지 않는다. `install_requirements.bat`에서 별도로 설치한다.

수동 설치:

```powershell
python -m pip install -r requirements.txt
winget install --id Cloudflare.cloudflared -e
```

## 실행 전 필수 설치 확인

가장 빠른 방법은 `check_requirements.bat` 실행이다. 이 파일은 `python.exe`가 없으면
`py.exe`도 확인하고 Python 패키지와 `cloudflared` 설치 여부를 표시한다.

직접 확인:

```powershell
python --version
python -c "import serial, PIL, flask, qrcode; print('Python packages OK')"
cloudflared --version
```

`cloudflared`를 방금 설치했다면 현재 CMD/PowerShell의 PATH가 아직 갱신되지 않았을 수
있으므로 창을 닫고 새로 연 뒤 다시 확인한다.

## UART 유지 State Override

`run_web.bat`으로 서버와 UART를 실행/연결한 뒤 `run_debug.bat`을 실행한다. 기본 화면은
`STICKER`이며, `실제 State 사용 / OPEN / SHOOT / CAPTURE / STICKER / DRAW /
FINAL_EXPORT / RESULT`를 즉시 전환할 수 있다.

이 기능은 FPGA의 실제 State를 변경하지 않는다. 실제 UART 수신과 Status 값은 계속
유지하고 사용자 화면에 표시되는 `state_code/state_name`만 덮어쓴다. 따라서
Sticker ID, Sticker Size, Draw Color, Marker 관련 bit 등 나머지 Status 값은 실제 UART
수신값을 그대로 확인할 수 있다.
