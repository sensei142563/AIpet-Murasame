# -*- coding: utf-8 -*-
"""记录用户 2026-10-13 对 Ollama 的澄清，并据此结清"两套本地视觉机制"的遗留问题。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

# ---------- ① 待确认文档：结清 ----------
D = os.path.join(ROOT, "dev", "docs", "本地视觉疑似有两套机制-待确认-2026-10-13.md")
add = """

---

## 八、✅ 作者澄清（2026-10-13，用户原话）

> "Ollama 似乎是前作留下的，**也可以用的**，但是咱们**没用过**，
>  就一直留在那里做一个**备选**。"

据此把前面几个问题彻底结清：

| 之前的疑问 | 现在的答案 |
|---|---|
| 机制 B（Ollama `qwen2.5vl`）还活着吗？ | **代码上活着、但确实没被用过**：函数在（`chat.py:275`）、只被 import（`murasame_class.py:72`）、**没有调用点**；也不是"忘了删"，而是**有意留作备选** |
| "本地视觉不使用、仅保留接口"覆盖哪一条？ | 覆盖**机制 A**（`tool/vision_local.py` + 上游那套 UI）。机制 B 属于"前作遗留 + 备选"，本来就不在这条决策里 |
| README 那句 `ollama pull qwen2.5vl:7b` 要改吗？ | **不改**（它描述的是这条备选路径）。本轮只在旁边补一句"这是备选、当前未使用"，避免读者误以为必须装 |

⇒ 结论：**两条线是"现役（A，默认云端、本地可选）"与"备选（B，前作遗留、未使用）"**，
而不是"两套并行机制"。之前文档里"疑似两套"的措辞，按此更正为"现役 + 备选"。

## 九、连带的一条纪律（写给以后）
"**代码里存在**"≠"**在用**"，也≠"**该删**"。
这次我一开始按"死代码"处理（建议清理 `ollama_qwen25vl` 的未使用导入），
作者澄清后才知道它是**有意保留的备选** —— 所以：
**删任何"看起来没人用"的东西之前，一律先问作者**（本轮我没有动它，是对的）。
"""
t = io.open(D, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
if "作者澄清（2026-10-13" not in t:
    io.open(D, "w", encoding="utf-8", newline="\n").write(t.rstrip() + add)
    print("✓ ① 已在待确认文档里结清（现役 A + 备选 B）")

# ---------- ② README 那句补"备选" ----------
R = os.path.join(ROOT, "README.md")
r = io.open(R, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
OLD = ("#       `ollama pull qwen2.5vl:7b` 对应的是历史遗留函数 ollama_qwen25vl，\n"
       "#       该函数目前**没有任何调用点**（只被 import，不被调用），拉了也不会生效。")
NEW = ("#       `ollama pull qwen2.5vl:7b` 对应的是**前作遗留的备选路径**（函数 ollama_qwen25vl）。\n"
       "#       该路径当前**没有任何调用点**（只被 import，不被调用），属于\"留着备用\"，\n"
       "#       现在拉这个模型不会生效。（作者 2026-10-13 确认：可以用，但我们没用过。）")
if OLD in r:
    r = r.replace(OLD, NEW, 1)
    io.open(R, "w", encoding="utf-8", newline="\n").write(r)
    print("✓ ② README 那句已补成「前作遗留的备选」")
else:
    print("· ② README 锚点未命中（可能已改过）")

MSG = """docs: 作者澄清 Ollama 是"前作遗留的备选" —— 结清"两套机制"的遗留问题

用户 2026-10-13 原话："Ollama 似乎是前作留下的，**也可以用的**，但是咱们**没用过**，
就一直留在那里做一个**备选**。"

## 据此结清
| 之前的疑问 | 答案 |
|---|---|
| 机制 B（Ollama qwen2.5vl）还活着吗？ | 代码上活着、**确实没被用过**：函数在（chat.py:275）、只被 import
（murasame_class.py:72）、没有调用点；**不是忘了删，是有意留作备选** |
| "本地视觉不使用、仅保留接口"覆盖哪条？ | 覆盖**机制 A**（tool/vision_local.py + 上游 UI）；机制 B 属"前作遗留 + 备选"，
本就不在该决策范围内 |
| README 那句 `ollama pull qwen2.5vl:7b` 要改吗？ | **不改**（它讲的就是这条备选）；只在旁边补一句
"前作遗留的备选、当前没有调用点、现在拉也不生效" |

⇒ 措辞更正：不是"两套并行机制"，而是**现役（A：默认云端，本地可选）+ 备选（B：前作遗留，未使用）**。

## 连带的一条纪律
"**代码里存在**" ≠ "**在用**" ≠ "**该删**"。
我一开始按"死代码"处理（建议清理 ollama_qwen25vl 的未使用导入），作者澄清后才知道是有意保留的备选。
⇒ **删任何"看起来没人用"的东西之前，一律先问作者**。本轮我没动它 —— 现在看是对的。
"""
p = os.path.join(MAP, "_msg_ollama_clarify.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:170])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
