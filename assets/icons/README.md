# MatyOS file-type icons

A black-and-white icon set for the MatyOS file types. One minimalist rounded
tile per type, each carrying an invented mathematical glyph; the sealed project
archive is inverted (white-on-black) with a spine binding to read as a *bundle
of files*.

![MatyOS file icons](contact_sheet.png)

| Icon | Extension | Glyph | Meaning |
|------|-----------|-------|---------|
| `Σ` (inverted) | `.matyos` | Sigma | the sealed project archive — a *sigma of files* (theories + theorems + proofs + tests) |
| `∀` | `.thm`  | for-all | a theorem **statement** |
| `∎` | `.prf`  | QED | a **proof** (kernel-checked) |
| `∃` | `.hyp`  | there-exists | a **hypothesis / conjecture** (assumed — *realistic*) |
| `✓` | `.test` | check | a **test** / experiment |
| `λ` | `.elk`  | lambda | **definitions & datatypes** (the vocabulary) |

Each type ships as `NAME.svg` (scalable source of truth), `NAME.png` (256px), and
`NAME.ico` (multi-size, for OS file association). Regenerate with:

```
python assets/icons/generate_icons.py
```

Black & white only for now; a colour pass can come later by editing the palette
constants in `generate_icons.py`.
