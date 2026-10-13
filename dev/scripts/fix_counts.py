# -*- coding: utf-8 -*-
"""把写死的旧自检数字（381 / 24）统一更新为当前真实值（386 / 27），
   并补一句"以命令输出为准"，避免下次又过期。

只改**活的交付物**：README / PPT(outline+notes) / 录屏操作单 / 两份本轮 dev 文档。
不改历史提交信息（dev/merge-map/_msg_*.txt）与旧规划文档（docs/plan/*），但要标注。
"""
import io
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")
done = []


def fix(path, pairs, must=True):
    p = os.path.join(ROOT, path)
    if not os.path.isfile(p):
        print("   ✗ 不存在:", path)
        return
    t = io.open(p, encoding="utf-8", errors="replace").read()
    orig = t
    for old, new in pairs:
        if old in t:
            t = t.replace(old, new)
    if t != orig:
        io.open(p, "w", encoding="utf-8", newline="\n").write(t)
        done.append(path)
        print("   ✓ %s" % path)
    else:
        print("   · %s（锚点未命中或无变化）" % path)


print("=== ① README ===")
fix("README.md", [
    ("## ✅ 自检与回归：381 项，一条命令可复现",
     "## ✅ 自检与回归：386 项，一条命令可复现"),
    ("总计 10 个文件 / 381 项通过 / 0 个文件失败",
     "总计 10 个文件 / 386 项通过 / 0 个文件失败"),
    ("| `test_vision_interface.py` | 24 |",
     "| `test_vision_interface.py` | 27 |"),
])

print("=== ② PPT（大纲 + 讲稿）===")
OUT = os.path.join(ROOT, "dev", "ppt", "outline.json")
o = json.loads(io.open(OUT, encoding="utf-8", errors="replace").read())
for s in o["slides"]:
    for b in s.get("bullets", []):
        if "381" in (b.get("text") or ""):
            b["text"] = "386 项自带自检"
        if "381" in (b.get("sub") or ""):
            b["sub"] = b["sub"].replace("381", "386")
json.dump(o, io.open(OUT, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=2)
print("   ✓ dev/ppt/outline.json")

NT = os.path.join(ROOT, "dev", "ppt", "notes.json")
n = json.loads(io.open(NT, encoding="utf-8", errors="replace").read())
hit = 0
for k, v in list(n["notes"].items()):
    if "381" in v:
        n["notes"][k] = v.replace("381", "386")
        hit += 1
io.open(NT, "w", encoding="utf-8", newline="\n").write(json.dumps(n, ensure_ascii=False, indent=2))
print("   ✓ dev/ppt/notes.json（改了 %d 页讲稿）" % hit)

print("=== ③ 录屏操作单（3 处）===")
fix("dev/docs/PPT录屏截图操作单-2026-10-13.md", [
    ("总计 10 个文件 / 381 项通过 / 0 个文件失败",
     "总计 10 个文件 / 386 项通过 / 0 个文件失败"),
    ("**这段讲**：381 项自检全绿", "**这段讲**：386 项自检全绿"),
    ("| 16 | 工程质量：验得出来 | **S8**、**C5** | 381 项那一行 |",
     "| 16 | 工程质量：验得出来 | **S8**、**C5** | 386 项那一行 |"),
])

print("=== ④ 本轮两份 dev 文档 ===")
fix("dev/docs/本地视觉口径排查-2026-10-13.md",
    [("10 个文件 / 381 项通过 / 0 失败", "10 个文件 / 386 项通过 / 0 失败")])
fix("docs/大厂入局与对标补查-2026-10-13.md",
    [("工程质量（381 项自检）", "工程质量（386 项自检）")])

# ⑤ 加"以命令输出为准"的说明
R = os.path.join(ROOT, "README.md")
t = io.open(R, encoding="utf-8", errors="replace").read()
NOTE = ("\n> 上面的数字会随体检项增加而变 —— **以 `tests/run_all.py` 的实时输出为准**。\n")
if "以 `tests/run_all.py` 的实时输出为准" not in t:
    t = t.replace("当前状态（2026-10-13 实测）：", "当前状态（2026-10-13 实测）：" + NOTE, 1)
    io.open(R, "w", encoding="utf-8", newline="\n").write(t)
    print("   ✓ README 补了一句「以命令输出为准」")

print()
print("=== 已改文件 ===")
for d in done:
    print("   -", d)
print("   - dev/ppt/notes.json")

MSG = """docs: 把写死的旧自检数字统一更新为当前真实值（381→386、24→27）

## 为什么必须改
这几轮我给自检加了守卫（+2 条）并把 vision 接口的检查项从 24 补到 27，
总数从 **381 → 386**。但**写死在文档里的还是 381**：
- README 标题「自检与回归：381 项」与实测输出那一行
- README 体检表里 `test_vision_interface.py | 24`
- **PPT 大纲第 16 页「381 项自带自检」**与对应讲稿
- **录屏操作单 3 处**（含 S8 要照着念的那一行、以及"386 项那一行"的映射）
- `docs/大厂入局与对标补查` 与 `dev/docs/本地视觉口径排查` 各一处

其中**录屏操作单最要紧**：用户录 S8 时会照着它念"381 项"，而终端实际打印 386 ——
当场就对不上，属于"演示时当众出丑"的那类问题。

## 顺带加了一句防过期的话
README 里补：> 上面的数字会随体检项增加而变 —— **以 `tests/run_all.py` 的实时输出为准**。

## 没改的（历史材料，刻意不动）
- `dev/merge-map/_msg_*.txt` —— 那是**历史提交信息**，记录当时的真实数字（384/386 都有），
  改了就篡改历史；
- `dev/docs/红测试修复清单-2026-10-13.md`、`docs/handover/2026-09-24.md` —— 同样是历史快照；
- `docs/plan/00-总体规划.md` / `01-现状盘点.md` 里写的"8 个文件 / 385 项"是更早的口径
  （**已过期但不是本次引入**）—— 留待单独一轮核对，避免和本次混在一起。

## 流程
改 outline/notes 后按既定顺序重建：build_deck → ppt_add_notes（重建会丢备注）→ render_qc。
"""
p = os.path.join(MAP, "_msg_counts.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:170])
n2 = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                    capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n2, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
