#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""babyfy.py -- 幼年盔甲纹理转换器 引擎 / baby armor texture converter engine

由 Transformer.bat 调用。

默认行为：把本目录下的 equipment\ 转成 output\humanoid_baby\。

    equipment\humanoid\<材质>.png            成年 64x32
    equipment\humanoid_leggings\<材质>.png   成年 64x32（可缺）

固定规则（不开放选项，避免转错）：
    * 最近邻采样，保持像素风
    * 输出分辨率跟随源纹理：64x32 -> 64x64，128x64 -> 128x128
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)            # 工具根目录，Transformer.bat 所在处
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import armor_babyfy as A                # noqa: E402

DEFAULT_INPUT = os.path.join(ROOT, "equipment")
DEFAULT_OUTPUT = os.path.join(ROOT, "output")

LANG = "en"
MODE_FLAGS = {
    "--zh": "zh", "-zh": "zh", "--chinese": "zh",
    "--en": "en", "-en": "en", "--english": "en",
}


def t(en, zh):
    return zh if LANG == "zh" else en


def usage():
    print()
    print(t("usage:", "用法："))
    print(t("  Transformer.bat                       convert .\\equipment",
            "  Transformer.bat                       转换 .\\equipment"))
    print(t("  Transformer.bat <folder or png...>    convert something else",
            "  Transformer.bat <文件夹 或 png...>    转换别的位置"))
    print()
    print(t("Put the pack's equipment folder here, next to this bat:",
            "把资源包的 equipment 文件夹放在这里，和本 bat 同级："))
    print("  %s" % DEFAULT_INPUT)
    print(t("    humanoid\\<material>.png", "    humanoid\\<材质>.png"))
    print(t("    humanoid_leggings\\<material>.png",
            "    humanoid_leggings\\<材质>.png"))


def _add_png(path, pairs, warn):
    name = os.path.basename(path)
    folder = os.path.dirname(path)
    leggings = None
    for candidate in (os.path.join(os.path.dirname(folder),
                                   "humanoid_leggings", name),
                      os.path.join(folder, "humanoid_leggings", name)):
        if os.path.exists(candidate):
            leggings = candidate
            break
    if name in pairs:
        warn(t("duplicate name, keeping the first: %s" % name,
               "重名，保留第一个：%s" % name))
        return
    pairs[name] = (path, leggings)


def _add_folder(folder, pairs, warn):
    humanoid = os.path.join(folder, "humanoid")
    if not os.path.isdir(humanoid):
        if os.path.basename(folder).lower() == "humanoid":
            humanoid = folder
        elif any(n.lower().endswith(".png") for n in os.listdir(folder)):
            humanoid = folder
        else:
            warn(t("no humanoid\\ folder inside: %s" % folder,
                   "里面没有 humanoid\\ 文件夹：%s" % folder))
            return
    leggings_dir = os.path.join(os.path.dirname(humanoid), "humanoid_leggings")
    if not os.path.isdir(leggings_dir):
        leggings_dir = None
    for name in sorted(os.listdir(humanoid)):
        if not name.lower().endswith(".png"):
            continue
        leggings = None
        if leggings_dir:
            candidate = os.path.join(leggings_dir, name)
            if os.path.exists(candidate):
                leggings = candidate
        if name in pairs:
            warn(t("duplicate name, keeping the first: %s" % name,
                   "重名，保留第一个：%s" % name))
            continue
        pairs[name] = (os.path.join(humanoid, name), leggings)
    # legwear (belts, stockings, boots) often ships only humanoid_leggings\
    if leggings_dir:
        for name in sorted(os.listdir(leggings_dir)):
            if not name.lower().endswith(".png") or name in pairs:
                continue
            pairs[name] = (None, os.path.join(leggings_dir, name))


def main(argv):
    global LANG
    for a in argv:
        if a.lower() in MODE_FLAGS:
            LANG = MODE_FLAGS[a.lower()]

    out = None
    paths = []
    i = 0
    while i < len(argv):
        a = argv[i]
        low = a.lower()
        if low in MODE_FLAGS:
            i += 1
            continue
        if low in ("--out", "-o"):
            if i + 1 >= len(argv):
                raise SystemExit("--out needs a folder")
            out = argv[i + 1]
            i += 2
            continue
        if low in ("-h", "--help", "/?"):
            usage()
            return 0
        if low.startswith("-"):
            print(t("  ignored option %s" % a, "  忽略未知选项 %s" % a))
            i += 1
            continue
        paths.append(a)
        i += 1

    print("=" * 68)
    print(t(" Baby armor converter  ·  adult armor textures -> baby armor",
            " 幼年盔甲纹理转换器  ·  成年盔甲纹理 -> 幼年盔甲纹理"))
    print("=" * 68)

    warnings = []
    pairs = {}
    if not paths:
        if not os.path.isdir(DEFAULT_INPUT):
            print(t("\nNo equipment\\ folder here: %s" % DEFAULT_INPUT,
                    "\n这里没有 equipment 文件夹：%s" % DEFAULT_INPUT))
            usage()
            return 1
        paths = [DEFAULT_INPUT]

    for raw in paths:
        path = os.path.abspath(raw)
        if os.path.isdir(path):
            before = len(pairs)
            _add_folder(path, pairs, warnings.append)
            print(t("  folder  %s  (%d texture(s))" % (path, len(pairs) - before),
                    "  目录    %s  （%d 张纹理）" % (path, len(pairs) - before)))
        elif path.lower().endswith(".png") and os.path.exists(path):
            _add_png(path, pairs, warnings.append)
            print(t("  file    %s" % path, "  文件    %s" % path))
        else:
            print(t("  ignored %s" % path, "  忽略    %s" % path))

    for w in warnings:
        print("  ! %s" % w)
    if not pairs:
        print(t("\nNo armor texture found.", "\n没找到盔甲纹理。"))
        return 2

    out = out or DEFAULT_OUTPUT
    out_dir = os.path.join(out, "humanoid_baby")
    os.makedirs(out_dir, exist_ok=True)
    print()
    print(t("  %d texture(s) -> %s" % (len(pairs), out_dir),
            "  共 %d 张 -> %s" % (len(pairs), out_dir)))
    print(t("  nearest neighbour, output follows the source size",
            "  最近邻采样，输出分辨率跟随源纹理"))
    print()

    ok = 0
    skipped = 0
    for name in sorted(pairs):
        humanoid_path, leggings_path = pairs[name]
        try:
            humanoid = A.open_rgba(humanoid_path) if humanoid_path else None
            leggings = A.open_rgba(leggings_path) if leggings_path else None
            ref = humanoid if humanoid is not None else leggings
            if ref.width != ref.height * 2:
                skipped += 1
                print(t("  skipped  %-22s %dx%d is not an adult armor texture "
                        "(expected 64x32 or a multiple)"
                        % (name, ref.width, ref.height),
                        "  跳过     %-22s %d×%d 不是成年盔甲纹理（应为 64×32 或倍数）"
                        % (name, ref.width, ref.height)))
                continue
            notes = []
            image = A.convert(humanoid, leggings, False, notes.append, None, True)
            image.save(os.path.join(out_dir, name))
            ok += 1
            tag_en = "" if humanoid is not None else "   (leggings only)"
            tag_zh = "" if humanoid is not None else "   （只有护腿）"
            print(t("  ok       %-22s -> humanoid_baby/%s  %dx%d%s"
                    % (name, name, image.width, image.height,
                       tag_en or ("" if leggings_path else "   (no leggings)")),
                    "  完成     %-22s -> humanoid_baby/%s  %d×%d%s"
                    % (name, name, image.width, image.height,
                       tag_zh or ("" if leggings_path else "   （无护腿贴图）"))))
            for note in notes:
                if "no leggings" in note:
                    note = t(note, "没有护腿贴图——腰带和腿部取自第 1 层"
                                   "（靴子那张）贴图")
                elif "no humanoid" in note:
                    note = t(note, "没有胸甲贴图——头/胸/手臂留空（这是裤装/靴类）")
                print("           ! %s" % note)
        except Exception as exc:                       # noqa: BLE001
            skipped += 1
            print(t("  failed   %-22s %s" % (name, exc),
                    "  失败     %-22s %s" % (name, exc)))

    print()
    print(t("Done: %d converted, %d skipped." % (ok, skipped),
            "完成：%d 张已转换，%d 张跳过。" % (ok, skipped)))
    print(t("Output: %s" % out_dir, "输出：%s" % out_dir))
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
