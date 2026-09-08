#!/usr/bin/env python3
"""Convert a JPG/PNG image to a 640x480 RGB565 .mem file for ROM/web testing."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageOps


def convert_image(input_path: Path, output_path: Path, width: int, height: int) -> None:
    image = Image.open(input_path)
    image = ImageOps.exif_transpose(image).convert("RGB")
    image = image.resize((width, height))

    with output_path.open("w", encoding="utf-8") as mem_file:
        for y in range(height):
            for x in range(width):
                red, green, blue = image.getpixel((x, y))

                red5 = red >> 3
                green6 = green >> 2
                blue5 = blue >> 3
                rgb565 = (red5 << 11) | (green6 << 5) | blue5

                mem_file.write(f"{rgb565:04X}\n")

    print(f"MEM 생성 완료: {output_path.resolve()}")
    print(f"Pixel 수: {width * height}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="JPG/PNG 이미지를 FPGA ROM 시험용 RGB565 .mem 파일로 변환합니다."
    )
    parser.add_argument("input", type=Path, help="입력 JPG/PNG 이미지")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("sunset.mem"),
        help="출력 .mem 파일 경로 (기본: sunset.mem)",
    )
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.width <= 0 or args.height <= 0:
        raise SystemExit("width와 height는 1 이상이어야 합니다.")
    if not args.input.is_file():
        raise SystemExit(f"입력 이미지가 없습니다: {args.input}")

    convert_image(args.input, args.output, args.width, args.height)


if __name__ == "__main__":
    main()
