# FPGA ROM 시험 전용

UART 블록을 Basys3에서 단독 검증하기 위한 시험용 소스다. 최종 팀 프로젝트에서는
실제 System Controller, Frame Buffer, 이미지 처리 블록으로 교체한다.

## 임의 사진을 `sunset.mem`으로 변환

`image_to_mem.py`를 사용하면 JPG/PNG 이미지를 현재 ROM/Web 시험 기준인
**640×480 RGB565** `.mem` 파일로 변환할 수 있다.

```powershell
python image_to_mem.py test.png
```

기본 출력 파일은 현재 폴더의 `sunset.mem`이다. 다른 이름으로 저장하려면 다음과 같이
실행한다.

```powershell
python image_to_mem.py test.png -o sample.mem
```

정상 변환되면 Pixel 수가 다음과 같이 표시된다.

```text
Pixel 수: 307200
```

생성된 `sunset.mem`은 FPGA ROM 시험에 사용할 수 있으며,
`03_PC_PYTHON_WEB`의 관리자 화면에서 **`sunset.mem으로 시험`** 버튼을 눌러
FPGA 없이도 이미지 복원, Web UI, QR 및 다운로드 기능을 확인할 수 있다.
