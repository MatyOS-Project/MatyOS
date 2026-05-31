#!/usr/bin/env python3
"""Build a standalone `matyos` executable with PyInstaller.

    python build_matyos.py

Produces `dist/matyos` (or `dist/matyos.exe` on Windows): a single-file binary
that runs the proof assistant with no Python installation required.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENTRY = ROOT / "matyos" / "__main__.py"


def _make_icon():
    """Build a clean multi-size .ico from the logo. Best-effort: returns the
    icon path, or None if it cannot be produced (the build then proceeds with
    no custom icon rather than failing — a single-size 1024px .ico makes
    PyInstaller's Windows icon embedder fail)."""
    try:
        from PIL import Image
    except Exception:
        return None
    src = ROOT / "assets" / "logo.png"
    if not src.exists():
        src = ROOT / "matyos_icon.ico"
    if not src.exists():
        return None
    try:
        out = ROOT / "build" / "matyos.ico"
        out.parent.mkdir(parents=True, exist_ok=True)
        img = Image.open(src).convert("RGBA")
        img.save(out, format="ICO",
                 sizes=[(16, 16), (32, 32), (48, 48), (64, 64),
                        (128, 128), (256, 256)])
        return out
    except Exception as e:
        print(f"(icon generation skipped: {e})")
        return None


def main():
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller not found. Install it with:  pip install pyinstaller")
        return 1

    args = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "matyos",
        "--paths", str(ROOT),
        "--collect-submodules", "matyos",
        "--console",
        "--noconfirm",
        "--clean",
    ]
    icon = _make_icon()
    if icon is not None:
        args += ["--icon", str(icon)]
    args.append(str(ENTRY))

    print("Building matyos executable...")
    rc = subprocess.call(args)
    if rc == 0:
        exe = "matyos.exe" if sys.platform.startswith("win") else "matyos"
        print(f"\nBuilt: dist/{exe}")
        print(f"Try:   dist/{exe} check stdlib/arith.elk")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
