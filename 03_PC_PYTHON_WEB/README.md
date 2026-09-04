# PC Python 웹 프로그램

`run_web.bat`을 실행하면 로컬 관리 화면, 사진 전용 서버, Cloudflare Tunnel이
함께 실행된다. 첫 화면은 사용자용 화면이며 COM 포트와 서버 설정은
`run_settings.bat`으로 별도 관리자 화면을 열어 처리한다. FPGA 없이 확인할
때만 관리자 화면의 `sunset.mem으로 시험` 버튼을 사용한다.

## 실행 전 필수 설치 확인

가장 빠른 방법은 `check_requirements.bat` 실행입니다.

직접 확인:

```powershell
python --version
python -c "import serial, PIL, flask, qrcode; print('Python packages OK')"
cloudflared --version
```

빠진 Python 패키지 설치:

```powershell
python -m pip install -r requirements.txt
```

현재 기본 이미지 크기는 **640×480**이며 `web_config.json`, UART CLI 기본값, FPGA UART RTL 기본 파라미터가 동일하게 맞춰져 있습니다.

## UART 유지 State Override

`run_web.bat`으로 서버와 UART를 실행/연결한 뒤 `run_debug.bat`을 실행합니다. 기본 화면은 `STICKER`이며, `실제 State 사용 / OPEN / SHOOT / CAPTURE / STICKER / DRAW / FINAL_EXPORT / RESULT`를 즉시 전환할 수 있습니다. 실제 UART 수신과 Status 값은 계속 유지되고 사용자 화면의 State 표시만 덮어씁니다.
