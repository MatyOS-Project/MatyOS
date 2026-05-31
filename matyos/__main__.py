"""Allow `python -m matyos ...` to invoke the same CLI as the `matyos` command."""

from matyos.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
