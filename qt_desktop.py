from __future__ import annotations

import ctypes
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox


def _show_error(message: str) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(0, message, "usb-logic-trace-correlator", 0x10)
    except Exception:
        print(message)


def _resolve_app_path() -> Path:
    if hasattr(sys, "_MEIPASS"):
        base = Path(getattr(sys, "_MEIPASS"))
        app = base / "app.py"
        if app.exists():
            return app
    return Path(__file__).resolve().parent / "app.py"


def _wait_http_ready(url: str, timeout_s: float = 25.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as resp:
                if 200 <= resp.status < 300:
                    return True
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.25)
    return False


def _run_streamlit_child(app_path: Path, port: int) -> int:
    from streamlit.web import cli as stcli

    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        "--server.headless",
        "true",
        "--server.port",
        str(port),
        "--server.maxUploadSize",
        "4096",
        "--server.maxMessageSize",
        "4096",
        "--global.developmentMode",
        "false",
        "--browser.gatherUsageStats",
        "false",
    ]
    return stcli.main()


def _start_streamlit_process(app_path: Path, port: int) -> subprocess.Popen:
    cmd = [
        sys.executable,
        "--qt-streamlit-child",
        str(app_path),
        str(port),
    ]
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> int:
    if len(sys.argv) >= 4 and sys.argv[1] == "--qt-streamlit-child":
        return _run_streamlit_child(Path(sys.argv[2]), int(sys.argv[3]))

    app_path = _resolve_app_path()
    if not app_path.exists():
        _show_error(f"app.py not found: {app_path}")
        return 1

    port = 8501
    url = f"http://127.0.0.1:{port}"
    health_url = f"{url}/_stcore/health"
    server = _start_streamlit_process(app_path, port)

    if not _wait_http_ready(health_url):
        if server.poll() is None:
            server.terminate()
        _show_error("Qt desktop app failed to start local server on http://127.0.0.1:8501")
        return 1

    qt = QApplication(sys.argv)
    win = QMainWindow()
    win.setWindowTitle("USB Logic Trace Correlator (Qt)")
    win.resize(1500, 980)

    view = QWebEngineView()
    view.setUrl(QUrl(url))
    win.setCentralWidget(view)

    def _cleanup() -> None:
        if server.poll() is None:
            server.terminate()

    qt.aboutToQuit.connect(_cleanup)

    win.show()
    try:
        return qt.exec()
    finally:
        _cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
