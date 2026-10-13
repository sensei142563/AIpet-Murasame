# -*- coding: utf-8 -*-
"""① 查 agent 守卫在当前树的状态 ② 生成《红测试修复清单》文档（按缺失功能分组）"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")

print("=== ① agent 守卫在当前树的现状 ===")
mc = io.open(os.path.join(ROOT, "classes", "murasame_class.py"), encoding="utf-8",
             errors="replace").read()
for k in ("_run_agent_task", "_on_agent_done", "_agent_worker", "AgentWorker",
          "我还在做上一件事", "要让她去做吗", "agent_bridge"):
    print("   %-20s %s" % (k, "有 ✓" if k in mc else "**没有** ✗"))
print("   在 main.py 里:", "有" if "agent" in io.open(os.path.join(ROOT, "main.py"),
      encoding="utf-8", errors="replace").read().lower() else "没有")
print("   tool/agent_bridge.py 是否存在:",
      "有 ✓" if os.path.isfile(os.path.join(ROOT, "tool", "agent_bridge.py")) else "没有 ✗")

print()
print("=== ② 跑全量测试，收集所有 FAIL 明细 ===")
r = subprocess.run([VENV, os.path.join("tests", "run_all.py")], cwd=ROOT, capture_output=True,
                   text=True, encoding="utf-8", errors="replace", timeout=1800)
summary = ((r.stdout or "") + (r.stderr or ""))
fails = {}
cur_file = None
for l in summary.split("\n"):
    m = re.match(r"\s*(test_\w+\.py)\s+(\d+)\s+(\d+)\s+(\d+)", l)
    if m:
        cur_file = m.group(1)
        fails[cur_file] = {"ok": int(m.group(2)), "fail": int(m.group(3)), "items": []}
        continue
for l in summary.split("\n"):
    m = re.search(r"FAILED \d+ 项：(.*)$", l)
    if m and cur_file:
        fails[cur_file]["items"] = [x.strip() for x in m.group(1).split("、")]

print("   文件 / 通过 / 失败 / 失败项")
for f, d in fails.items():
    print("   %-26s %3d OK  %2d FAIL" % (f, d["ok"], d["fail"]))
    for it in d["items"][:14]:
        print("        · " + it[:110])

doc = ["# 红测试修复清单（2026-10-13 生成）",
       "",
       "> 来源：`runtime\\venv\\Scripts\\python.exe tests\\run_all.py`（项目自带总跑器）。",
       "> 用途：这些**红项就是「协作者基线里缺的东西」的可执行清单** —— 每一项都对应一个具体缺失功能或失配。",
       "> 规矩：**先看断言要什么，再决定是补代码还是修测试**；不许为了变绿而放松断言。",
       ""]
total_fail = sum(d["fail"] for d in fails.values())
doc.append("## 总览：%d 个文件 / %d 项失败" % (len([f for f in fails if fails[f]['fail'] > 0]), total_fail))
doc.append("")
doc.append("| 文件 | 通过 | 失败 | 主要缺什么 |")
doc.append("|---|---|---|---|")
GUESS = {
    "test_bounds.py": "字体缩放下界（0.05 vs 断言 [0.1,3.0]）",
    "test_bugfix_0930.py": "**状态窗 / 状态页整套**（status_page_enabled、QSS、卡片样式、侧栏「状态」项）",
    "test_bugfix_0930b.py": "main.py 对 off/voice/chat 三种输入方式的处理",
    "test_config_contracts.py": "**全仓重复字典键**（tool/jp_names.py 等）",
    "test_frontend_style.py": "启动器前端配色/顺序一致性",
    "test_qt_lifecycle.py": "**agent 任务守卫 + 确认框**（本轮已定位）",
    "test_vision_interface.py": "视觉服务接口（vision_source 等键）",
}
for f, d in fails.items():
    if d["fail"]:
        doc.append("| `%s` | %d | **%d** | %s |" % (f, d["ok"], d["fail"],
                                                     GUESS.get(f, "")))
doc.append("")
for f, d in fails.items():
    if not d["fail"]:
        continue
    doc.append("## %s（%d 项）" % (f, d["fail"]))
    doc.append("")
    for it in d["items"]:
        doc.append("- [ ] %s" % it)
    doc.append("")

doc += ["## 已修（本轮）", "",
        "- ✅ `test_plugin_markup.py` 全绿：恢复 `tool/plugins.py` 超集版（补齐 `handle_reply` 等 14 个函数）。",
        "- ✅ `test_bugfix_0930.py` 菜单那 4 项转绿：菜单弹出方式改成了动画 `popup()`，而测试只打桩 `exec_`；",
        "  已把桩同步（**断言一条未改**），并补回菜单里丢失的「输入对话（打字）」「切换形象（当前：…）」。",
        "",
        "## 已定位但未修（下一轮）", "",
        "1. `test_qt_lifecycle.py`：源码里**没有** `_run_agent_task` / `_on_agent_done` / `_agent_worker`，",
        "   而备份版是完整的（含「同时只跑一个」守卫与默认「否」的确认框）。",
        "   ⇒ 需要把这段恢复，并确认 `tool/agent_bridge.py` 与 `classes/Worker_class.py::AgentWorker` 都在。",
        "2. `test_bugfix_0930.py` 剩 7 项 + `test_bugfix_0930b.py` 2 项：**状态窗/状态页**整套。",
        "3. `test_config_contracts.py` 3 项：重复字典键，机械修复、风险低。",
        "4. `test_vision_interface.py` 9 项、`test_frontend_style.py` 13 项：接口键与配色一致性。",
        "",
        "## 注意", "",
        "- 用户 2026-10-13 拍板：**不恢复表情符号**、**PPT 中文不署名**、",
        "  **不要动 opencv-python/numpy 的版本组合**（那是两台机器唯一都能用的组合，已在 requirements.txt 写明）。",
        ]

D = os.path.join(ROOT, "dev", "docs", "红测试修复清单-2026-10-13.md")
io.open(D, "w", encoding="utf-8", newline="\n").write("\n".join(doc) + "\n")
print()
print("=== 已写出 %s（%d 行）===" % (os.path.basename(D), len(doc)))
