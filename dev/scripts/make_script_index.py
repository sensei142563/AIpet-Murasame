# -*- coding: utf-8 -*-
"""生成 dev/scripts 索引（分类 + 用途 + 何时该跑），然后提交。

分类规则（按文件名与是否被闸门/验收引用）：
  gate        —— verify_all.py 及其直接调用的离线套件
  accept      —— accept_all.py 及其直接调用的验收辅助
  tool        —— 可复用的小工具（每次都可能用到）
  handover    —— 交接/索引类生成器
  oneoff      —— 一次性的读源码 / 探针 / 修 bug 脚本（保留便于回溯，但平时不用跑）
"""
import io
import os
import re
import subprocess
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
SD = os.path.join(MAIN, "dev", "scripts")
OUT = os.path.join(MAIN, "dev", "docs", "脚本索引-2026-10.md")


def read(p, n=4000):
    try:
        return io.open(p, encoding="utf-8", errors="replace").read()
    except Exception:
        return ""


def docstring_of(src):
    # 只认文件最开头那段：前缀只允许注释行（不跨代码），否则会把函数内部的
    # docstring 也匹配上 —— 我第一次用 ^\s*(?:#.*\n\s*)* 太松，accept_all.py
    # 的用途被写成了它里面某个内部函数的说明。
    m = re.search(r'\A(?:#[^\n]*\n)*[ \t]*"""(.*?)"""', src, re.S)
    if not m:
        m = re.search(r"^\s*(?:#.*\n\s*)*'''(.*?)'''", src, re.S)
    if not m:
        return ""
    first = [l.strip() for l in m.group(1).strip().split("\n") if l.strip()]
    return first[0] if first else ""


GATE = {"verify_all.py", "mem_adversarial.py", "qq_outbox_adversarial.py",
        "test_heavy_gate.py", "test_vad.py"}
ACCEPT = {"accept_all.py", "fix_accept_verdict.py", "fix_accept_verdict2.py",
          "fix_accept_verdict3.py", "accept_section8.py", "fix_accept_syntax.py",
          "make_accept_all.py"}
HANDOVER = {"make_handover.py", "make_script_index.py", "handover_polish.py", "handover_polish2.py"}
TOOL = {"vrm_inspect.py", "normalize_crlf.py", "check_crlf_risk.py",
        "make_accept_all.py", "heavy_gate_e2e2.py"}
# 被闸门/验收 import 或调用的其他脚本，统一列在对应分类下
GATE_EXTRA = {"silero_pc_1.py": "（Silero 真实语音校验的原始实现，判据已并入 verify_all）"}
ACCEPT_EXTRA = {"heavy_gate_e2e.py": "（重型闸门的真实接口取证，一次性）"}

rows = []
for f in sorted(os.listdir(SD)):
    if not f.endswith(".py"):
        continue
    p = os.path.join(SD, f)
    src = read(p)
    ds = docstring_of(src)
    if f in GATE:
        cat = "gate"
    elif f in HANDOVER:
        cat = "handover"
    elif f in ACCEPT:
        cat = "accept"
    elif f in TOOL:
        cat = "tool"
    elif re.match(r"^(read_|show_|probe_|find_|inspect_|verify_settings|verify_chat)", f) or \
         re.search(r"_(fix|adv|polish|probe|read|show|find)\w*\.py$", f) or \
         re.search(r"_\d+\.py$", f) or f.startswith(("fix_", "commit_", "onebot_adv", "chatcore_",
                                                     "store_fix", "ilink_fix", "safe_store",
                                                     "assetseed", "tts_chain", "vad_pc",
                                                     "silero_pc", "heavy_gate", "adversarial_",
                                                     "hand_touch", "wake_", "make_", "accept_",
                                                     "mem_fix", "qq_outbox_fix", "commit_")):
        cat = "oneoff"
    else:
        cat = "tool"
    rows.append({"f": f, "cat": cat, "ds": ds[:150], "size": os.path.getsize(p),
                 "mtime": os.path.getmtime(p), "extra": GATE_EXTRA.get(f, ACCEPT_EXTRA.get(f, ""))})

order = {"gate": 0, "accept": 1, "handover": 2, "tool": 3, "oneoff": 4}
rows.sort(key=lambda r: (order.get(r["cat"], 9), -r["mtime"]))
cnt = {}
for r in rows:
    cnt[r["cat"]] = cnt.get(r["cat"], 0) + 1

L = []
L.append("# dev/scripts 脚本索引（自动生成于 %s）" % datetime.now().strftime("%Y-%m-%d %H:%M"))
L.append("")
L.append("> 由 `dev/scripts/make_script_index.py` 生成：分类按文件名与用途规则，用途取自脚本自身 docstring。")
L.append("> 共 **%d** 个脚本：gate %d · accept %d · handover %d · tool %d · oneoff %d"
         % (len(rows), cnt.get("gate", 0), cnt.get("accept", 0), cnt.get("handover", 0),
            cnt.get("tool", 0), cnt.get("oneoff", 0)))
L.append("")
L.append("## 最常用的几条命令（记住这些就够）")
L.append("")
L.append("```")
L.append("# 1) 离线回归闸门：不需要手机，约 5 秒，失败即非 0（提交前跑它）")
L.append("python dev/scripts/verify_all.py")
L.append("")
L.append("# 2) 真机验收：手机插上线后跑，失败会自动打包诊断（截图+日志+dump+旋钮现值）")
L.append("python dev/scripts/accept_all.py")
L.append("python dev/scripts/accept_all.py --dry-run   # 无手机时自检脚本本身")
L.append("")
L.append("# 3) 交接清单 / 脚本索引（数字自动刷新，不用手改）")
L.append("python dev/scripts/make_handover.py")
L.append("python dev/scripts/make_script_index.py")
L.append("")
L.append("# 4) 记忆导出导入（与手机端同协议）")
L.append("python tool/memory_transfer.py export --pet murasame")
L.append("python tool/memory_transfer.py import 文件.json")
L.append("")
L.append("# 5) 新 VRM 模型体检（VRoid 导出后先跑它）")
L.append("python dev/scripts/vrm_inspect.py")
L.append("```")
L.append("")
L.append("## 分类说明")
L.append("")
L.append("| 分类 | 含义 | 平时要跑吗 |")
L.append("|---|---|---|")
L.append("| gate | 离线闸门及其直接调用的套件 | **要**（提交前）|")
L.append("| accept | 真机验收脚本及其辅助 | **要**（插线后）|")
L.append("| handover | 交接清单/索引生成器 | 偶尔（内容变了就重生成）|")
L.append("| tool | 可复用小工具 | 按需 |")
L.append("| oneoff | 一次性的读源码/探针/修 bug 脚本 | **不用**（保留是为了回溯「当时怎么查的」）|")
L.append("")
for cat, title in (("gate", "① 离线闸门（提交前跑）"), ("accept", "② 真机验收"),
                   ("handover", "③ 交接与索引"), ("tool", "④ 可复用工具"),
                   ("oneoff", "⑤ 一次性脚本（保留供回溯，平时不用跑）")):
    subset = [r for r in rows if r["cat"] == cat]
    if not subset:
        continue
    L.append("## %s（%d 个）" % (title, len(subset)))
    L.append("")
    L.append("| 脚本 | 用途 |")
    L.append("|---|---|")
    for r in subset:
        d = r["ds"] or r["extra"] or "（无 docstring）"
        L.append("| `%s` | %s |" % (r["f"], d.replace("|", "\\|")))
    L.append("")
L.append("---")
L.append("")
L.append("生成：`python dev/scripts/make_script_index.py`（重跑即刷新）")

io.open(OUT, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
print("✓ 已生成 %s" % OUT)
print("   脚本总数 %d：%s" % (len(rows), cnt))
print()
print("=== 回读：命令区 + 分类表 + 前 12 个 gate/accept 条目 ===")
txt = io.open(OUT, encoding="utf-8").read()
i = txt.find("## 最常用的几条命令")
j = txt.find("## ① ")
print(txt[i:j][:1500] if i > 0 else "(未找到)")
k = 0
for l in txt[j:].split("\n") if j > 0 else []:
    if l.startswith("| `"):
        print("   " + l[:150])
        k += 1
        if k >= 12:
            break
