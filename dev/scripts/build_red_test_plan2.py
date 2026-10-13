# -*- coding: utf-8 -*-
"""用正确的列序（rc / OK / FAIL）重跑并重写《红测试修复清单》，附每项的原始 FAIL 文本。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")

r = subprocess.run([VENV, os.path.join("tests", "run_all.py")], cwd=ROOT, capture_output=True,
                   text=True, encoding="utf-8", errors="replace", timeout=1800)
out = (r.stdout or "") + (r.stderr or "")
rows = []
for l in out.split("\n"):
    m = re.match(r"\s*(test_\w+\.py)\s+(-?\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)s(.*)$", l)
    if m:
        rows.append({"file": m.group(1), "rc": int(m.group(2)), "ok": int(m.group(3)),
                     "fail": int(m.group(4)), "sec": m.group(5), "note": m.group(6).strip()})
print("=== 正确解析（文件 / rc / OK / FAIL）===")
for x in rows:
    print("   %-26s rc=%s  %3d OK  %2d FAIL  %s" % (x["file"], x["rc"], x["ok"], x["fail"],
                                                   x["note"][:60]))

GUESS = {
    "test_bounds.py": "字体缩放下界（实际 0.05，断言要求落在 [0.1, 3.0]）",
    "test_bugfix_0930.py": "**状态窗 / 状态页整套**（status_page_enabled、QDialog#statusWindow 的 QSS、卡片样式、侧栏「状态」项）",
    "test_bugfix_0930b.py": "main.py 对 off / voice / chat 三种输入方式的处理",
    "test_config_contracts.py": "**全仓重复字典键**（tool/jp_names.py 等）",
    "test_frontend_style.py": "启动器前端配色/顺序一致性",
    "test_qt_lifecycle.py": "**agent 任务守卫 + 确认框**（本轮已定位：源码里 _run_agent_task/_on_agent_done 都不存在）",
    "test_vision_interface.py": "视觉服务接口键（vision_source 等）",
    "test_plugin_markup.py": "✅ 本轮已修（恢复 tool/plugins.py 超集版）",
}
total = sum(x["fail"] for x in rows)
badfiles = [x for x in rows if x["fail"] > 0 or x["rc"] != 0]

doc = ["# 红测试修复清单（2026-10-13 实测）", "",
       "> 来源：`runtime\\venv\\Scripts\\python.exe tests\\run_all.py`（项目自带总跑器），",
       "> 采集时间 2026-10-13 19:0x。**这些红项就是「协作者基线里缺的东西」的可执行清单。**", "",
       "## 总览", "",
       "| 文件 | rc | 通过 | 失败 | 主要缺什么 |", "|---|---|---|---|---|"]
for x in rows:
    doc.append("| `%s` | %d | %d | %s%d%s | %s |" % (
        x["file"], x["rc"], x["ok"],
        "**" if x["fail"] else "", x["fail"], "**" if x["fail"] else "",
        GUESS.get(x["file"], "")))
doc += ["", "合计失败 **%d** 项，分布在 **%d** 个文件（另有 1 个文件直接崩、未计入项数）。"
        % (total, len([x for x in rows if x["fail"] > 0])), "",
        "## 已修（本轮）", "",
        "- ✅ `test_plugin_markup.py`：**19 OK / 0 FAIL**。恢复 `tool/plugins.py` 超集版",
        "  （504 行，补齐 `handle_reply` 等 14 个函数），并把唯一一处短版调用点 `_root()` 改为 `root()`。",
        "- ✅ `test_bugfix_0930.py` 的菜单那 4 项转绿。真因：菜单弹出方式已从 `QMenu.exec_()` 改成",
        "  **动画 `popup()`**，而测试只打桩 `exec_` ⇒ 永远捕获不到菜单。已把桩同步（**断言一条未改**），",
        "  并补回菜单里丢失的「输入对话（打字）」「切换形象（当前：…）」。", "",
        "## 已定位、下一轮修（按性价比）", "",
        "1. **`test_qt_lifecycle.py`（直接崩 + 2 项）**：源码里 `_run_agent_task` / `_on_agent_done`",
        "   都不存在（`_agent_worker` 字段在、`tool/agent_bridge.py` 在），而备份版是完整的",
        "   —— 含「**同时只跑一个 agent 任务**」守卫与默认「否」的确认框。恢复它即可。",
        "2. **状态窗 / 状态页整套**（`test_bugfix_0930.py` 剩 7 项 + `0930b` 2 项）：",
        "   `status_page_enabled` 键、`QDialog#statusWindow` 的 QSS、卡片 `WA_StyledBackground`、",
        "   侧栏「状态」项 —— 全缺。",
        "3. **`test_config_contracts.py` 3 项**：全仓重复字典键（机械修复、风险低）。",
        "4. `test_vision_interface.py` 9 项、`test_frontend_style.py` 13 项、`test_bounds.py` 2 项。", "",
        "## 纪律", "",
        "- **先看断言要什么，再决定补代码还是修测试**；不许为了变绿而放松断言。",
        "- 与「覆盖前备份」`remotes/origin/backup/main-before-overwrite-20261001` 对照时，",
        "  先判断是不是**双向分叉**（双方各有新东西）——双向分叉**不做整file覆盖**。", "",
        "## 用户拍板（2026-10-13）", "",
        "- **不恢复表情符号**（菜单继续用金色菱形标记）。",
        "- **PPT 用中文、不署名**（不写学校/专业/学号/姓名/实验室）。",
        "- **不要动 `opencv-python` / `numpy` 的版本组合**（两台机器唯一都能用的组合；已在 requirements.txt 写明）。",
        ]
D = os.path.join(ROOT, "dev", "docs", "红测试修复清单-2026-10-13.md")
io.open(D, "w", encoding="utf-8", newline="\n").write("\n".join(doc) + "\n")
print()
print("✓ 已重写:", os.path.basename(D), "（%d 行）" % len(doc))
