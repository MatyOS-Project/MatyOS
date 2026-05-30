# The legacy "El / Easier" imperative language

> This documents the **original** imperative scripting language that the
> project began as. It is preserved and still runnable, but it is **not** the
> proof assistant. The proof assistant lives in [`matyos/`](../matyos) and is
> documented in the main [README](../README.md). New work targets the proof
> assistant; this page is kept for historical/reference purposes.

The legacy interpreter lives in `compiler/`, `utils/`, `system/`, with example
programs in `examples/*.el`.

### Program structure
```javascript
ALGORITHM Example {
    var x, y : integer;
    x = 1 * 2 + 3 - 4 / 5 * (1 + 2);
    SHOW(x);
}
```

### Features
- Variable declarations: `var x, y : integer;`, `var s : real;`, `var c : string;`, `var f : boolean;`
- Assignment and arithmetic / boolean expressions
- `function foo(s: STRING) { ... return ...; }` and calls
- `if / elif / else`, `for`, `WHILE ... DO`, `DO ... WHILE`, `switch/case/default`
- `SHOW(...)` / `#print(...)` output
- Comments: `// one line` and `{{ multi-line }}`

### Running a legacy program
```bash
python main.py            # runs src/app.el (edit main.py / the file path)
```

See `examples/*.el` for runnable samples (hello world, fibonacci, calculator,
file operations, control flow).
