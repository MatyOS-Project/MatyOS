"""MatyOS command-line interface.

    python -m matyos check <file.elk>   # type-check a proof file
    python -m matyos eval  <file.elk>   # same, echoing eval/check results
    python -m matyos version
"""

import sys
from matyos import __version__
from matyos.frontend.surface import run_file


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd = argv[0]
    if cmd in ("version", "--version", "-v"):
        print(f"MatyOS {__version__}")
        return 0
    if cmd in ("check", "eval"):
        if len(argv) < 2:
            print(f"usage: python -m matyos {cmd} <file.elk>")
            return 2
        run_file(argv[1])
        return 0
    # bare path -> check it
    run_file(cmd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
