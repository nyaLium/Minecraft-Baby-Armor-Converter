# -*- coding: utf-8 -*-
"""Geometry of the vanilla 26.3 baby humanoid armor model (and its adult source).

Everything here was read out of the 26.3 client jar:

    net/minecraft/client/model/HumanoidModel
        createBaseArmorMesh(CubeDeformation)      -> adult armor cube list
        createBabyArmorMesh(CubeDeformation, PartPose) -> baby armor cube list
        ADULT_ARMOR_PARTS_PER_SLOT / BABY_ARMOR_PARTS_PER_SLOT
    net/minecraft/client/renderer/entity/layers/HumanoidArmorLayer
        a baby uses LayerType.HUMANOID_BABY for *every* slot (leggings included),
        which is why `humanoid_baby` is a single 64x64 texture containing head,
        chest, waist, legs and feet, while adults need `humanoid` + `humanoid_leggings`.

A box is described by (u, v, w, h, d): texture origin and cube size in pixels.
"""

# ---------------------------------------------------------------- adult side
# (u, v, w, h, d) -- one cube per part, matching HumanoidModel.createMesh(d, 0)
# for head/body/arms and createBaseArmorMesh for the legs.
ADULT = {
    "humanoid": {
        "head": (0, 0, 8, 8, 8),
        "hat": (32, 0, 8, 8, 8),          # helmet overlay, not used by these 9 materials
        "body": (16, 16, 8, 12, 4),
        "right_arm": (40, 16, 4, 12, 4),
        "left_arm": (40, 16, 4, 12, 4),   # mirrored copy of right_arm
        "right_leg": (0, 16, 4, 12, 4),
        "left_leg": (0, 16, 4, 12, 4),    # mirrored copy of right_leg
    },
    "humanoid_leggings": {
        "body": (16, 16, 8, 12, 4),
        "right_leg": (0, 16, 4, 12, 4),
        "left_leg": (0, 16, 4, 12, 4),
    },
}

# ----------------------------------------------------------------- baby side
# createBabyArmorMesh: (u, v, w, h, d).  `hat` is an empty cube list (no texels).
BABY = {
    "head": (0, 0, 9, 8, 8),
    "body": (0, 17, 6, 5, 3),
    "waist": (0, 36, 5.9, 2, 2.9),
    "left_arm": (30, 17, 2, 5, 3),
    "right_arm": (30, 25, 2, 5, 3),
    "inner_body": (0, 17, 6, 5, 3),       # same texels as `body`
    "left_leg": (18, 24, 3, 4, 3),
    "right_leg": (18, 17, 3, 4, 3),
    "right_foot": (0, 25, 3, 1, 3),
    "left_foot": (0, 29, 3, 1, 3),
}

# BABY_ARMOR_PARTS_PER_SLOT
SLOT_PARTS = {
    "head": {"head"},
    "chest": {"body", "left_arm", "right_arm"},
    "legs": {"left_leg", "right_leg", "waist"},
    "feet": {"left_foot", "right_foot"},
}

# where each baby region takes its pixels from: (adult texture, adult part,
# window) -- `window` is the vertical slice of the adult face to use, as a
# fraction (0..1) of the face height.
SOURCES = {
    "head": ("humanoid", "head", (0.0, 1.0)),
    "body": ("humanoid", "body", (0.0, 1.0)),
    "waist": ("humanoid_leggings", "body", (0.0, 0.25)),
    "left_arm": ("humanoid", "left_arm", (0.0, 1.0)),
    "right_arm": ("humanoid", "right_arm", (0.0, 1.0)),
    "left_leg": ("humanoid_leggings", "left_leg", (0.0, 1.0)),
    "right_leg": ("humanoid_leggings", "right_leg", (0.0, 1.0)),
    "right_foot": ("humanoid", "right_leg", (0.66, 1.0)),
    "left_foot": ("humanoid", "left_leg", (0.66, 1.0)),
}

FACES = ("north", "east", "south", "west", "up", "down")

# when a material ships only `humanoid_leggings` (belts, stockings, boots), the
# feet take the boot band of the leggings' leg face instead of the humanoid one
FOOT_FALLBACK = ("right_leg", (0.66, 1.0))


def face_rects(box):
    """(u, v, w, h, d) -> {face: (x0, y0, x1, y1)} in texture pixels."""
    u, v, w, h, d = box
    return {
        "north": (u + d, v + d, u + d + w, v + d + h),
        "east": (u, v + d, u + d, v + d + h),
        "south": (u + 2 * d + w, v + d, u + 2 * d + 2 * w, v + d + h),
        "west": (u + d + w, v + d, u + 2 * d + w, v + d + h),
        "up": (u + d, v, u + d + w, v + d),
        "down": (u + d + w, v, u + 2 * w + d, v + d),
    }


def windowed(rect, window):
    """Slice a face rect vertically (the v axis) by `window` = (t0, t1)."""
    x0, y0, x1, y1 = rect
    t0, t1 = window
    dy = (y1 - y0)
    return (x0, y0 + dy * t0, x1, y0 + dy * t1)


def part_bbox(box, pad=0.0):
    """Texture bounding box covered by a part's six faces."""
    rects = face_rects(box).values()
    x0 = min(r[0] for r in rects) - pad
    y0 = min(r[1] for r in rects) - pad
    x1 = max(r[2] for r in rects) + pad
    y1 = max(r[3] for r in rects) + pad
    return (x0, y0, x1, y1)


def slot_of(part):
    for slot, parts in SLOT_PARTS.items():
        if part in parts:
            return slot
    return None
