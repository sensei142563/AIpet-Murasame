# -*- coding: utf-8 -*-
"""把这轮"差点改错文档"的过程与发现记下来 —— 只记录证据与未决问题，不改 README。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

D = os.path.join(ROOT, "dev", "docs", "本地视觉疑似有两套机制-待确认-2026-10-13.md")
io.open(D, "w", encoding="utf-8", newline="\n").write("""# 「本地视觉」疑似有**两套不同机制** —— 待确认（2026-10-13）

> 起因：上一条我说要核 README 的「本地模型（可选）」一节。按**标题**找到它在第 1471 行，
> 内容是**本地对话模型（Ollama）**，其中 1477 行写着：
> `ollama pull qwen2.5vl:7b  # 如需本地屏幕识别`。
> 我本来准备把这句话改掉（因为 README 1219 行说本地视觉走的是
> `tool/vision_service.py` + Qwen2-VL-2B）。**先查了代码，结果发现差点改错。**

## 一、查到的事实（两套写法都存在）

**机制 A —— `tool/vision_service.py`（README 主口径）**
```
README:1219  "本地视觉模型（可选，默认不使用）：截图交给本机的 tool/vision_service.py 跑
              （Qwen2-VL-2B，用 GPT-SoVITS 的 ROCm 运行时 + 显卡）"
config.example.json:10-11  vision_local_model_dir / vision_local_port
tool/vision_local.py       取值集合 (cloud, local)，缺省 cloud
```

**机制 B —— Ollama 的 `qwen2.5vl:7b`（README:1477 指的就是它）**
```
chat.py:275   def ollama_qwen25vl(image_path: str):
chat.py:280       prompt = {"model": "qwen2.5vl:7b", ...}
chat.py:284       reply = ollama_post("ollama-qwen2.5vl", prompt)
chat.py:32        if name == "ollama-qwen2.5vl": ...
config.json:3     "ollama": "http://localhost:28565/ollama"     ← 你的配置里指向 28565
```

⇒ README:1477 那句**不是笔误**，它对应的是机制 B。**所以我没有改它**（本来打算改，查明后撤回）。

## 二、因此仍**未确认**的问题（不猜）

1. **两条机制各在什么条件下被走到？** 即 `describe_image()`（tool/chat.py:765 附近）
   里面 `if vision_source() == "local"` 走到的是 A 还是 B，还是两者都有分支？
2. **"本地视觉：不使用，仅保留接口"这条决策，覆盖的是哪一条？**
   从字面看它针对的是 A（`tool/vision_local.py` 那套 + 上游的 UI 面）；
   机制 B 是 `model_type="local"`（本地对话）体系里的东西，可能根本不在该决策范围内。
3. 你的 `config.json` 里 `model_type` 是什么？若**不是** `local`，机制 B 实际上不会被用到，
   README:1477 对当前配置就是"用不到但不算错"的说明。

## 三、这轮的处理与教训

- **不改 README**（拿不准的不写）；
- 把上面三条列成待确认项，等有空/有你在时一起看；
- 教训：这次如果按"我记忆里的行号 + 想当然的口径"去改，就会把一句本来正确的说明改坏。
  **先查代码再改文案**——今天已经是第二次靠这一步避免了错误改动
  （上一次是"设置页不提供该选项"那句）。

## 四、顺带修正我自己的一个说法
上一轮我说"README 1415 行起「本地模型（可选）」那一节可能还有同类措辞" —— 行号不准确，
真实位置是 **1471 行**，而且它的主题是**本地对话模型**，不是本地视觉。
以后定位文档一律**按标题搜**，不按行号。
""")
print("✓ 已写 dev/docs/本地视觉疑似有两套机制-待确认-2026-10-13.md")

MSG = """docs: 记录「本地视觉疑似有两套机制」—— 我差点改错一句本来正确的 README

## 经过
按标题去核 README 的「本地模型（可选）」（真实在 1471 行，我上次记的行号不准），
它 1477 行写着 `ollama pull qwen2.5vl:7b  # 如需本地屏幕识别`。
我本准备改掉它（依据是 README:1219 说本地视觉走 `tool/vision_service.py` + Qwen2-VL-2B）。

**先查代码，结果发现差点改错**：`chat.py:275-284` 确实有一条 Ollama 视觉路径 ——
`ollama_qwen25vl(image_path)` → `{"model": "qwen2.5vl:7b"}` → `ollama_post("ollama-qwen2.5vl", …)`。
⇒ README:1477 不是笔误，它对应的是**另一套机制**。**所以我没有改它。**

## 由此列出三条待确认（写进文档，不猜）
1. 两条机制各在什么条件下被走到？`describe_image()` 里 `if vision_source() == "local"`
   走的是 A（vision_service.py）还是 B（Ollama），还是都有分支？
2. "本地视觉：不使用，仅保留接口"这条决策覆盖的是哪一条？（字面看针对 A）
3. 用户 config.json 的 `model_type` 是否为 local？若不是，机制 B 实际不会被用到，
   README:1477 对当前配置属于"用不到但不算错"。

## 教训（今天第二次靠"先查再改"避免错误改动）
上一次是"设置页不提供该选项"那句（查了发现设置页确实提供）。
两次都是**凭印象写文案**要坏事的场景。
另：以后定位文档按**标题**搜，不按行号（这次行号就差了 50 多行）。
"""
p = os.path.join(MAP, "_msg_two_vision.txt")
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
