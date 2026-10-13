# -*- coding: utf-8 -*-
"""审 deck 第 14 页得出的结论 + 精准修正：
   ✔「按真实相处证据（天数×对话量）抬高下限」—— 与 tool/state.py:188 的 affinity_floor()
     完全对得上（"读的时候不低于 affinity_floor()，并把抬上去的值落盘"）⇒ 准确，保留。
   ✘「不靠嘴甜」—— 桌面端成立，但 **QQ 侧另有一套好感玩法**：
     qq_chat.py 的 prompt 明写"夸奖、关心、有趣、体贴、哄你开心 → [好感+N]，N 取 2~8（越讨你喜欢越高）"，
     并由 qq_chat.py:747/784 解析 [好感±N] 落到 0~100 的 QQ 好感；qq_galgame.py 再用它算约会成功率。
   ⇒ 把断言收窄到"桌面端"，并如实说明 QQ 侧那一套；讲稿同步。
"""
import io
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")
OUT = os.path.join(ROOT, "dev", "ppt", "outline.json")
NOTES = os.path.join(ROOT, "dev", "ppt", "notes.json")

o = json.loads(io.open(OUT, encoding="utf-8", errors="replace").read())
slides = o["slides"]
for s in slides:
    if s.get("title", "").startswith("怎么做到的（二）"):
        for b in s["bullets"]:
            if b.get("text") == "关系会变":
                b["sub"] = ("桌面端：按真实相处证据（天数×对话量）抬高下限（affinity_floor）；"
                            "QQ 侧另有一套面向群聊的好感玩法，按对话内容结算")
        print("✓ 已修正第 14 页「关系会变」一条")
        break
json.dump(o, io.open(OUT, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=2)

n = json.loads(io.open(NOTES, encoding="utf-8", errors="replace").read())
for i, s in enumerate(slides, 1):
    if s.get("title", "").startswith("怎么做到的（二）"):
        n["notes"][str(i)] = (
            "记忆是分层的：对话记忆、长期记忆、日记、状态快照各管一段。"
            "关系值分两套，要说清楚：桌面端按**真实相处证据**（相处天数×对话量）抬高一个下限，"
            "不是聊几句好话就涨；QQ 侧另有一套面向群聊的好感玩法，按对话内容结算，"
            "还有约会这类玩法。她会自己补课、自己归纳关于我的事。")
        print("✓ 讲稿已同步")
        break
io.open(NOTES, "w", encoding="utf-8", newline="\n").write(
    json.dumps(n, ensure_ascii=False, indent=2))

# 记录审出来的东西
D = os.path.join(ROOT, "dev", "docs", "审PPT断言-关系值-2026-10-13.md")
io.open(D, "w", encoding="utf-8", newline="\n").write("""# 审 deck 断言：「关系值按真实相处证据抬升，不靠嘴甜」

> 方法：把 deck 里**具体到能被要求在代码里指出来**的句子挑出来，逐句回代码核。
> 这一句在第 14 页，原文是：
> 「按真实相处证据（**天数×对话量**）抬高**下限**，不靠嘴甜」。

## 一、成立的部分（精确对得上）

```
tool/state.py:13    state.feel(+8, "主人摸了头")     # 记一次情绪/关系变化
tool/state.py:122   print(f"[状态] {reason}（心情 {mood_delta:+.0f}，好感 {affinity_delta:+.1f} → …")
tool/state.py:188   当前关系值 —— 读的时候不低于 affinity_floor()，并把抬上去的值落盘，…
```
⇒「按真实相处证据抬高**下限**」与 `affinity_floor()` 的实现**完全对得上**（连"下限"这个词都一致）。
   桌面端的"摸头"这类**真实互动**确实会推动心情与好感（`state.feel`）。
   **这半句保留。**

## 二、不成立的部分（越界了）

QQ 侧是**另一套**、而且**明确会因"嘴甜"加分**：

```
qq/qq_chat.py:496   "· 夸奖、关心、有趣、体贴、**哄你开心** → [好感+N]，N 取 2~8（**越讨你喜欢越高**）"
qq/qq_chat.py:747/784/790  解析模型给出的 [好感±N] 并落到 0~100 的 QQ 好感，然后把标记从正文移除
qq/qq_chat.py:793/798      加完还把"（好感度 +N，当前 M）"追加到回复末尾（**不进记忆**）
qq/qq_galgame.py:7/9/27    每轮由模型给 [好感±N]，本模块 clamp + 持久化；
                           约会成功 +15~25 / 失败 -15~25（每人每群 60 分钟冷却）；
                           成功率 = 30% + 每点好感 0.6%（上限 90%）
qq/qq_commands.py:140/273  面向用户的说明也写着"说好话、逗她开心会加分；冒犯、没礼貌会扣分"
```
⇒ 所以「**不靠嘴甜**」这半句**在 QQ 侧不成立** ✗。
   而且这两套是**不同的值**：桌面端 `tool/state.py` 的 affinity（对主人）
   vs QQ 侧按 QQ 号/群维度的 0~100 好感。

## 三、怎么改的（收窄，不是删掉）

第 14 页该条改为：
> 桌面端：按真实相处证据（天数×对话量）抬高下限（affinity_floor）；
> **QQ 侧另有一套面向群聊的好感玩法，按对话内容结算**

这样既保住了"桌面端不靠嘴甜"这个真实卖点，也不会在被追问"QQ 里夸她两句会不会涨"时翻车。
讲稿同步重写，明确说出"两套"。

## 四、为什么这类审计值得做
领导/导师最容易做的动作就是"**这句在代码里哪儿？**"。
本工程反复出现的教训是"**标签/说法对错了对象**"（今天已抓到多处），
这一句属于同一类：**把桌面端的性质说成了全局的性质**。
宁可自己先收窄，也不要现场被收窄。
""")
print("✓ 已写 dev/docs/审PPT断言-关系值-2026-10-13.md")

MSG = """docs(ppt): 审出 deck 一句越界断言并收窄 —— 「不靠嘴甜」只对桌面端成立

## 审计方法
把 deck 里**具体到能被要求在代码里指出来**的句子挑出来逐句核。
第 14 页原文：「按真实相处证据（**天数×对话量**）抬高**下限**，**不靠嘴甜**」。

## 成立的一半（精确对得上）
```
tool/state.py:13    state.feel(+8, "主人摸了头")      ← 真实互动推动心情/好感
tool/state.py:188   当前关系值 —— 读的时候不低于 **affinity_floor()**，并把抬上去的值落盘
```
连"下限"这个词都与实现一致 ⇒ **保留**。

## 不成立的一半（越界）
QQ 侧是另一套，且**明确因"嘴甜"加分**：
```
qq/qq_chat.py:496   "夸奖、关心、有趣、体贴、**哄你开心** → [好感+N]，N 取 2~8（越讨你喜欢越高）"
qq/qq_chat.py:747/784/790  解析 [好感±N] → 落到 0~100 的 QQ 好感，标记从正文移除
qq/qq_galgame.py:7/9/27    约会成功 +15~25 / 失败 -15~25；成功率 = 30% + 好感×0.6%（上限 90%）
qq/qq_commands.py:140      面向用户的说明："说好话、逗她开心会加分；冒犯、没礼貌会扣分"
```
⇒ 而且两套是**不同的值**（桌面 affinity vs 按 QQ 号/群的 0~100）。

## 改法：收窄，不删
第 14 页改为「桌面端：按真实相处证据…抬高下限（affinity_floor）；
**QQ 侧另有一套面向群聊的好感玩法，按对话内容结算**」；讲稿同步，明说"两套"。
⇒ 既保住"桌面端不靠嘴甜"这个真卖点，也不会被"QQ 里夸两句会不会涨"问倒。

## 为什么值得做
评审最爱做的动作是"**这句在代码里哪儿？**"。本工程今天的反复教训是
"**说法对错了对象**"——这一句属于同一类：把**桌面端的性质说成了全局的性质**。
宁可自己先收窄。
"""
p = os.path.join(MAP, "_msg_affection.txt")
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
