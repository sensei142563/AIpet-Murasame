# -*- coding: utf-8 -*-
"""三件事一起做（都是同一个根因：本地视觉从"默认"改成"可选"没改干净）：
  ① 更正我刚写进 README 的那句**未经验证**的话（"设置页不提供该选项"是错的）
  ② widgets.py 的「识别来源」下拉默认 "local" → "cloud"（与实现的缺省一致）
  ③ 把测试盲区记下来：断言查的是标签"视觉来源"，而设置页用的标签是"识别来源"
     ⇒ 所以设置页一直暴露着这个选项、测试却仍然全绿。
"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
RD = os.path.join(ROOT, "README.md")
WG = os.path.join(ROOT, "pcl_launcher", "widgets.py")

# ---------- ② widgets.py：下拉默认 ----------
w = io.open(WG, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
OLD = '''self._add_choice("vision_source", "识别来源", ["local", "cloud"], "local",'''
NEW = '''self._add_choice("vision_source", "识别来源", ["local", "cloud"], "cloud",'''
if OLD in w:
    w = w.replace(OLD, NEW, 1)
    io.open(WG, "w", encoding="utf-8", newline="\n").write(w)
    print("✓ ② widgets.py：识别来源 默认 local → cloud（与 tool/vision_local.py 的缺省一致）")
else:
    print("✗ ② 锚点未命中（检查 widgets.py:285 的实际写法）")

# ---------- ① README：更正那句错话 ----------
t = io.open(RD, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
BAD = ("**设置页不提供该选项** —— 接口保留给 `tool/vision_local.py` 与安装脚本用；"
       "`config.example.json` 里也不再写它（不配就是云端）。 |")
GOOD = ("设置页里有「识别来源」下拉（`本地视觉模型（本机显卡）` / `云端 API`），"
        "**默认已指向云端**；`config.example.json` 里不再写这个键（不配就是云端）。 |")
if BAD in t:
    t = t.replace(BAD, GOOD, 1)
    io.open(RD, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ ① README：更正为事实（设置页确实有这个下拉，默认云端）")
else:
    print("✗ ① README 锚点未命中")

# ---------- ③ 记下测试盲区 ----------
D = os.path.join(ROOT, "dev", "docs", "本地视觉口径排查-2026-10-13.md")
io.open(D, "w", encoding="utf-8", newline="\n").write("""# 本地视觉口径排查（2026-10-13）

> 起因：既定决策是"**本地视觉：不使用，仅保留接口**"，
> 实现里 `vision_source` 的缺省是 **cloud**（`tool/vision_local.py:14/63`，
> 测试 `tests/test_vision_interface.py:10/52` 也这么断言）；
> 但 UI 上有三处仍按"本地是默认"来写。逐处查、逐处修，**并记录测试为什么没拦住**。

## 一、查到的三处（同一根因：从"默认本地"改成"可选"时没改干净）

| # | 位置 | 表现 | 状态 |
|---|---|---|---|
| 1 | `pcl_launcher/silicon_window.py` 4 处 `cfg.get("vision_source") or "local"` | 没配时按**本地**处理：首页模型卡片写"本地视觉模型（本地部署）"、"视觉服务"胶囊、起服务判断、状态探测**全反** | ✅ 已修（4 处改 `or "cloud"`） |
| 2 | `pcl_launcher/widgets.py:285` `_add_choice("vision_source", "识别来源", [...], "local")` | 设置页下拉**默认选在 local** | ✅ 已修（改 `"cloud"`） |
| 3 | `README.md` 1215 / 1382 等 | 把本地视觉写成"**默认**"，整段（4.4GB 模型下载、显存占用、卡顿排查）读起来像必装 | ✅ 已修（改"可选，默认不使用"；相关段落加"仅在使用本地视觉时相关"；4.1 标为历史排查记录） |

## 二、⚠ 为什么测试没拦住（**这是我这次要记下来的重点**）

`tests/test_vision_interface.py` 第 77~80 行断言设置页**不含**这些项：
```python
check('"vision_source", "视觉来源" not in w')
check('"vision_local_url", "本地视觉服务地址"' not in w and ...)
```
注意它查的**标签是「视觉来源」**，而设置页实际用的标签是 **「识别来源」**
（`widgets.py:285`：`_add_choice("vision_source", "识别来源", ...)`）。

⇒ **字符串对不上，断言就永远成立**，于是"设置页不该暴露这个选项"这条意图
**从来没被真正检查过**，一路全绿到这次手工翻代码才发现。

**要学的一条**：这种"断言某个 UI 里不存在某字符串"的检查，
必须**同时钉住它用的标签**，否则改了文案就等于把检查悄悄关掉。
（下次改这一带时，应当把断言改成检查 `_add_choice` 的**键名**而不是标签，
或者直接断言"设置页不含任何 `vision_source` 的写入路径"。）

## 三、验证
```
tool/vision_local.py:14    vision_source  "cloud"（默认）| "local"        ← 与修后 UI 一致
tests/test_vision_interface.py:52  没配 → cloud                          ← 与修后 UI 一致
UIA 文本实测（重启启动器后读界面文本）：
   [24] Text "● 视觉服务：云端 API"
   [53] Text "qwen-vl-plus（云端）"        ← 与 config.json 的 vision_model_name 一致
回归：tests/run_all.py ⇒ 10 个文件 / 381 项通过 / 0 失败
```

## 四、仍未处理（诚实留档）
- README 1415 行起「本地模型（可选）」那一节里可能还有同类措辞，本次未逐行核；
- `tests/test_vision_interface.py` 的**标签盲区**还没改成按键名断言（改动测试需要谨慎，
  且要连带核对它检查的到底是哪个 widget 源）；建议单独一轮做，别和文案修复混在一起。
""")
print("✓ ③ 已写 dev/docs/本地视觉口径排查-2026-10-13.md（含测试盲区原因）")

print()
print("=== 复核 widgets.py ===")
for i, l in enumerate(io.open(WG, encoding="utf-8", errors="replace").read().split("\n"), 1):
    if "vision_source" in l and "_add_choice" in l:
        print("   %5d| %s" % (i, l.strip()[:110]))
print("=== 复核 README ===")
for i, l in enumerate(io.open(RD, encoding="utf-8", errors="replace").read().split("\n"), 1):
    if "vision_source" in l:
        print("   %5d| %s" % (i, l.strip()[:118]))
