# Minecraft-Baby-Armor-Converter
Generate baby armor textures from normal armor textures

中文说明：[README-CN.md](README-CN.md)

## Features

- Two adult textures → one baby texture: `humanoid` + `humanoid_leggings` → `humanoid_baby`
- Materials that only ship `humanoid_leggings` convert too:
- **Nearest + coverage sampling** — no smoothing, pixel look preserved; when shrinking, no
  1px stripe is skipped, so both halves of a face stay consistent
- **Mirroring**: the baby model does not share textures between sides, so the left arm
  and leg are painted mirrored — no more "two right hands"
- Output resolution **follows the source**: 64×32 → 64×64, 128×64 → 128×128 (never hard-coded)
- A source that is not 2:1 (e.g. already 64×64) is skipped with a message, so a baby texture
  is never converted a second time
- No Python install needed — the runtime lives in `_engine\python`
- Writes textures only; it never touches your pack

## Usage

**1.** Put the pack's `equipment` folder here, next to `Transformer.bat`:

```
ArmorBabyConverter\
├─ Transformer.bat
├─ equipment\
│  ├─ humanoid\<material>.png
│  └─ humanoid_leggings\<material>.png
└─ output\                    ← results
```

**2.** Double-click `Transformer.bat`

**3.** Results land in `output\humanoid_baby\<material>.png`

To convert something else, drop that folder (or a few PNGs) onto `Transformer.bat`.

## Details

| Case | Result |
| --- | --- |
| `humanoid_leggings` exists | waist and legs come from it |
| it is missing (e.g. `turtle_scute`) | falls back to `humanoid`, the log says so |
| source is 2:1 (64×32, 128×64…) | converted; output side = source width × 2 |
| source is not 2:1 (64×64…) | skipped, with an explanation in the log |

The console follows the system language: Chinese on a Chinese Windows, English otherwise.
Force English with `set ABC_EN=1` before running.

## Requirements

Windows 64-bit (8.1+), bundled Python 3.12. Extract and run — the folder is portable.
