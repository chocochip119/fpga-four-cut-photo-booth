# PC Python 웹 프로그램

`run_web.bat`을 실행하면 로컬 관리 화면, 사진 전용 서버, Cloudflare Tunnel이
함께 실행된다. 첫 화면은 사용자용 화면이며 COM 포트와 서버 설정은
`run_settings.bat`으로 별도 관리자 화면을 열어 처리한다. FPGA 없이 확인할
때만 관리자 화면의 `sunset.mem으로 시험` 버튼을 사용한다.

## UART를 유지한 UI State 디버깅

`run_debug.bat`을 실행하면 디버그 전용 사용자 화면이 열리고 기본 표시 State는
`STICKER`로 시작한다. 상단 버튼으로 `OPEN`, `SHOOT`, `CAPTURE`, `STICKER`,
`DRAW`, `FINAL_EXPORT`, `RESULT`를 즉시 선택하거나 `실제 State 사용`으로 돌아갈 수 있다.

이 기능은 FPGA의 실제 State를 변경하지 않으며 UART 연결도 끊지 않는다. 실제
`/api/status` 수신은 계속 유지하고 디버그 화면 안에서 `state_code/state_name`만
임시로 바꾼다. 따라서 Sticker ID, Draw Color, Marker 관련 값과 다른 Status bit는
실제 UART 수신값을 그대로 확인할 수 있다.
