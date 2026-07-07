# MatyOS-C

A from-scratch **C** reimplementation of the MatyOS proof assistant — same
grammar, same architecture as the Python version (`../matyos`), for a
dependency-free, fast, single-binary kernel.

## Build

Needs a C11 compiler. Without a system compiler, use the self-contained zig
toolchain (`pip install ziglang`):

```sh
make CC="python -m ziglang cc" test
```

## Layout (planned, built milestone by milestone)

```
src/
  term.{h,c}    kernel terms (de Bruijn), arena, shift/subst/normalize/def_equal   [M1 ✓]
  infer.{h,c}   the trusted type checker (imax Pi, impredicative Prop)              [M2 ✓]
  env.{h,c}     global environment, inductives, recursors, iota, positivity         [M3 ✓]
  env.{h,c}     Eq / refl / J eliminator + transport (in env.c)                      [M4 ✓]
  parse.{h,c}   tokenizer + parser for the .elk surface language                    [M5]
  check.{h,c}   commands: def/axiom/inductive/example/check/eval + scientific method [M5/M6]
  tactics.*     intro/exact/assumption/refl/rewrite/induction/apply/auto            [M7]
  project.*     .thm/.prf/.hyp/.test, .matyos archives, --json                      [M8]
  main.c        the `matyos-c` CLI
test/           unit tests per module
```

Goal: `matyos-c check <file>` reproduces the Python results on the existing
`../stdlib/*.elk` and `../examples/proofs/*.elk` files.
