# -*- coding: utf-8 -*-
"""把上一条"待确认"的三个问题结清，并按证据精准修正 README 那句 Ollama 提示。
   证据：
     tool/chat.py:758-784  describe_image() = 唯一统一入口：
                             vision_source()=="local" → _local_vision_describe（tool/vision_service.py）
                             否则                    → cloud_vl
     全仓检索 ollama_qwen25vl：只有定义(chat.py:275)、它自己内部日志分支(chat.py:32/284)、
                             以及 classes/murasame_class.py:72 的 **import** —— **没有任何调用点**
     config.json：model_type='qwen'、无 vision_source、无 ollama 键 ⇒ 实际走云端
"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")
R = os.path.join(ROOT, "README.md")

# ---------- ① README:1477 改成有据可依的说明 ----------
t = io.open(R, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
OLD = "ollama pull qwen2.5vl:7b  # 如需本地屏幕识别"
NEW = ("# 注意：本地「屏幕识别」**不是**走 Ollama —— 它走 tool/vision_service.py（Qwen2-VL-2B）；\n"
       "#       `ollama pull qwen2.5vl:7b` 对应的是历史遗留函数 ollama_qwen25vl，\n"
       "#       该函数目前**没有任何调用点**（只被 import，不被调用），拉了也不会生效。")
if OLD in t:
    t = t.replace(OLD, NEW, 1)
    io.open(R, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ ① README 那句 Ollama 提示已改为有证据的说明")
else:
    print("✗ ① 锚点未命中")

# ---------- ② 更新待确认文档：三个问题结清 ----------
D = os.path.join(ROOT, "dev", "docs", "本地视觉疑似有两套机制-待确认-2026-10-13.md")
add = """

---

## 五、✅ 三个待确认问题已结清（同日补充，全部有代码证据）

**问 1：两条机制各在什么条件下被走到？**
```
tool/chat.py:758-784  describe_image() 是**唯一**统一视觉入口：
    if vision_source() == "local":  → _local_vision_describe(...)   ← 机制 A（tool/vision_service.py）
    （本地失败还会 _ensure_local_vision() 自启后重试一次）
    else:                            → cloud_vl(...)                 ← 云端
⇒ describe_image **从不**调用 ollama_qwen25vl。
```

**问 2：机制 B（Ollama qwen2.5vl）到底还有没有用？**
```
全仓检索 `ollama_qwen25vl`：
    chat.py:275                        定义
    chat.py:284                        它自己内部调 ollama_post（自洽）
    chat.py:32                         `if name == "ollama-qwen2.5vl"` 日志分支
    classes/murasame_class.py:72       **import 了**
    …此后**没有任何调用点**
⇒ 结论：**机制 B 是死代码**（函数在、被 import、但没人调）。
   `ollama pull qwen2.5vl:7b` 对当前实现**不产生任何作用**。
```

**问 3：你的配置实际走哪条？**
```
config.json：model_type='qwen'、vision_model_name='qwen-vl-plus'、
             无 vision_source 键、无 ollama 键
⇒ vision_source() 缺省 cloud ⇒ **实际走云端**（与"本地视觉不使用、仅保留接口"一致）
```

## 六、据此做的文档修正（这次是有证据的，不是想当然）
README 原 1477 行 `ollama pull qwen2.5vl:7b  # 如需本地屏幕识别` 已改为：
```
# 注意：本地「屏幕识别」**不是**走 Ollama —— 它走 tool/vision_service.py（Qwen2-VL-2B）；
#       `ollama pull qwen2.5vl:7b` 对应的是历史遗留函数 ollama_qwen25vl，
#       该函数目前**没有任何调用点**（只被 import，不被调用），拉了也不会生效。
```

## 七、顺带发现（留档，未处理）
`classes/murasame_class.py:72` 从 `tool.chat` 导入的 `ollama_qwen25vl` 是**未使用的导入**。
无害，但它会让读代码的人以为"这条路径还活着" —— 与 README 那句旧提示是同一个误会来源。
建议后续清理（连同 `chat.py:275-290` 那段一并处理），**但那是删代码，不在本轮做**。
"""
t2 = io.open(D, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
if "三个待确认问题已结清" not in t2:
    io.open(D, "w", encoding="utf-8", newline="\n").write(t2.rstrip() + add)
    print("✓ ② 已在待确认文档里结清三个问题 + 记录死代码结论")

MSG = """docs(vision): 结清"两套本地视觉机制" —— 机制 B 是死代码；据此精准修正 README 那句 Ollama 提示

上一条我把三个问题列为"待确认"。这次全部查清（都有代码证据），并据此改文档。

## 结论一：统一入口只有一个，且不碰 Ollama
`tool/chat.py:758-784 describe_image()`：
    if vision_source() == "local": → _local_vision_describe（tool/vision_service.py，Qwen2-VL-2B）
                                     本地失败还会 _ensure_local_vision() 自启后重试一次
    else:                          → cloud_vl
⇒ describe_image **从不调用** ollama_qwen25vl。

## 结论二：机制 B（Ollama qwen2.5vl）是**死代码**
全仓检索 `ollama_qwen25vl` 只有：定义（chat.py:275）、它自洽的内部调用（chat.py:284）、
日志分支（chat.py:32）、以及 `classes/murasame_class.py:72` 的 **import** —— **没有任何调用点**。
⇒ `ollama pull qwen2.5vl:7b` 对当前实现**没有任何作用**。

## 结论三：你的配置实际走云端
config.json：model_type='qwen'、vision_model_name='qwen-vl-plus'、
             无 vision_source、无 ollama 键 ⇒ vision_source() 缺省 cloud。

## 据此修正 README（与上次"差点改错"相对照）
原 1477 行 `ollama pull qwen2.5vl:7b  # 如需本地屏幕识别` 改为：
```
# 注意：本地「屏幕识别」**不是**走 Ollama —— 它走 tool/vision_service.py（Qwen2-VL-2B）；
#       `ollama pull qwen2.5vl:7b` 对应的是历史遗留函数 ollama_qwen25vl，
#       该函数目前**没有任何调用点**（只被 import，不被调用），拉了也不会生效。
```
⚠ 与上一次的区别：上次我准备按"想当然"把整句删掉（那会丢掉"确实存在这么一个函数"的事实）；
这次是**先查清调用点**再写，所以能说准"函数在、但没人调"。

## 顺带留档（未处理）
`classes/murasame_class.py:72` 的 `ollama_qwen25vl` 是**未使用的导入**，建议后续连同
`chat.py:275-290` 一起清理 —— 但那是删代码，不在本轮范围。
"""
p = os.path.join(MAP, "_msg_resolve_vision.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:170])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
