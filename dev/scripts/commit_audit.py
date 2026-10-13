# -*- coding: utf-8 -*-
"""把"真丢失 vs 设计分叉"的审计结论写进红测试清单，然后提交。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")
MAP = os.path.join(ROOT, "dev", "merge-map")
D = os.path.join(ROOT, "dev", "docs", "红测试修复清单-2026-10-13.md")

# 重新采集当前状态
r = subprocess.run([VENV, os.path.join("tests", "run_all.py")], cwd=ROOT, capture_output=True,
                   text=True, encoding="utf-8", errors="replace", timeout=1800)
out = (r.stdout or "") + (r.stderr or "")
rows = []
for l in out.split("\n"):
    m = re.match(r"\s*(test_\w+\.py)\s+(-?\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)s(.*)$", l)
    if m:
        rows.append((m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))))
total_ok = sum(x[2] for x in rows)
total_fail = sum(x[3] for x in rows)

ADD = """

---

## 审计结论（2026-10-13 19:1x 更新）：哪些是**真丢失**、哪些是**设计分叉**

> 判断依据：与覆盖前备份 `remotes/origin/backup/main-before-overwrite-20261001` 逐项比对，
> 并看代码里的注释是否**主动**偏离上游。

### A. 真丢失（已修好，且都有测试为证）
| 项 | 证据 | 结果 |
|---|---|---|
| `tool/plugins.py` 超集版 | 缺 14 个函数（含 `handle_reply`），而备份与 origin/main 函数集合完全相同；`test_plugin_markup.py:101` 直接调它 | ✅ `test_plugin_markup.py` 全绿 |
| `pets/natsume/pet.json` 的 `decor_rules` | `tool/portrait_outfit.py` 全程在读；本树任何 pet.json 都没有 | ✅ 已补（a=[]、b=[{嫌弃阴影}]） |
| 右键菜单两个主操作 | 备份第一层有「输入对话（打字）」「换回 2D / 换成 Live2D」；`test_bugfix_0930.py` 的断言正是"要有 Live2D/2D 项" | ✅ 菜单 4 项转绿 |
| 「agent 任务」整条链 | 本树缺 `AgentWorker` 类 + `_run_agent_task`/`_on_agent_done` + `/agent` 分发 | ✅ 不再崩，+24 项 |
| `tool/jp_names.py` 重复字典键 | 前者被 Python 静默丢弃 | ✅ `test_config_contracts.py` 全绿 |
| `qq/qq_config.py` 窄真值比较 / 顶层配置读取式下标 | 缺键直接 KeyError | ✅ 同上 |
| 字号下界不一致（registry 0.05 vs 代码 0.10）+ 两处裸读未夹 | 敌意值 0.05 未被夹住 | ✅ `test_bounds.py` 全绿 |

### B. **设计分叉**（不是丢失，需要人拍板；我不擅自改）
| 项 | 情况 | 为什么不能自作主张 |
|---|---|---|
| 「状态窗 / 状态页」整套（`test_bugfix_0930.py` 7 项 + `0930b` 2 项） | 本树 `classes/status_window.py` 是 **554~612 行的新版实现**（与 origin/main 相同）；备份是 **234~271 行旧版**，旧版里有 `QDialog#statusWindow` 的 QSS 不透明底与卡片 `WA_StyledBackground`；`config.example.json` 的 `status_page_enabled` 本树也没有 | 测试是**按旧版做法**写的；新版可能有它自己的视觉方案 —— 到底是"把旧版样式移植进新版"还是"改测试判据"，是产品决定 |
| 本地视觉服务（`test_vision_interface.py` 9 项） | `tool/vision_local.py` **本树与备份、origin/main 都是 198 行**（模块在 ✓）；但 `pcl_launcher/widgets.py:357` 与 `classes/murasame_class.py:1371` 的注释写明**主动偏离上游**："上游的『本地视觉只留接口』"、"上游 vision_local.py 是另一套语义（vision_source 默认 cloud、要用户自接模型）"，那行 import 还被注释掉了 | 测试按**上游语义**写（要 `vision_source`/`vision_local_url`/`vision_local_command` + 设置页三项）；本树是**主动选择不走那套** |
| `pcl_launcher/colors.py` | 双向分叉：本树 700 行 / 备份 605 行，双方各有新东西（备份有 `secondary_text`/`_ACTIVE_THEME_ID`/8 级灰阶派生；本树有 `_mix_color`/`_theme_text_color`） | 整file覆盖会丢本树的新东西；缺的 `secondary_text` 当前**无调用点**，暂不报错 |

### C. 待处理（未分类）
- `test_frontend_style.py` 13 项（启动器配色/顺序一致性，含 `vision_source 与 tts_type 同方向` 这类与 B 组同源）
- `test_qt_lifecycle.py` 7 项（agent 下游行为 + `run.py/main.py` 的 `_spawn_console + _watch_child`）
"""

t = io.open(D, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
if "审计结论（2026-10-13 19:1x 更新）" not in t:
    t = t.rstrip() + ADD
    io.open(D, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ 已把审计结论追加进红测试清单")
else:
    print("· 已有审计结论")

MSG = """docs: 红测试清单补「真丢失 vs 设计分叉」的审计结论（当前 254 通过 / 5 个文件红）

本轮把前三轮"换基线丢了什么"的排查结论固化成表，避免以后重复考古：

A. **真丢失（已修好，都有测试为证）**
   tool/plugins.py 超集版（+handle_reply 等 14 个函数）→ test_plugin_markup 全绿
   pets/natsume/pet.json 的 decor_rules → 装扮随情绪联动恢复
   右键菜单两个主操作（输入对话 / 切换形象）→ test_bugfix_0930 菜单 4 项转绿
   「agent 任务」整条链（AgentWorker 类 + 两个方法 + /agent 分发）→ test_qt_lifecycle 不再崩（+24 项）
   tool/jp_names.py 重复字典键、qq_config 窄真值比较、顶层配置读取式下标 → test_config_contracts 全绿
   字号下界不一致（registry 0.05 vs 代码 0.10）+ 两处裸读未夹 → test_bounds 全绿

B. **设计分叉（不是丢失，等用户拍板；不擅自改）**
   「状态窗/状态页」：本树是 554~612 行**新版实现**（同 origin/main），备份是 234~271 行**旧版**，
     旧版才有 QDialog#statusWindow 的 QSS 不透明底与卡片 WA_StyledBackground；测试按旧版写。
   本地视觉服务：tool/vision_local.py 三方都是 198 行（模块在），但代码注释写明**主动偏离上游**
     （"上游的『本地视觉只留接口』"、"上游 vision_local.py 是另一套语义"），import 被注释掉；
     测试按上游语义写（要 vision_source / vision_local_url / vision_local_command + 设置页三项）。
   pcl_launcher/colors.py：双向分叉（本树 700 行 / 备份 605 行，各有新东西）；
     缺的 secondary_text 当前**无调用点**，暂不报错。

C. 待分类：test_frontend_style 13 项、test_qt_lifecycle 余 7 项（含 run.py/main.py 的
   `_spawn_console + _watch_child`）。

当前全量：**254 项通过 / 5 个文件红**（会话开始时 225 通过 / 7 个文件红）。
"""
p = os.path.join(MAP, "_msg_audit.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:160])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
