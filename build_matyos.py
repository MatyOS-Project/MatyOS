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
ICON = ROOT / "matyos_icon.ico"


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
    if ICON.exists():
        args += ["--icon", str(ICON)]
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
