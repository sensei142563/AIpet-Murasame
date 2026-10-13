# -*- coding: utf-8 -*-
"""让 README 的本地视觉口径贴合当前实现与决策：
   决策 = "本地视觉：**不使用**，仅保留接口"；实现 = `vision_source` 缺省 **cloud**
   （tool/vision_local.py:14/63 + tests/test_vision_interface.py:10/52）。
   本脚本只改"口径"，不删任何本地视觉的说明（接口保留，说明也要留）。
"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
R = os.path.join(ROOT, "README.md")

t = io.open(R, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
done = []


def rep(old, new, tag):
    global t
    if old in t:
        t = t.replace(old, new, 1)
        done.append(tag)
    else:
        print("   ✗ 锚点未命中:", tag)


# ---------- 区域一：识别走哪边 ----------
rep("- **本地视觉模型（默认）**：截图交给本机的",
    "- **云端 API（默认）**：走 `vision_model_name` 指定的云端视觉模型。\n"
    "  > 当前版本**默认就是这一条**：`vision_source` 不配（或配成别的值）都按云端走，\n"
    "  > 与原行为完全一致（`tool/vision_local.py` 的取值集合仍是 `(cloud, local)`，\n"
    "  > 接口**保留**，只是不再默认启用）。\n"
    "- **本地视觉模型（可选，默认不使用）**：截图交给本机的",
    "① 本地视觉改标『可选』+ 云端标『默认』")

# 原来紧跟其后的那行"云端 API"现在重复了，合并掉
rep("- **云端 API**：走 `vision_model_name` 指定的云端视觉模型（原来的行为）。\n", "", "①b 去掉重复的『云端 API』行")

rep("**怎么配置／检查**：", "**只有在你要用本地视觉时才需要配置**：", "② 配置段的标题加限定")

rep("> 硬件：本地模型约需 6GB 显存",
    "> **以下几段只在使用本地视觉时相关**（默认走云端的话，不需要模型、不需要配置）。\n"
    ">\n"
    "> 硬件：本地模型约需 6GB 显存",
    "③ 硬件提示前加限定")

rep("#### 4.1 本地视觉为什么会让电脑卡（2026-09-24 实测排查）",
    "#### 4.1 本地视觉为什么会让电脑卡（2026-09-24 实测排查）\n\n"
    "> **本节是历史排查记录**，只在使用本地视觉时才相关；默认走云端不会遇到这些。保留备查。",
    "④ 卡顿排查节加『历史记录』标注")

# ---------- 区域二：配置表 ----------
rep("| `vision_source` | 视觉识别走哪边：`local`（默认，本机视觉模型）/ `cloud`（云端 API，用上面的 `vision_model_name`） |",
    "| `vision_source` | 视觉识别走哪边：**`cloud`（默认）** / `local`（本机视觉模型，可选）。"
    "**设置页不提供该选项** —— 接口保留给 `tool/vision_local.py` 与安装脚本用；"
    "`config.example.json` 里也不再写它（不配就是云端）。 |",
    "⑤ vision_source 行改口径")

rep("| `vision_local_model_dir` | 本地视觉模型目录",
    "| `vision_local_model_dir` | **（仅本地视觉）** 本地视觉模型目录",
    "⑥ 本地视觉相关键加『仅本地视觉』前缀")
for k in ("vision_local_port", "local_api.vision", "vision_runtime_python",
          "vision_device", "vision_idle_unload"):
    if "| `%s` | **（仅本地视觉）**" % k not in t:
        t = t.replace("| `%s` | " % k, "| `%s` | **（仅本地视觉）** " % k, 1)
done.append("⑥b 其余本地视觉键加前缀")

io.open(R, "w", encoding="utf-8", newline="\n").write(t)
print("已改：")
for d in done:
    print("   ✓", d)

print()
print("=== 复核（关键行）===")
for i, l in enumerate(io.open(R, encoding="utf-8", errors="replace").read().split("\n"), 1):
    if any(k in l for k in ("识别走哪边", "本地视觉模型（可选", "云端 API（默认）",
                            "vision_source", "只在使用本地视觉", "历史排查记录")):
        print("   %5d| %s" % (i, l.strip()[:118]))
