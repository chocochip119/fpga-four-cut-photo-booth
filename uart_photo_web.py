#!/usr/bin/env python3
"""Web dashboard for FPGA UART status and completed-photo reception."""

from __future__ import annotations

import json
import re
import socket
import threading
import webbrowser
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

import qrcode
import serial
from flask import Flask, abort, jsonify, render_template, request, send_from_directory
from PIL import Image
from serial.tools import list_ports

from receive_uart_image import parse_status, rgb444_payload_to_image


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "web_config.json"
PHOTO_DIR = BASE_DIR / "received_photos"
QR_DIR = PHOTO_DIR / "qr"
PHOTO_ID_PATTERN = re.compile(r"^[0-9]{8}_[0-9]{6}_[0-9]{6}$")


def load_config() -> dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
        config = json.load(config_file)

    config["state_names"] = {
        int(code): str(name) for code, name in config["state_names"].items()
    }
    return config


def detect_local_ip() -> str:
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        udp_socket.connect(("8.8.8.8", 80))
        return str(udp_socket.getsockname()[0])
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    finally:
        udp_socket.close()


def rgb565_mem_to_image(mem_path: Path, width: int, height: int) -> Image.Image:
    """Create a preview using the same RGB565-to-RGB444 slicing as the FPGA."""
    words = mem_path.read_text(encoding="utf-8").split()
    pixel_count = width * height

    if len(words) < pixel_count:
        raise ValueError(
            f"MEM Pixel 부족: expected={pixel_count}, actual={len(words)}"
        )

    rgb888 = bytearray(pixel_count * 3)

    for index, token in enumerate(words[:pixel_count]):
        rgb565 = int(token, 16)
        red4 = (rgb565 >> 12) & 0xF
        green4 = (rgb565 >> 7) & 0xF
        blue4 = (rgb565 >> 1) & 0xF

        rgb888[index * 3] = (red4 << 4) | red4
        rgb888[index * 3 + 1] = (green4 << 4) | green4
        rgb888[index * 3 + 2] = (blue4 << 4) | blue4

    return Image.frombytes("RGB", (width, height), bytes(rgb888))


class DashboardState:
    def __init__(self, config: dict[str, Any]) -> None:
        self._lock = threading.Lock()
        self._state_names: dict[int, str] = config["state_names"]
        self._data: dict[str, Any] = {
            "connected": False,
            "port": None,
            "message": "UART 연결 대기",
            "status_hex": "0x00000000",
            "state_code": 0,
            "state_name": self._state_names.get(0, "STATE_0"),
            "receive_progress": 0,
            "receiving_photo": False,
            "photo_id": None,
            "photo_page_url": None,
        }
        self._history: deque[dict[str, Any]] = deque(maxlen=30)

    def update(self, **values: Any) -> None:
        with self._lock:
            self._data.update(values)

    def record_status(self, status: int, state_code: int) -> None:
        state_name = self._state_names.get(state_code, f"STATE_0x{state_code:X}")
        history_item = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "status_hex": f"0x{status:08X}",
            "state_code": state_code,
            "state_name": state_name,
        }

        with self._lock:
            self._data.update(
                status_hex=history_item["status_hex"],
                state_code=state_code,
                state_name=state_name,
                message=f"{state_name} State 수신",
            )
            self._history.appendleft(history_item)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            result = dict(self._data)
            result["history"] = list(self._history)
            return result


class PhotoStore:
    def __init__(self, qr_host: str, web_port: int) -> None:
        PHOTO_DIR.mkdir(parents=True, exist_ok=True)
        QR_DIR.mkdir(parents=True, exist_ok=True)
        self.qr_host = qr_host
        self.web_port = web_port

    def save(self, image: Image.Image) -> tuple[str, str]:
        photo_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        image.convert("RGB").save(PHOTO_DIR / f"{photo_id}.png")

        page_url = f"http://{self.qr_host}:{self.web_port}/photo/{photo_id}"
        qr_image = qrcode.make(page_url).convert("RGB")
        qr_image.save(QR_DIR / f"{photo_id}.png")
        return photo_id, page_url

    @staticmethod
    def require_photo(photo_id: str) -> Path:
        if not PHOTO_ID_PATTERN.fullmatch(photo_id):
            abort(404)

        photo_path = PHOTO_DIR / f"{photo_id}.png"
        if not photo_path.is_file():
            abort(404)
        return photo_path


class UARTReceiver:
    def __init__(
        self,
        config: dict[str, Any],
        dashboard_state: DashboardState,
        photo_store: PhotoStore,
    ) -> None:
        self.config = config
        self.dashboard_state = dashboard_state
        self.photo_store = photo_store
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._serial: serial.Serial | None = None
        self._thread: threading.Thread | None = None

    def connect(self, port_name: str) -> None:
        self.disconnect()

        uart = serial.Serial(
            port=port_name,
            baudrate=int(self.config["baud_rate"]),
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.3,
        )
        uart.reset_input_buffer()

        with self._lock:
            self._serial = uart
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._receive_loop, daemon=True)
            self._thread.start()

        self.dashboard_state.update(
            connected=True,
            port=port_name,
            message="UART 연결 완료 — FPGA State 수신 대기",
        )

    def disconnect(self) -> None:
        self._stop_event.set()

        with self._lock:
            uart = self._serial
            self._serial = None
            receiver_thread = self._thread
            self._thread = None

        if uart is not None:
            try:
                uart.close()
            except serial.SerialException:
                pass

        if (
            receiver_thread is not None
            and receiver_thread is not threading.current_thread()
        ):
            receiver_thread.join(timeout=1.0)

        self.dashboard_state.update(
            connected=False,
            port=None,
            receiving_photo=False,
            receive_progress=0,
            message="UART 연결 해제",
        )

    def _read_exact(self, uart: serial.Serial, size: int) -> bytes:
        received = bytearray()

        while len(received) < size:
            if self._stop_event.is_set():
                raise InterruptedError

            chunk = uart.read(min(size - len(received), 4096))
            if not chunk:
                continue
            received.extend(chunk)

            if size > 4:
                progress = len(received) * 100 // size
                self.dashboard_state.update(receive_progress=progress)

        return bytes(received)

    def _receive_loop(self) -> None:
        with self._lock:
            uart = self._serial

        if uart is None:
            return

        pixel_payload_size = (
            int(self.config["image_width"])
            * int(self.config["image_height"])
            * 2
        )

        try:
            while not self._stop_event.is_set():
                raw_status = self._read_exact(uart, 4)
                status, state_code = parse_status(raw_status)
                self.dashboard_state.record_status(status, state_code)

                if state_code != int(self.config["export_state"]):
                    continue

                self.dashboard_state.update(
                    receiving_photo=True,
                    receive_progress=0,
                    message="완성 사진 수신 중",
                )
                payload = self._read_exact(uart, pixel_payload_size)
                image = rgb444_payload_to_image(
                    payload,
                    int(self.config["image_width"]),
                    int(self.config["image_height"]),
                )
                photo_id, page_url = self.photo_store.save(image)
                self.dashboard_state.update(
                    receiving_photo=False,
                    receive_progress=100,
                    photo_id=photo_id,
                    photo_page_url=page_url,
                    message="완성 사진 저장 및 QR 생성 완료",
                )
        except InterruptedError:
            return
        except Exception as exc:
            if not self._stop_event.is_set():
                self.dashboard_state.update(
                    connected=False,
                    receiving_photo=False,
                    message=f"UART 수신 오류: {exc}",
                )
        finally:
            try:
                uart.close()
            except Exception:
                pass

            with self._lock:
                if self._serial is uart:
                    self._serial = None
                    self._thread = None


config = load_config()
web_port = int(config["web_port"])
qr_host = str(config["qr_host"])
if qr_host.lower() == "auto":
    qr_host = detect_local_ip()

dashboard_state = DashboardState(config)
photo_store = PhotoStore(qr_host, web_port)
uart_receiver = UARTReceiver(config, dashboard_state, photo_store)

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
)


@app.get("/")
def dashboard() -> str:
    return render_template(
        "dashboard.html",
        baud_rate=config["baud_rate"],
        qr_host=qr_host,
        web_port=web_port,
    )


@app.get("/user")
def user_view() -> str:
    return render_template("user.html")


@app.get("/api/status")
def api_status():
    return jsonify(dashboard_state.snapshot())


@app.get("/api/ports")
def api_ports():
    ports = [
        {"device": item.device, "description": item.description}
        for item in list_ports.comports()
    ]
    return jsonify({"ports": ports})


@app.post("/api/connect")
def api_connect():
    body = request.get_json(silent=True) or {}
    port_name = str(body.get("port", "")).strip()

    if not port_name:
        return jsonify({"ok": False, "error": "COM 포트를 선택하세요."}), 400

    try:
        uart_receiver.connect(port_name)
    except Exception as exc:
        dashboard_state.update(message=f"UART 연결 실패: {exc}")
        return jsonify({"ok": False, "error": str(exc)}), 400

    return jsonify({"ok": True})


@app.post("/api/disconnect")
def api_disconnect():
    uart_receiver.disconnect()
    return jsonify({"ok": True})


@app.post("/api/test-photo")
def api_test_photo():
    """Create a web result from sunset.mem without opening a UART port."""
    try:
        image = rgb565_mem_to_image(
            BASE_DIR / "sunset.mem",
            int(config["image_width"]),
            int(config["image_height"]),
        )
        dashboard_state.record_status(0x1000_0000, int(config["export_state"]))
        photo_id, page_url = photo_store.save(image)
        dashboard_state.record_status(0x0000_0000, 0)
        dashboard_state.update(
            photo_id=photo_id,
            photo_page_url=page_url,
            receive_progress=100,
            message="샘플 사진과 QR 생성 완료",
        )
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({"ok": True, "photo_id": photo_id})


@app.get("/photos/<photo_id>.png")
def photo_file(photo_id: str):
    photo_store.require_photo(photo_id)
    return send_from_directory(PHOTO_DIR, f"{photo_id}.png")


@app.get("/qr/<photo_id>.png")
def qr_file(photo_id: str):
    photo_store.require_photo(photo_id)
    qr_path = QR_DIR / f"{photo_id}.png"
    if not qr_path.is_file():
        abort(404)
    return send_from_directory(QR_DIR, f"{photo_id}.png")


@app.get("/photo/<photo_id>")
def mobile_photo_page(photo_id: str):
    photo_store.require_photo(photo_id)
    return render_template("photo.html", photo_id=photo_id)


@app.get("/download/<photo_id>")
def download_photo(photo_id: str):
    photo_store.require_photo(photo_id)
    return send_from_directory(
        PHOTO_DIR,
        f"{photo_id}.png",
        as_attachment=True,
        download_name=f"four_cut_{photo_id}.png",
    )


def open_dashboard() -> None:
    webbrowser.open(f"http://127.0.0.1:{web_port}")


if __name__ == "__main__":
    threading.Timer(1.0, open_dashboard).start()
    app.run(host="0.0.0.0", port=web_port, debug=False, threaded=True)
