#!/usr/bin/env python3
"""Build the MatyOS **desktop app** with PyInstaller.

    pip install pyinstaller pywebview pillow
    python build_desktop.py

Produces a windowed application that opens the MatyOS research console in a
native webview:

  * macOS   → ``dist/MatyOS.app``   (icon from assets/logo.png via iconutil)
  * Windows → ``dist/MatyOS.exe``   (icon from a multi-size .ico)
  * Linux   → ``dist/MatyOS``       (GTK/Qt window)

This is separate from ``build_matyos.py`` (the console CLI binary): this target
is windowed (no terminal) and bundles pywebview + the packaged assets.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# Run a root launcher as __main__ so matyos.desktop imports as a real package
# submodule (its relative imports resolve); pointing PyInstaller straight at
# matyos/desktop.py would run it as top-level __main__ and break those imports.
ENTRY = ROOT / "desktop_launcher.py"
LOGO = ROOT / "matyos" / "assets" / "logo.png"


def _make_icns() -> Path | None:
    """macOS: build a proper multi-resolution .icns from the logo using a
    generated .iconset + the system `iconutil`. Best-effort → None on failure."""
    try:
        from PIL import Image
    except Exception:
        return None
    if not LOGO.exists():
        return None
    try:
        iconset = ROOT / "build" / "MatyOS.iconset"
        iconset.mkdir(parents=True, exist_ok=True)
        base = Image.open(LOGO).convert("RGBA")
        for size in (16, 32, 128, 256, 512):
            base.resize((size, size), Image.LANCZOS).save(iconset / f"icon_{size}x{size}.png")
            base.resize((size * 2, size * 2), Image.LANCZOS).save(
                iconset / f"icon_{size}x{size}@2x.png")
        out = ROOT / "build" / "MatyOS.icns"
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(out)],
                       check=True)
        return out
    except Exception as e:
        print(f"(icns generation skipped: {e})")
        return None


def _make_ico() -> Path | None:
    """Windows: multi-size .ico from the logo. Best-effort → None."""
    try:
        from PIL import Image
    except Exception:
        return None
    if not LOGO.exists():
        return None
    try:
        out = ROOT / "build" / "MatyOS.ico"
        out.parent.mkdir(parents=True, exist_ok=True)
        Image.open(LOGO).convert("RGBA").save(
            out, format="ICO",
            sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
        return out
    except Exception as e:
        print(f"(ico generation skipped: {e})")
        return None


def main() -> int:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller not found. Install it with:  pip install pyinstaller")
        return 1
    try:
        import webview  # noqa: F401
    except ImportError:
        print("pywebview not found. Install it with:  pip install pywebview")
        return 1

    sep = ";" if sys.platform == "win32" else ":"
    args = [
        sys.executable, "-m", "PyInstaller",
        "--name", "MatyOS",
        "--windowed",                     # no terminal window
        "--onedir",                       # a proper .app / folder bundle
        "--paths", str(ROOT),
        "--collect-submodules", "matyos",
        "--collect-data", "matyos",       # bundle assets/ + stdlib/
        "--collect-all", "webview",       # pywebview's platform back-ends
        "--noconfirm",
        "--clean",
    ]

    if sys.platform == "darwin":
        icns = _make_icns()
        if icns:
            args += ["--icon", str(icns)]
        args += ["--osx-bundle-identifier", "com.matyos.console"]
    elif sys.platform == "win32":
        ico = _make_ico()
        if ico:
            args += ["--icon", str(ico)]

    args.append(str(ENTRY))
    print("running:", " ".join(args))
    rc = subprocess.run(args).returncode
    if rc == 0:
        print("\nBuilt. macOS: open dist/MatyOS.app  ·  Windows: dist/MatyOS/MatyOS.exe")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
