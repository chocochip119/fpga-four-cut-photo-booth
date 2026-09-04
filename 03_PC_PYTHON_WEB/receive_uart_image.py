#!/usr/bin/env python3
"""Receive an RGB444 frame from the FPGA UART and save it as a PNG."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

from PIL import Image


STATE_NAMES = {
    0x0: "OPEN",
    0x1: "SHOOT",
    0x2: "CAPTURE",
    0x3: "STICKER",
    0x4: "DRAW",
    0x5: "FINAL_EXPORT",
    0x6: "RESULT",
}
STATE_EXPORT = 0x5
STATUS_SIZE = 4


def read_exact(stream: BinaryIO, size: int, show_progress: bool = False) -> bytes:
    """Read exactly ``size`` bytes from a stream while tolerating timeout reads."""
    received = bytearray()
    next_percent = 10
    while len(received) < size:
        chunk = stream.read(size - len(received))
        if not chunk:
            continue
        received.extend(chunk)
        if show_progress:
            percent = len(received) * 100 // size
            while percent >= next_percent and next_percent <= 100:
                print(f"  수신 진행: {next_percent}%")
                next_percent += 10
    return bytes(received)


def parse_status(raw_status: bytes) -> tuple[int, int]:
    """Decode four little-endian status bytes and return the status word and State."""
    if len(raw_status) != STATUS_SIZE:
        raise ValueError("Status는 정확히 4Byte여야 합니다.")
    status = int.from_bytes(raw_status, byteorder="little", signed=False)
    state = (status >> 28) & 0xF
    return status, state


def rgb444_payload_to_image(payload: bytes, width: int, height: int) -> Image.Image:
    """Convert the UART two-byte-per-pixel RGB444 payload into an RGB888 image."""
    pixel_count = width * height
    expected_size = pixel_count * 2
    if len(payload) != expected_size:
        raise ValueError(f"Pixel 데이터 크기 오류: expected={expected_size}, actual={len(payload)}")

    rgb888 = bytearray(pixel_count * 3)
    for index in range(pixel_count):
        low_byte = payload[index * 2]
        high_byte = payload[index * 2 + 1]
        rgb444 = low_byte | ((high_byte & 0x0F) << 8)
        red4 = (rgb444 >> 8) & 0xF
        green4 = (rgb444 >> 4) & 0xF
        blue4 = rgb444 & 0xF
        rgb888[index * 3] = (red4 << 4) | red4
        rgb888[index * 3 + 1] = (green4 << 4) | green4
        rgb888[index * 3 + 2] = (blue4 << 4) | blue4
    return Image.frombytes("RGB", (width, height), bytes(rgb888))


def make_output_path(output_dir: Path) -> Path:
    """Create the output directory and return a timestamped PNG path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return output_dir / f"uart_image_{timestamp}.png"


def receive_from_uart(args: argparse.Namespace) -> None:
    """Receive status and FINAL_EXPORT payloads from a serial port and save images."""
    try:
        import serial
    except ImportError as exc:
        raise SystemExit("pyserial이 없습니다. 먼저 'pip install -r requirements.txt'를 실행하세요.") from exc

    payload_size = args.width * args.height * 2
    output_dir = Path(args.output_dir)

    with serial.Serial(
        port=args.port,
        baudrate=args.baud,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.5,
    ) as uart:
        if not args.keep_buffer:
            uart.reset_input_buffer()

        print(f"UART 연결: {args.port}, {args.baud} baud, 8N1")
        print("FPGA의 FINAL_EXPORT State를 기다립니다. Ctrl+C를 누르면 종료됩니다.")
        saved_count = 0

        while True:
            raw_status = read_exact(uart, STATUS_SIZE)
            status, state = parse_status(raw_status)
            state_name = STATE_NAMES.get(state, f"UNKNOWN({state:#x})")
            print(f"Status 수신: 0x{status:08X}, State={state_name}")
            if state != STATE_EXPORT:
                continue

            print(f"Pixel 수신 시작: {args.width}x{args.height}, {payload_size}Byte")
            payload = read_exact(uart, payload_size, show_progress=True)
            image = rgb444_payload_to_image(payload, args.width, args.height)
            output_path = make_output_path(output_dir)
            image.save(output_path)
            if args.save_raw:
                output_path.with_suffix(".bin").write_bytes(payload)
            saved_count += 1
            print(f"사진 저장 완료: {output_path.resolve()}")
            if not args.continuous:
                break

        print(f"총 {saved_count}장 저장했습니다.")


def convert_payload_file(args: argparse.Namespace) -> None:
    """Convert a saved raw RGB444 payload file into a PNG image."""
    payload = Path(args.input_bin).read_bytes()
    image = rgb444_payload_to_image(payload, args.width, args.height)
    output_path = make_output_path(Path(args.output_dir))
    image.save(output_path)
    print(f"사진 저장 완료: {output_path.resolve()}")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for UART reception or raw payload conversion."""
    parser = argparse.ArgumentParser(description="FPGA UART의 RGB444 Pixel 데이터를 받아 PNG로 저장합니다.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--port", help="Windows COM 포트 예: COM5")
    source.add_argument("--input-bin", help="UART 없이 변환할 Pixel payload 파일(2Byte/Pixel)")
    parser.add_argument("--baud", type=int, default=1_000_000)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--output-dir", default="received_images")
    parser.add_argument("--continuous", action="store_true", help="한 장 저장한 뒤 종료하지 않고 다음 FINAL_EXPORT를 계속 기다립니다.")
    parser.add_argument("--keep-buffer", action="store_true", help="프로그램 시작 시 기존 UART 수신 버퍼를 비우지 않습니다.")
    parser.add_argument("--save-raw", action="store_true", help="PNG와 함께 수신 Pixel payload를 .bin으로 저장합니다.")
    return parser.parse_args()


def main() -> None:
    """Run the command-line receiver using the selected input source."""
    args = parse_args()
    if args.width <= 0 or args.height <= 0:
        raise SystemExit("width와 height는 1 이상이어야 합니다.")
    if args.port:
        receive_from_uart(args)
    else:
        convert_payload_file(args)


if __name__ == "__main__":
    main()
