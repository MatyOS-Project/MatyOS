# Contributing to MatyOS

End users only need the `matyos` binary from the
[Releases](https://github.com/MatyOS-Project/MatyOS/releases) page. This document
is for **contributors** who want to build MatyOS from source, run the test
suite, or hack on the kernel.

## Implementation

MatyOS is currently implemented in Python 3.8+. The released `matyos` command is
a self-contained binary (built with PyInstaller) so end users never need a
toolchain. Contributors do.

## Building the `matyos` binary

```bash
pip install pyinstaller        # one-time build dependency
python build_matyos.py         # -> dist/matyos  (dist/matyos.exe on Windows)
dist/matyos check stdlib/arith.elk
```

Released cross-platform binaries are produced automatically by the
`Build MatyOS` GitHub Actions workflow (`.github/workflows/matyos.yml`) on every
`v*` tag.

## Running the test suite

```bash
pip install pytest
python -m pytest -q            # 233 tests
python -m pytest tests/test_kernel_core.py -q
```

The suite covers the kernel (substitution/normalization/inference, sort rules),
inductive types and computation, the J rule and the `n+0=n` induction proof,
strict-positivity rejection, definitions, impredicative `Prop`, the surface
parser, the CLI exit codes, every `.elk` file, and the three-valued logic.

During development you can also run the checker directly without building the
binary:

```bash
python -m matyos check stdlib/arith.elk
```

## Project layout

See the *Architecture* section of the [README](README.md). The cardinal rule:

> **The kernel is the only trusted component.** Keep `matyos/kernel` small,
> auditable, and sound. Everything else (parser, stdlib, `realistic` layer,
> future tactics, LLM output) must reduce to terms the kernel re-checks. Never
> add a shortcut that marks something "proven" without the kernel checking it.

## Tests are required

Any change to the kernel must come with tests, and the full suite must stay
green. If you find a soundness bug, that is the highest-priority issue — please
flag it explicitly.

## The legacy language

The original imperative "El / Easier" language lives in `compiler/`, `utils/`,
`system/` and is documented in [docs/legacy-el-language.md](docs/legacy-el-language.md).
It is independent from the proof assistant; new work targets MatyOS.
