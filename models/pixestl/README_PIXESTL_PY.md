## PIXEstL (Python port)

This workspace contains the original Java project in `models/PIXEstL/` and a Python port in `pixestl/`.

### Install

```bash
python -m pip install -r requirements-pixestl.txt
```

### Run (same flags as the Java CLI)

Example (same as `test_pixestl.sh`, but using Python):

```bash
python -m pixestl -p repositories/pixestl/filament-palette-0.10mm.json -w 130 -d RGB -i images/tiger.jpg
```

This generates a zip (default: `<image>.zip`) containing:
- `image-color-preview.png` (if `-z true`)
- `image-texture-preview.png` (if `-Z true`)
- `layer-plate.stl`
- `layer-<filament(s)>.stl` (one or more)
- `layer-texture-White[...].stl` (if `-Z true`)
- `instructions.txt` (only in ADDITIVE mode)

