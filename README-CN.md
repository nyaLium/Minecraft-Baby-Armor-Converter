# 幼年盔甲纹理转换器 · Baby Armor Converter

成年每套盔甲有两张 64×32（`humanoid` + `humanoid_leggings`），幼年只有一张 64×64
（`humanoid_baby`）。本工具一次把两张合成一张，颜色、纹理走向、露脸开口都保留。

## 功能

- 两张成年贴图 → 一张幼年贴图：`humanoid` + `humanoid_leggings` → `humanoid_baby`
- 只有 `humanoid_leggings` 的材质也能转
- **最近邻 + 覆盖采样**：不做平滑、保留像素颗粒；缩小规格时不会漏掉 1 像素的条纹，左右两半保持一致
- **左右镜像**：幼年模型的左右手/腿不共享贴图，左边按原纹理镜像绘制，
  不会出现"两只右手"、"两条右腿"
- 输出分辨率**跟随源纹理**，不写死：64×32 → 64×64，128×64 → 128×128
- 源贴图不是 2:1（例如已经是 64×64）会被跳过并提示，避免把幼年贴图当成年贴图再转一遍
- 不需要安装 Python，运行库在 `_engine\python`
- 只生成贴图，不改资源包

## 用法

**1.** 把资源包的 `equipment` 文件夹整个放到本目录，和 `Transformer.bat` 同级：

```
ArmorBabyConverter\
├─ Transformer.bat
├─ equipment\
│  ├─ humanoid\<材质>.png
│  └─ humanoid_leggings\<材质>.png
└─ output\                    ← 转换结果
```

**2.** 双击 `Transformer.bat`

**3.** 结果在 `output\humanoid_baby\<材质>.png`

要转换别的位置，把那个文件夹（或几个 png）拖到 `Transformer.bat` 上即可。

## 细节

| 情况 | 结果 |
| --- | --- |
| 有 `humanoid_leggings` | 腰带和腿取自护腿那张 |
| 没有（如 `turtle_scute`） | 用 `humanoid` 顶替，日志里提示 |
| 源贴图是 2:1（64×32、128×64…） | 正常转换，输出边长 = 源宽度 × 2 |
| 源贴图不是 2:1（64×64…） | 跳过，并在日志里说明 |

控制台语言跟随系统：中文 Windows 中文，英文 Windows 英文。
想强制英文：先 `set ABC_EN=1` 再运行。

## 环境

Windows 64 位（Win8.1 及以上），内置 Python 3.12。解压即用，整个文件夹可以随便搬。
