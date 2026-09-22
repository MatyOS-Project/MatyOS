"""MatyOS desktop app — the research console in a native window.

Boots the local :mod:`matyos.ui` server on a private localhost port and shows
it in an OS-native webview window (WKWebView on macOS, WebView2 on Windows,
GTK/Qt on Linux). No browser chrome, no Electron, no Node — it reuses the same
zero-dependency stdlib server the ``matyos-ui`` command serves.

The MatyOS logo is used two ways: it renders in the console's hero inside the
window, and it is set as the window/app icon where the platform allows it (the
packaged ``.app`` / ``.exe`` carries it as the bundle icon — see build_desktop.py).

pywebview is an *optional* dependency so the core package keeps zero runtime
deps::

    pip install "matyos[desktop]"

If pywebview is not installed, this falls back to opening the console in the
default browser and keeping the server alive.
"""
from __future__ import annotations

import os
import socket
import tempfile
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer

from . import __version__
from .ui import _Handler, _asset

HOST = "127.0.0.1"


def _free_port(host: str = HOST) -> int:
    """Ask the OS for an unused TCP port (bind to 0, read it back)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]


def _start_server(host: str, port: int) -> ThreadingHTTPServer:
    """Serve the console in a daemon thread; returns the running server."""
    httpd = ThreadingHTTPServer((host, port), _Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def _wait_until_up(url: str, timeout: float = 5.0) -> bool:
    """Poll the server until it answers, so the window never opens on a blank
    page. Returns False if it never came up within ``timeout`` seconds."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=0.5)  # noqa: S310 (localhost)
            return True
        except OSError:
            time.sleep(0.05)
    return False


def _icon_file() -> str | None:
    """Materialise the packaged logo to a temp PNG so the webview/app can point
    at it by path. Returns None if the logo can't be read."""
    data = _asset("logo.png")
    if not data:
        return None
    fd, path = tempfile.mkstemp(suffix="-matyos.png")
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return path


def _run_browser_fallback(url: str) -> None:
    """No pywebview: open the console in the default browser and hold the
    server open until interrupted."""
    import webbrowser

    print('pywebview not installed — opening MatyOS in your browser instead.')
    print('For the native desktop window:  pip install "matyos[desktop]"')
    print(f"MatyOS research console → {url}  (Ctrl-C to stop)")
    webbrowser.open(url)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


def main() -> None:
    port = _free_port()
    _start_server(HOST, port)
    url = f"http://{HOST}:{port}/"
    if not _wait_until_up(url):
        raise SystemExit("MatyOS: the local console server failed to start.")

    try:
        import webview  # pywebview
    except ImportError:
        _run_browser_fallback(url)
        return

    webview.create_window(
        f"MatyOS {__version__}",
        url,
        width=1220,
        height=840,
        min_size=(920, 620),
    )
    icon = _icon_file()
    try:
        # `icon` is honoured on GTK/Qt; ignored on macOS Cocoa (the .app bundle
        # icon is used there instead). Fall back if this pywebview predates the
        # kwarg.
        webview.start(icon=icon) if icon else webview.start()
    except TypeError:
        webview.start()


if __name__ == "__main__":
    main()
