#!/usr/bin/env python3
"""Local UART dashboard plus a photo-only Cloudflare Quick Tunnel."""

from __future__ import annotations

import atexit
import json
import os
import re
import secrets
import shutil
import subprocess
import threading
import time
import webbrowser
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

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
SAMPLE_MEM_PATH = BASE_DIR.parent / "02_FPGA_ROM_TEST" / "sunset.mem"
PHOTO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{20,64}$")
TUNNEL_URL_PATTERN = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
_WINDOWS_CONSOLE_HANDLER: Any | None = None


def load_config() -> dict[str, Any]:
    """Load the JSON web configuration and normalize State keys to integers."""
    with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
        config = json.load(config_file)
    config["state_names"] = {
        int(code): str(name) for code, name in config["state_names"].items()
    }
    config.setdefault("public_port", 5001)
    config.setdefault("photo_expire_minutes", 10)
    return config


def find_cloudflared() -> str | None:
    """Find cloudflared from PATH or common WinGet/MSI install locations."""
    override = os.environ.get("CLOUDFLARED_EXE")
    if override and Path(override).is_file():
        return override

    path_result = shutil.which("cloudflared")
    if path_result:
        return path_result

    candidates: list[Path] = []
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        local_root = Path(local_app_data)
        candidates.append(local_root / "Microsoft" / "WinGet" / "Links" / "cloudflared.exe")
        package_root = local_root / "Microsoft" / "WinGet" / "Packages"
        if package_root.is_dir():
            candidates.extend(package_root.glob("Cloudflare.cloudflared_*/*cloudflared.exe"))

    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        program_files = os.environ.get(variable)
        if program_files:
            candidates.append(Path(program_files) / "cloudflared" / "cloudflared.exe")

    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def rgb565_mem_to_image(mem_path: Path, width: int, height: int) -> Image.Image:
    """Create a preview using the same RGB565-to-RGB444 slicing as the FPGA."""
    words = mem_path.read_text(encoding="utf-8").split()
    pixel_count = width * height
    if len(words) < pixel_count:
        raise ValueError(f"MEM Pixel 부족: expected={pixel_count}, actual={len(words)}")

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


def decode_status_fields(status: int) -> dict[str, int | bool]:
    """Decode the System Controller status_data[31:0] bit mapping."""
    return {
        "filter_sel": (status >> 24) & 0x7,
        "capture_count": (status >> 21) & 0x7,
        "frame_sel": (status >> 18) & 0x1,
        "edit_mode": (status >> 16) & 0x3,
        "edit_active": bool((status >> 15) & 0x1),
        "sticker_id": (status >> 13) & 0x3,
        "sticker_size": (status >> 11) & 0x3,
        "draw_color": (status >> 8) & 0x7,
        "cam_ready": bool((status >> 7) & 0x1),
        "all_done": bool((status >> 4) & 0x1),
        "cam_stream_en": bool((status >> 3) & 0x1),
        "marker_track_en": bool((status >> 2) & 0x1),
        "img_export_active": bool((status >> 1) & 0x1),
    }


def encode_status_fields(values: dict[str, Any]) -> tuple[int, int]:
    """Build the exact 32-bit Controller status word used by the FPGA."""
    ranges = {
        "state_code": (0, 6),
        "filter_sel": (0, 7),
        "capture_count": (0, 4),
        "frame_sel": (0, 1),
        "edit_mode": (0, 3),
        "sticker_id": (0, 3),
        "sticker_size": (0, 3),
        "draw_color": (0, 7),
        "receive_progress": (0, 100),
    }

    parsed: dict[str, int] = {}
    for name, (minimum, maximum) in ranges.items():
        value = int(values.get(name, 0))
        if value < minimum or value > maximum:
            raise ValueError(f"{name} 값은 {minimum}~{maximum} 범위여야 합니다.")
        parsed[name] = value

    status = (
        (parsed["state_code"] << 28)
        | (parsed["filter_sel"] << 24)
        | (parsed["capture_count"] << 21)
        | (parsed["frame_sel"] << 18)
        | (parsed["edit_mode"] << 16)
        | (int(bool(values.get("edit_active", False))) << 15)
        | (parsed["sticker_id"] << 13)
        | (parsed["sticker_size"] << 11)
        | (parsed["draw_color"] << 8)
        | (int(bool(values.get("cam_ready", False))) << 7)
        | (int(bool(values.get("all_done", False))) << 4)
        | (int(bool(values.get("cam_stream_en", False))) << 3)
        | (int(bool(values.get("marker_track_en", False))) << 2)
        | (int(bool(values.get("img_export_active", False))) << 1)
    )
    return status, parsed["receive_progress"]


class DashboardState:
    """Thread-safe shared state consumed by the local user and admin pages."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the dashboard snapshot and bounded State history."""
        self._lock = threading.Lock()
        self._state_names: dict[int, str] = config["state_names"]
        self._data: dict[str, Any] = {
            "connected": False,
            "test_mode": False,
            "status_source": "UART",
            "port": None,
            "message": "UART 연결 대기",
            "status_hex": "0x00000000",
            "state_code": 0,
            "state_name": self._state_names.get(0, "STATE_0"),
            **decode_status_fields(0),
            "receive_progress": 0,
            "receiving_photo": False,
            "photo_id": None,
            "photo_page_url": None,
            "photo_expired": False,
            "tunnel_ready": False,
            "tunnel_url": None,
            "tunnel_message": "Cloudflare 공개 주소 생성 중",
        }
        self._history: deque[dict[str, Any]] = deque(maxlen=30)

    def update(self, **values: Any) -> None:
        """Atomically merge values into the current dashboard snapshot."""
        with self._lock:
            self._data.update(values)

    def record_status(self, status: int, state_code: int, source: str = "UART") -> None:
        """Decode and store one FPGA or test Status snapshot and history entry."""
        state_name = self._state_names.get(state_code, f"STATE_0x{state_code:X}")
        status_fields = decode_status_fields(status)
        history_item = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "status_hex": f"0x{status:08X}",
            "state_code": state_code,
            "state_name": state_name,
            "source": source,
        }
        with self._lock:
            previous_state = self._data["state_code"]
            if state_code == 0 and previous_state != 0:
                self._data.update(
                    photo_id=None,
                    photo_page_url=None,
                    photo_expired=False,
                    receive_progress=0,
                )
            self._data.update(
                status_hex=history_item["status_hex"],
                state_code=state_code,
                state_name=state_name,
                status_source=source,
                message=f"{state_name} State 수신",
                **status_fields,
            )
            self._history.appendleft(history_item)

    def snapshot(self) -> dict[str, Any]:
        """Return a copy of the current dashboard data and recent history."""
        with self._lock:
            result = dict(self._data)
            result["history"] = list(self._history)
            return result


class PhotoStore:
    """Store result images and QR codes with time-based expiration."""

    def __init__(self, expire_minutes: int) -> None:
        """Create photo directories and configure the expiration interval."""
        PHOTO_DIR.mkdir(parents=True, exist_ok=True)
        QR_DIR.mkdir(parents=True, exist_ok=True)
        self.expire_seconds = max(1, expire_minutes) * 60
        self._lock = threading.Lock()
        self._public_base_url: str | None = None

    def set_public_base_url(self, url: str) -> None:
        """Set the current public tunnel URL and refresh QR codes for live photos."""
        with self._lock:
            self._public_base_url = url.rstrip("/")
        self.cleanup_expired()
        for photo_path in PHOTO_DIR.glob("*.png"):
            if PHOTO_ID_PATTERN.fullmatch(photo_path.stem):
                self.create_qr(photo_path.stem)

    def page_url(self, photo_id: str) -> str | None:
        """Return the public mobile page URL for a photo when a tunnel is ready."""
        with self._lock:
            base_url = self._public_base_url
        return None if base_url is None else f"{base_url}/photo/{photo_id}"

    def create_qr(self, photo_id: str) -> str | None:
        """Generate a QR image pointing to the public mobile photo page."""
        page_url = self.page_url(photo_id)
        if page_url is None:
            return None
        qrcode.make(page_url).convert("RGB").save(QR_DIR / f"{photo_id}.png")
        return page_url

    def save(self, image: Image.Image) -> tuple[str, str | None]:
        """Save a result image and return its opaque ID and optional public URL."""
        self.cleanup_expired()
        photo_id = secrets.token_urlsafe(24)
        image.convert("RGB").save(PHOTO_DIR / f"{photo_id}.png")
        return photo_id, self.create_qr(photo_id)

    def cleanup_expired(self) -> None:
        """Delete expired result images and their matching QR files."""
        now = time.time()
        for photo_path in PHOTO_DIR.glob("*.png"):
            if now - photo_path.stat().st_mtime <= self.expire_seconds:
                continue
            photo_id = photo_path.stem
            photo_path.unlink(missing_ok=True)
            (QR_DIR / f"{photo_id}.png").unlink(missing_ok=True)

    def is_available(self, photo_id: str) -> bool:
        """Return whether a photo ID is valid, present, and not expired."""
        if not PHOTO_ID_PATTERN.fullmatch(photo_id):
            return False
        photo_path = PHOTO_DIR / f"{photo_id}.png"
        if not photo_path.is_file():
            return False
        if time.time() - photo_path.stat().st_mtime <= self.expire_seconds:
            return True
        photo_path.unlink(missing_ok=True)
        (QR_DIR / f"{photo_id}.png").unlink(missing_ok=True)
        return False

    def require_photo(self, photo_id: str) -> Path:
        """Return an available photo path or abort with the appropriate HTTP status."""
        if not PHOTO_ID_PATTERN.fullmatch(photo_id):
            abort(404)
        photo_path = PHOTO_DIR / f"{photo_id}.png"
        if not photo_path.is_file():
            abort(404)
        if time.time() - photo_path.stat().st_mtime > self.expire_seconds:
            photo_path.unlink(missing_ok=True)
            (QR_DIR / f"{photo_id}.png").unlink(missing_ok=True)
            abort(410)
        return photo_path


class UARTReceiver:
    """Receive status words and RGB444 frames from the Basys3 serial port."""

    def __init__(self, config: dict[str, Any], dashboard_state: DashboardState, photo_store: PhotoStore) -> None:
        """Initialize UART receiver configuration and background-thread state."""
        self.config = config
        self.dashboard_state = dashboard_state
        self.photo_store = photo_store
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._serial: serial.Serial | None = None
        self._thread: threading.Thread | None = None

    def connect(self, port_name: str) -> None:
        """Open the selected serial port and start the receive thread."""
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
        self.dashboard_state.update(connected=True, port=port_name, message="UART 연결 완료 — FPGA State 수신 대기")

    def disconnect(self) -> None:
        """Stop UART reception, close the serial port, and update dashboard state."""
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
        if receiver_thread is not None and receiver_thread is not threading.current_thread():
            receiver_thread.join(timeout=1.0)
        self.dashboard_state.update(connected=False, port=None, receiving_photo=False, receive_progress=0, message="UART 연결 해제")

    def _read_exact(self, uart: serial.Serial, size: int) -> bytes:
        """Read exactly ``size`` bytes while reporting image-receive progress."""
        received = bytearray()
        while len(received) < size:
            if self._stop_event.is_set():
                raise InterruptedError
            chunk = uart.read(min(size - len(received), 4096))
            if not chunk:
                continue
            received.extend(chunk)
            if size > 4:
                self.dashboard_state.update(receive_progress=len(received) * 100 // size)
        return bytes(received)

    def _receive_loop(self) -> None:
        """Continuously decode Status words and FINAL_EXPORT image payloads."""
        with self._lock:
            uart = self._serial
        if uart is None:
            return
        pixel_payload_size = int(self.config["image_width"]) * int(self.config["image_height"]) * 2
        try:
            while not self._stop_event.is_set():
                raw_status = self._read_exact(uart, 4)
                status, state_code = parse_status(raw_status)
                self.dashboard_state.record_status(status, state_code)
                if state_code != int(self.config["export_state"]):
                    continue
                self.dashboard_state.update(receiving_photo=True, receive_progress=0, message="완성 사진 수신 중")
                payload = self._read_exact(uart, pixel_payload_size)
                image = rgb444_payload_to_image(payload, int(self.config["image_width"]), int(self.config["image_height"]))
                photo_id, page_url = self.photo_store.save(image)
                self.dashboard_state.update(
                    receiving_photo=False,
                    receive_progress=100,
                    photo_id=photo_id,
                    photo_page_url=page_url,
                    photo_expired=False,
                    message="완성 사진 저장 및 QR 생성 완료",
                )
        except InterruptedError:
            return
        except Exception as exc:
            if not self._stop_event.is_set():
                self.dashboard_state.update(connected=False, receiving_photo=False, message=f"UART 수신 오류: {exc}")
        finally:
            try:
                uart.close()
            except Exception:
                pass
            with self._lock:
                if self._serial is uart:
                    self._serial = None
                    self._thread = None


class CloudflareTunnel:
    """Manage the cloudflared Quick Tunnel subprocess used by the mobile page."""

    def __init__(self, public_port: int, dashboard_state: DashboardState, on_ready: Callable[[str], None]) -> None:
        """Store tunnel configuration and initialize subprocess lifecycle state."""
        self.public_port = public_port
        self.dashboard_state = dashboard_state
        self.on_ready = on_ready
        self._process: subprocess.Popen[str] | None = None
        self._stopping = False
        self._stop_lock = threading.Lock()

    def start(self) -> None:
        """Start cloudflared and launch a reader thread for the generated public URL."""
        executable = find_cloudflared()
        if executable is None:
            self.dashboard_state.update(tunnel_ready=False, tunnel_message="cloudflared를 찾을 수 없습니다. PowerShell을 다시 열어보세요.")
            return
        creation_flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        try:
            self._process = subprocess.Popen(
                [executable, "tunnel", "--url", f"http://127.0.0.1:{self.public_port}"],
                cwd=BASE_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creation_flags,
            )
        except OSError as exc:
            self.dashboard_state.update(tunnel_ready=False, tunnel_message=f"Cloudflare Tunnel 실행 실패: {exc}")
            return
        threading.Thread(target=self._read_output, daemon=True).start()

    def _read_output(self) -> None:
        """Read cloudflared output, capture the Quick Tunnel URL, and track exit state."""
        process = self._process
        if process is None or process.stdout is None:
            return
        found_url = False
        for line in process.stdout:
            match = TUNNEL_URL_PATTERN.search(line)
            if match is None or found_url:
                continue
            found_url = True
            public_url = match.group(0)
            self.on_ready(public_url)
            self.dashboard_state.update(
                tunnel_ready=True,
                tunnel_url=public_url,
                tunnel_message="휴대폰 공개 주소 준비 완료",
            )
            print(f"[Cloudflare] 공개 주소: {public_url}", flush=True)
        return_code = process.wait()
        if not self._stopping:
            self.dashboard_state.update(tunnel_ready=False, tunnel_message=f"Cloudflare Tunnel 종료됨 (code={return_code})")

    def stop(self) -> None:
        """Terminate cloudflared, escalating to kill when graceful termination times out."""
        with self._stop_lock:
            self._stopping = True
            process = self._process
            if process is None or process.poll() is not None:
                return
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1)


def register_windows_console_cleanup(tunnel: CloudflareTunnel) -> None:
    """Stop cloudflared when Windows sends a console close/control event."""
    global _WINDOWS_CONSOLE_HANDLER
    if os.name != "nt":
        return

    try:
        import ctypes
        from ctypes import wintypes

        handler_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)
        cleanup_events = {0, 1, 2, 5, 6}  # CTRL_C/BREAK/CLOSE/LOGOFF/SHUTDOWN

        @handler_type
        def console_handler(control_type: int) -> bool:
            if control_type in cleanup_events:
                tunnel.stop()
            # Let Python/Windows continue their normal termination handling.
            return False

        kernel32 = ctypes.WinDLL("Kernel32", use_last_error=True)
        kernel32.SetConsoleCtrlHandler.argtypes = [handler_type, wintypes.BOOL]
        kernel32.SetConsoleCtrlHandler.restype = wintypes.BOOL
        if not kernel32.SetConsoleCtrlHandler(console_handler, True):
            raise ctypes.WinError(ctypes.get_last_error())

        # Keep the ctypes callback alive for the lifetime of the process.
        _WINDOWS_CONSOLE_HANDLER = console_handler
    except Exception as exc:
        print(f"[Cloudflare] Windows console cleanup handler registration failed: {exc}", flush=True)


config = load_config()
private_port = int(config["web_port"])
public_port = int(config["public_port"])
dashboard_state = DashboardState(config)
photo_store = PhotoStore(int(config["photo_expire_minutes"]))
uart_receiver = UARTReceiver(config, dashboard_state, photo_store)
app = Flask(__name__, template_folder=str(BASE_DIR / "templates"))
public_app = Flask("photo_public", template_folder=str(BASE_DIR / "templates"))


def handle_tunnel_ready(public_url: str) -> None:
    """Update photo URLs and QR codes after Cloudflare publishes a tunnel URL."""
    photo_store.set_public_base_url(public_url)
    photo_id = dashboard_state.snapshot().get("photo_id")
    if photo_id:
        dashboard_state.update(photo_page_url=photo_store.page_url(photo_id))


tunnel = CloudflareTunnel(public_port, dashboard_state, handle_tunnel_ready)
register_windows_console_cleanup(tunnel)
atexit.register(tunnel.stop)


@app.get("/")
def user_screen() -> str:
    """Render the user-facing photo booth screen."""
    return render_template("user.html")


@app.get("/settings")
def settings_screen() -> str:
    """Render the administrator settings and Status monitor screen."""
    return render_template("dashboard.html", baud_rate=config["baud_rate"])


@app.get("/api/status")
def api_status():
    """Return the latest UART/test Status, tunnel state, and photo metadata."""
    snapshot = dashboard_state.snapshot()
    photo_id = snapshot.get("photo_id")
    if photo_id and not photo_store.is_available(photo_id):
        dashboard_state.update(
            photo_id=None,
            photo_page_url=None,
            photo_expired=True,
        )
        snapshot = dashboard_state.snapshot()
    return jsonify(snapshot)


@app.get("/api/ports")
def api_ports():
    """Return available serial ports for the administrator connection selector."""
    ports = [{"device": item.device, "description": item.description} for item in list_ports.comports()]
    return jsonify({"ports": ports})


@app.post("/api/connect")
def api_connect():
    """Connect the UART receiver to the selected COM port."""
    body = request.get_json(silent=True) or {}
    port_name = str(body.get("port", "")).strip()
    if not port_name:
        return jsonify({"ok": False, "error": "COM 포트를 선택하세요."}), 400
    try:
        dashboard_state.update(test_mode=False, status_source="UART")
        uart_receiver.connect(port_name)
    except Exception as exc:
        dashboard_state.update(message=f"UART 연결 실패: {exc}")
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True})


@app.post("/api/disconnect")
def api_disconnect():
    """Disconnect the active UART receiver."""
    uart_receiver.disconnect()
    return jsonify({"ok": True})


@app.post("/api/test-mode")
def api_test_mode():
    """Enable or disable the FPGA-free administrator UI test mode."""
    body = request.get_json(silent=True) or {}
    enabled = bool(body.get("enabled", False))
    if enabled:
        uart_receiver.disconnect()
        dashboard_state.update(
            test_mode=True,
            status_source="TEST",
            message="UI 시험 모드 — 관리자 입력 사용 중",
        )
    else:
        dashboard_state.update(
            test_mode=False,
            status_source="UART",
            receiving_photo=False,
            receive_progress=0,
            message="UI 시험 모드 종료 — UART 연결 대기",
        )
    return jsonify({"ok": True, "test_mode": enabled})


@app.post("/api/test-status")
def api_test_status():
    """Apply one synthetic Controller Status snapshot while test mode is active."""
    if not dashboard_state.snapshot().get("test_mode"):
        return jsonify({"ok": False, "error": "먼저 UI 시험 모드를 켜세요."}), 400

    body = request.get_json(silent=True) or {}
    try:
        status, receive_progress = encode_status_fields(body)
        state_code = int(body.get("state_code", 0))
        dashboard_state.record_status(status, state_code, source="TEST")
        dashboard_state.update(
            receiving_photo=(state_code == int(config["export_state"])),
            receive_progress=receive_progress,
            message=f"{config['state_names'].get(state_code, state_code)} UI 시험값 적용",
        )
    except (TypeError, ValueError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, "status_hex": f"0x{status:08X}"})


@app.post("/api/test-reset")
def api_test_reset():
    """Reset the synthetic test Status and photo metadata to OPEN defaults."""
    if not dashboard_state.snapshot().get("test_mode"):
        return jsonify({"ok": False, "error": "먼저 UI 시험 모드를 켜세요."}), 400
    dashboard_state.record_status(0, 0, source="TEST")
    dashboard_state.update(
        receiving_photo=False,
        receive_progress=0,
        photo_id=None,
        photo_page_url=None,
        photo_expired=False,
        message="UI 시험값 초기화 완료",
    )
    return jsonify({"ok": True})


@app.post("/api/test-photo")
def api_test_photo():
    """Build a sample result photo from sunset.mem for FPGA-free web/QR testing."""
    try:
        if not dashboard_state.snapshot().get("test_mode"):
            uart_receiver.disconnect()
            dashboard_state.update(test_mode=True, status_source="TEST")
        image = rgb565_mem_to_image(SAMPLE_MEM_PATH, int(config["image_width"]), int(config["image_height"]))
        export_state = int(config["export_state"])
        dashboard_state.record_status((export_state << 28) | 0x0080_0012, export_state, source="TEST")
        photo_id, page_url = photo_store.save(image)
        dashboard_state.record_status(0x6080_0010, 6, source="TEST")
        dashboard_state.update(
            photo_id=photo_id,
            photo_page_url=page_url,
            photo_expired=False,
            receive_progress=100,
            message="샘플 사진과 QR 생성 완료",
        )
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
    return jsonify({"ok": True, "photo_id": photo_id})


@app.get("/photos/<photo_id>.png")
def local_photo_file(photo_id: str):
    """Serve a non-expired result photo to the local dashboard/user page."""
    photo_store.require_photo(photo_id)
    return send_from_directory(PHOTO_DIR, f"{photo_id}.png")


@app.get("/qr/<photo_id>.png")
def local_qr_file(photo_id: str):
    """Serve the locally generated QR code for a result photo."""
    photo_store.require_photo(photo_id)
    qr_path = QR_DIR / f"{photo_id}.png"
    if not qr_path.is_file():
        abort(404)
    return send_from_directory(QR_DIR, f"{photo_id}.png")


@app.get("/download/<photo_id>")
def local_download_photo(photo_id: str):
    """Serve a result photo as a local attachment download."""
    photo_store.require_photo(photo_id)
    return send_from_directory(PHOTO_DIR, f"{photo_id}.png", as_attachment=True, download_name=f"four_cut_{photo_id}.png")


@public_app.after_request
def disable_public_cache(response):
    """Disable caching and MIME sniffing on public photo responses."""
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@public_app.get("/photo/<photo_id>")
def mobile_photo_page(photo_id: str):
    """Render the public mobile photo page for a valid non-expired photo."""
    photo_store.require_photo(photo_id)
    return render_template("photo.html", photo_id=photo_id)


@public_app.get("/photos/<photo_id>.png", endpoint="photo_file")
def public_photo_file(photo_id: str):
    """Serve a public non-expired result image."""
    photo_store.require_photo(photo_id)
    return send_from_directory(PHOTO_DIR, f"{photo_id}.png")


@public_app.get("/download/<photo_id>", endpoint="download_photo")
def public_download_photo(photo_id: str):
    """Serve a public result image as an attachment download."""
    photo_store.require_photo(photo_id)
    return send_from_directory(PHOTO_DIR, f"{photo_id}.png", as_attachment=True, download_name=f"four_cut_{photo_id}.png")


def run_public_server() -> None:
    """Run the localhost-only photo server that cloudflared exposes publicly."""
    public_app.run(host="127.0.0.1", port=public_port, debug=False, threaded=True, use_reloader=False)


def open_dashboard() -> None:
    """Open the local user page in the default browser."""
    webbrowser.open(f"http://127.0.0.1:{private_port}")


if __name__ == "__main__":
    threading.Thread(target=run_public_server, daemon=True).start()
    time.sleep(0.7)
    tunnel.start()
    threading.Timer(1.0, open_dashboard).start()
    try:
        app.run(host="127.0.0.1", port=private_port, debug=False, threaded=True, use_reloader=False)
    finally:
        tunnel.stop()
