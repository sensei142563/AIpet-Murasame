# -*- coding: utf-8 -*-
"""批量审 deck 断言的产出：
   ① 修第 14 页"状态页四个分类：状态/习惯/记忆/提醒" —— 实为**五个页签**：
      现在 / 习惯 / 心里 / 提醒 / 记忆（status_snapshot.py:141/163/223/243/264）
   ② 把这次批量审计的结果写成文档（4 条成立 + 1 条已修）。
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
            if b.get("text") == "状态看得见":
                b["sub"] = "状态页五个页签：现在 / 习惯 / 心里 / 提醒 / 记忆"
        print("✓ ① 第 14 页「状态看得见」已改为五页签（含真实标题）")
        break
json.dump(o, io.open(OUT, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=2)

n = json.loads(io.open(NOTES, encoding="utf-8", errors="replace").read())
for i, s in enumerate(slides, 1):
    if s.get("title", "").startswith("怎么做到的（二）"):
        n["notes"][str(i)] = (
            "记忆是分层的：对话记忆、长期记忆、日记、状态快照各管一段。"
            "关系值分两套，要说清楚：桌面端按**真实相处证据**（相处天数×对话量）抬高一个下限，"
            "不是聊几句好话就涨；QQ 侧另有一套面向群聊的好感玩法，按对话内容结算。"
            "她空闲时会自己补课、归纳关于我的事，还会写日记。"
            "状态页有五个页签：现在 / 习惯 / 心里 / 提醒 / 记忆。")
        print("✓ ② 讲稿已同步（含五页签）")
        break
io.open(NOTES, "w", encoding="utf-8", newline="\n").write(
    json.dumps(n, ensure_ascii=False, indent=2))

D = os.path.join(ROOT, "dev", "docs", "审PPT断言-批量5条-2026-10-13.md")
io.open(D, "w", encoding="utf-8", newline="\n").write("""# 批量审 deck 断言（2026-10-13）：5 条里 4 条成立、1 条不准

> 方法：挑 deck 里**具体到能被要求在代码里指出来**的句子，逐条回代码核，给出依据行。
> 这比"整体读一遍觉得没问题"可靠；今天已经靠这个方法抓到多处越界/错位的说法。

## ✗ A. 「状态页四个分类：状态 / 习惯 / 记忆 / 提醒」——**不准，已修**

实测 `tool/status_snapshot.py` 返回 **五块**（每块带自己的 `title`）：

```
:141  {"key": "now",    "title": "现在", …}
:163  {"key": "habits", "title": "习惯", …}
:223  {"key": "mind",   "title": "心里", …}
:243  {"key": "remind", "title": "提醒", …}
:264  {"key": "memory", "title": "记忆", …}
```
`pcl_launcher/status_panel.py:190` 逐个 `addTab(area, title)` 建页签 ⇒ 界面上就是这五个。

⇒ 正确的是：**五个页签：现在 / 习惯 / 心里 / 提醒 / 记忆**。
   原句错在三处：① 数量 4（实为 5）② 第一个叫"状态"（实为"现在"）③ 漏了"心里"。
   **已改**（第 14 页与讲稿同步）。

## ✓ B. 「她自己会学：空闲时自己补课、归纳"关于主人的事"」——成立

```
tool/self_learn.py:8   1. **归纳记忆**：聊完一段，她自己提炼"关于主人的事"（喜好、习惯、正在忙什么）
tool/self_learn.py:43  p = os.path.join("data", "self_learn.log")
data/self_learn.log    693 KB / 10175 行；末几条含"写好了 2026-09-30 的日记"
```
补充说明（不算问题，但讲的时候别夸张）：日志最后一条是 **2026-09-30**，
之后桌宠没怎么跑，所以近期没有新记录 —— 功能在，但"一直在学"要看它有没有在运行。

## ✓ C. 「装扮即数据：衣服 / 发型 / 装饰 / 姿势都是层号，换装=换层再合成」——成立

```
tool/portrait_outfit.py:56   # 层号一一对应，如下（丛雨 a 套；b 套半身立绘没有腕差分）：
tool/portrait_outfit.py:198  def _pet_tables(set_name=None, pet_id=None):   # 每角色一套层表
tool/portrait_outfit.py:201  新角色的立绘层号跟丛雨完全不同（芳乃 a 套校服 1860、b 套 1997）
```
⇒ 层号确实是数据，且**按角色分别维护**（这也解释了为什么换装必须"换身体"）。

## ✓ D. 「一套引擎跑多个角色，各有各的记忆与声音」——成立（实际比 deck 说的更强）

```
pets/ 下：arona / hiyori / murasame / natsume / noir（+ _template）
  各带 pet.json ✓ voices ✓；多数还带 memory ✓ live2d ✓；murasame 另有 fgimages ✓
```
⇒ 引擎与角色包确实是分离的。**但**：README/deck 说"随附丛雨与诺瓦两个示范角色"——
其余几个（arona / hiyori / natsume 等）看起来是**未完成的角色包**（natsume 缺 memory/live2d），
所以对外表述仍以"两个完整示范角色"为准，**不要拿数量吹**（这一条留给用户判断，不擅自改）。

## ✓ E. 「手机端与桌面端共用同一套记忆」——成立

```
chatter/.../MemoryStore.kt:12  每个桌宠独立记忆，存储在 pets/<角色>/memory/ 下
                          :15  - long_history.json: 完整对话（最近 N 轮）
                          :16  - history.json:      同步写入的短文本记忆
```
⇒ 与桌面端**同名同构**，因此跨端可以共用同一份（这也是 deck 第 15 页"共用同一份记忆"的依据）。

## 小结
5 条里 4 条成立、1 条不准（已修）。**不准的那条恰好是最容易被现场点开看的**（打开启动器数页签）。
""")
print("✓ ③ 已写 dev/docs/审PPT断言-批量5条-2026-10-13.md")

MSG = """docs(ppt): 批量审 5 条 deck 断言 —— 4 条成立，1 条不准（状态页是**五个**页签）

延续"能指出代码的句子就回代码核"的方法，一次审 5 条。

## ✗ 不准并已修：第 14 页「状态页四个分类：状态 / 习惯 / 记忆 / 提醒」
`tool/status_snapshot.py` 实际返回**五块**（status_panel.py:190 逐个 addTab）：
```
:141 "现在"   :163 "习惯"   :223 "心里"   :243 "提醒"   :264 "记忆"
```
⇒ 错三处：数量（4→实为 5）、第一个标题（"状态"→实为"现在"）、漏了"心里"。
已改为「状态页五个页签：现在 / 习惯 / 心里 / 提醒 / 记忆」，讲稿同步。
**这条尤其要紧**：它是最容易被现场点开启动器数一数的那句话。

## ✓ 成立的四条（含依据行）
- **B 自学**：`tool/self_learn.py:8`「聊完一段，她自己提炼"关于主人的事"」；
  `data/self_learn.log` 693 KB / 10175 行，末条"写好了…的日记"。
  （附注：最后一条是 2026-09-30，之后桌宠没怎么跑 ⇒ 讲解时别说成"一直在学"。）
- **C 装扮即数据**：`portrait_outfit.py:56`「层号一一对应…」+ `:198 _pet_tables()` 每角色一套层表；
  `:201` 记录"新角色的立绘层号跟丛雨完全不同"。
- **D 多角色**：`pets/` 下 5 个角色包 + `_template`，各带 pet.json/voices，多数带 memory/live2d。
  ⚠ 但其余几个是不完整包（natsume 缺 memory/live2d）⇒ 对外仍按"两个完整示范角色"讲，
  **不拿数量吹**（这一条留给用户判断，未擅自改文案）。
- **E 手机端共用记忆**：`MemoryStore.kt:12-16` 明确 `pets/<角色>/memory/` 下
  `long_history.json` + `history.json`，与桌面端同名同构。

原文件另存 `dev/docs/审PPT断言-批量5条-2026-10-13.md`。
"""
p = os.path.join(MAP, "_msg_audit5.txt")
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
