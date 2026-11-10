# -*- coding: utf-8 -*-
r"""armor_babyfy.py -- adult humanoid armor textures -> baby armor texture

26.3 renders baby armor with a dedicated model, so a baby needs
`textures/entity/equipment/humanoid_baby/<material>.png` (64x64) instead of the
adult pair `humanoid/<material>.png` + `humanoid_leggings/<material>.png`
(both 64x32).  `HumanoidArmorLayer` uses HUMANOID_BABY for *every* slot when the
entity is a baby, so the baby file has to contain helmet, chest, waist, legs and
feet at once.

    adult source                         baby target
    ---------------------------------    -----------------------------------
    humanoid      head      (0,0) 8x8x8  head       (0,0)   9x8x8
    humanoid      body      (16,16)      body       (0,17)  6x5x3
    humanoid      left_arm  (40,16)      left_arm   (30,17) 2x5x3   (mirrored)
    humanoid      right_arm (40,16)      right_arm  (30,25) 2x5x3
    leggings      body      (16,16)      waist      (0,36)  5.9x2x2.9  (top band)
    leggings      right_leg (0,16)       right_leg  (18,17) 3x4x3
    leggings      left_leg  (0,16)       left_leg   (18,24) 3x4x3   (mirrored)
    humanoid      right_leg (0,16)       right_foot (0,25)  3x1x3      (boot band)
    humanoid      left_leg  (0,16)       left_foot  (0,29)  3x1x3      (boot band)

Three details that are easy to get wrong:

* **Mirroring.** The baby model does not mirror its left limbs (the adult model
  does, which is why the adult art is shared by both arms).  Vanilla therefore
  paints `left_arm` / `left_leg` as the *horizontal mirror* of the right ones;
  copying them straight produces "two right hands".  The mirrored art is applied
  per face, on the four side faces only (up/down match on both sides in vanilla).
* **Coverage sampling.** Squeezing 8 texels onto 6 with plain nearest sampling
  skips whole source columns, so a 1px stripe on one half of a face disappears
  on the other half -- the two sides stop matching.  A destination texel therefore
  also accepts a source texel whose centre lies inside the area it covers; those
  areas tile the source, so nothing is skipped and the silhouette follows the
  original shape.  `--no-coverage` restores the plain nearest behaviour.
* **Leggings-only materials.** Belts, stockings and boots often ship only
  `humanoid_leggings/`.  Those still convert: waist/legs/feet come from the
  leggings texture, head/chest stay empty (that is all the item covers).

Usage:
    python armor_babyfy.py --src equipment --out equipment_baby
    python armor_babyfy.py --humanoid iron.png --leggings iron_leggings.png --out iron_baby.png
"""
from __future__ import annotations

import argparse
import math
import os
import sys

try:                                                  # Pillow is optional ...
    from PIL import Image as _PILImage
except ImportError:                                   # pragma: no cover
    _PILImage = None                                  # ... pngio.py takes over

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import baby_armor_model as M                          # noqa: E402

_pngio = None


def _png():
    """Lazy import so Pillow users never touch the fallback codec."""
    global _pngio
    if _pngio is None:
        import pngio
        _pngio = pngio
    return _pngio


BACKEND = "Pillow" if _PILImage is not None else "pngio (built-in)"

# parts whose art must be mirrored (the model does not mirror them)
MIRROR_PARTS = ("left_arm", "left_leg")
# only the four side faces are mirrored in vanilla
SIDE_FACES = ("north", "east", "south", "west")


def open_rgba(path):
    """Read any PNG as an 8-bit RGBA raster."""
    if _PILImage is not None:
        return _PILImage.open(path).convert("RGBA")
    return _png().PNGImage.load(path)


def new_image(size, colour=(0, 0, 0, 0)):
    if _PILImage is not None:
        return _PILImage.new("RGBA", size, colour)
    return _png().PNGImage.new(size, colour)


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def sample(img, x, y, bilinear):
    """Sample at a float texture coordinate (texel centres at .5)."""
    w, h = img.size
    if not bilinear:
        return img.getpixel((_clamp(int(x), 0, w - 1), _clamp(int(y), 0, h - 1)))
    x -= 0.5
    y -= 0.5
    x0, y0 = int(x // 1), int(y // 1)
    fx, fy = x - x0, y - y0
    out = [0.0, 0.0, 0.0, 0.0]
    for dy, wy in ((0, 1.0 - fy), (1, fy)):
        for dx, wx in ((0, 1.0 - fx), (1, fx)):
            weight = wx * wy
            if weight <= 0.0:
                continue
            px = img.getpixel((_clamp(x0 + dx, 0, w - 1), _clamp(y0 + dy, 0, h - 1)))
            for i in range(4):
                out[i] += px[i] * weight
    return tuple(int(round(v)) for v in out)


def opaque_near(img, x, y, half_w, half_h):
    """Nearest opaque texel around (x, y), or None.

    `x`/`y` are float coordinates; only texels whose centre lies within +-half of
    them are considered, so an upscaled face (half < 0.5) keeps its exact pixel
    and a squeezed face gains the neighbour that covers the hole.
    """
    w, h = img.size
    cx, cy = x - 0.5, y - 0.5                 # texel-centre space
    x0 = int(math.ceil(cx - half_w))
    x1 = int(math.floor(cx + half_w))
    y0 = int(math.ceil(cy - half_h))
    y1 = int(math.floor(cy + half_h))
    best = None
    best_d = 1e9
    for iy in range(max(0, y0), min(h - 1, y1) + 1):
        for ix in range(max(0, x0), min(w - 1, x1) + 1):
            px = img.getpixel((ix, iy))
            if px[3] < 8:
                continue
            d = (ix - cx) ** 2 + (iy - cy) ** 2
            if d < best_d:
                best_d = d
                best = px
    return best


def blit_face(dst, img, src_rect, dst_rect, bilinear, flip=False, coverage=True):
    """Map every texel inside `dst_rect` from the matching spot in `src_rect`.

    With `coverage` (default) a destination texel is allowed to draw any source
    texel whose **centre** falls inside the area it covers.  When downscaling,
    those areas tile the source exactly, so a 1px strip can never be skipped --
    which is what makes the left and right halves of a face stay symmetric
    (nearest alone drops every other column on an 8 -> 6 squeeze).
    """
    sx0, sy0, sx1, sy1 = src_rect
    dx0, dy0, dx1, dy1 = dst_rect
    sw, sh = sx1 - sx0, sy1 - sy0
    dw, dh = dx1 - dx0, dy1 - dy0
    if sw <= 0 or sh <= 0 or dw <= 0 or dh <= 0:
        return
    kx, ky = abs(sw) / dw, abs(sh) / dh          # source texels per dest texel
    for y in range(int(dy0 // 1), int(-(-dy1 // 1))):
        cy = y + 0.5
        if not (dy0 <= cy < dy1):
            continue
        ty = (cy - dy0) / dh
        for x in range(int(dx0 // 1), int(-(-dx1 // 1))):
            cx = x + 0.5
            if not (dx0 <= cx < dx1):
                continue
            tx = (cx - dx0) / dw
            if flip:
                tx = 1.0 - tx
            sx = sx0 + tx * sw
            sy = sy0 + ty * sh
            px = sample(img, sx, sy, bilinear)
            if coverage and px[3] < 8:
                fill = opaque_near(img, sx, sy, 0.5 * kx, 0.5 * ky)
                if fill is not None:
                    px = fill
            dst.putpixel((_clamp(x, 0, dst.width - 1), _clamp(y, 0, dst.height - 1)),
                         px)


def _auto_window(img, rects, default):
    """Fit a window to the rows that actually carry art.

    A belt texture paints one thin band somewhere in the leggings torso; a fixed
    "top quarter" window then samples empty texels and the baby part comes out
    invisible.  Measuring the painted rows keeps the part's outline following
    the original art instead.
    """
    side = [rects[f] for f in SIDE_FACES]
    top = min(r[1] for r in side)
    bottom = max(r[3] for r in side)
    rows = []
    for y in range(int(round(top)), int(round(bottom))):
        for x0, _, x1, _ in side:
            if any(img.getpixel((x, y))[3] > 8
                   for x in range(int(round(x0)), int(round(x1)))):
                rows.append(y)
                break
    if not rows:
        return default
    height = float(bottom - top) or 1.0
    return ((rows[0] - top) / height, (rows[-1] + 1 - top) / height)


def convert(humanoid, leggings, bilinear=False, warn=None, scale=None,
            coverage=True):
    """Adult humanoid (+ leggings) images -> baby humanoid texture.

    Either image may be None: legwear items ship only `humanoid_leggings`, in
    which case the head/chest areas simply stay transparent.

    `scale` follows the source resolution (an HD 128x64 adult texture produces
    a 128x128 baby texture); pass 1.0 to force the vanilla 64x64 grid.
    """
    if humanoid is None and leggings is None:
        raise ValueError("need at least one adult texture")
    primary = humanoid if humanoid is not None else leggings
    if primary.width < 64 or primary.height < 32:
        raise ValueError("texture is %dx%d, expected at least 64x32"
                         % (primary.width, primary.height))

    src = {
        "humanoid": humanoid.convert("RGBA") if humanoid is not None else None,
        "humanoid_leggings": (leggings.convert("RGBA")
                              if leggings is not None else None),
    }
    if scale is None:
        scale = primary.width / 64.0
    if src["humanoid_leggings"] is None:
        src["humanoid_leggings"] = src["humanoid"]
        if warn:
            warn("no leggings texture - waist/legs are taken from the layer 1 "
                 "texture (boots art)")
    if src["humanoid"] is None and warn:
        warn("no humanoid texture - head/chest/arms stay empty (legwear only)")

    out = new_image((int(round(64 * scale)), int(round(64 * scale))),
                    (0, 0, 0, 0))
    for part, (tex, apart, window) in M.SOURCES.items():
        image = src[tex]
        if image is None:
            if part.startswith(("left_foot", "right_foot")):
                image = src["humanoid_leggings"]
                apart, window = M.FOOT_FALLBACK
            else:
                continue
        box = M.BABY[part]
        adult_box = M.ADULT[tex][apart]
        adult_rects = M.face_rects(adult_box)
        if window != (0.0, 1.0):
            # waist / boot bands: follow the painted rows of the source
            window = _auto_window(image, adult_rects, window)
        baby_rects = M.face_rects(box)
        for face in M.FACES:
            src_face = face
            if part in MIRROR_PARTS:
                # the mirrored limb swaps its two side faces: the art that the
                # adult renders on its outer side must land on the baby's outer
                # side, which is the opposite rect of the block
                src_face = {"east": "west", "west": "east"}.get(face, face)
            src_rect = tuple(v * scale
                             for v in M.windowed(adult_rects[src_face], window))
            dst_rect = tuple(v * scale for v in baby_rects[face])
            flip = part in MIRROR_PARTS and face in SIDE_FACES
            blit_face(out, image, src_rect, dst_rect, bilinear,
                      flip=flip, coverage=coverage)
    return out


def name_pairs(src_dir):
    """Yield (name, humanoid_path_or_None, leggings_path_or_None)."""
    hum = os.path.join(src_dir, "humanoid")
    leg = os.path.join(src_dir, "humanoid_leggings")
    seen = set()
    if os.path.isdir(hum):
        for name in sorted(os.listdir(hum)):
            if not name.lower().endswith(".png"):
                continue
            lp = os.path.join(leg, name)
            seen.add(name)
            yield name, os.path.join(hum, name), (lp if os.path.exists(lp) else None)
    if os.path.isdir(leg):
        for name in sorted(os.listdir(leg)):
            if not name.lower().endswith(".png") or name in seen:
                continue
            yield name, None, os.path.join(leg, name)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Convert adult humanoid armor textures into the 26.3 baby layout.")
    ap.add_argument("--src", help="folder containing humanoid/ and humanoid_leggings/")
    ap.add_argument("--out", required=True, help="output folder or .png file")
    ap.add_argument("--humanoid", help="single adult humanoid texture")
    ap.add_argument("--leggings", help="single adult humanoid_leggings texture")
    ap.add_argument("--resolution", type=int, default=0,
                    help="force a baby texture resolution (default: follow the adult one)")
    ap.add_argument("--filter", choices=("nearest", "linear"), default="nearest",
                    help="resampling filter (default: nearest, keeps the pixel look)")
    ap.add_argument("--no-coverage", action="store_true",
                    help="plain nearest sampling (may drop 1px stripes when "
                         "downscaling)")
    args = ap.parse_args(argv)

    bilinear = args.filter == "linear"
    coverage = not args.no_coverage
    scale = (args.resolution / 64.0) if args.resolution else None
    warnings = []
    warn = warnings.append

    if args.humanoid or args.leggings:
        hum = open_rgba(args.humanoid) if args.humanoid else None
        leg = open_rgba(args.leggings) if args.leggings else None
        img = convert(hum, leg, bilinear, warn, scale, coverage)
        dst = args.out
        if os.path.isdir(dst) or not dst.lower().endswith(".png"):
            os.makedirs(dst, exist_ok=True)
            dst = os.path.join(dst, os.path.basename(args.humanoid or args.leggings))
        else:
            os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
        img.save(dst)
        print("  %-28s -> %s" % (os.path.basename(args.humanoid or args.leggings), dst))
        for w in warnings:
            print("      ! %s" % w)
        return 0

    if not args.src:
        ap.error("give --src <folder> or --humanoid/--leggings <file>")
    pairs = list(name_pairs(args.src))
    if not pairs:
        print("no humanoid/*.png found under %s" % args.src)
        return 2

    out_dir = os.path.join(args.out, "humanoid_baby")
    os.makedirs(out_dir, exist_ok=True)
    print("adult textures : %s" % args.src)
    print("baby textures  : %s" % out_dir)
    print("filter         : %s" % args.filter)
    print("backend        : %s\n" % BACKEND)
    ok = 0
    for name, hp, lp in pairs:
        warnings = []
        try:
            img = convert(open_rgba(hp) if hp else None,
                          open_rgba(lp) if lp else None,
                          bilinear, warn, scale, coverage)
            img.save(os.path.join(out_dir, name))
            ok += 1
            print("  %-20s -> humanoid_baby/%s%s"
                  % (name, name, "" if hp else "   (leggings only)"))
            for w in warnings:
                print("      ! %s" % w)
        except Exception as exc:                       # noqa: BLE001
            print("  failed: %s -> %s" % (name, exc))
    print("\n%d/%d texture(s) converted" % (ok, len(pairs)))
    return 0 if ok == len(pairs) else 2


if __name__ == "__main__":
    sys.exit(main())
