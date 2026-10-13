# -*- coding: utf-8 -*-
"""按用户给的新增比对清单写市场文档 + 往 deck 插一页，并把讲稿与操作单的页码一起改对。

新增对标（7 个）：兽耳助手 / Live2DViewerEX(Steam) / 人工桌面(yoyo鹿鸣) / Shimeji /
                  天选姬(天选桌宠) / 虚拟桌宠模拟器 VPet / BongoCat
"""
import io
import json
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")
DOC = os.path.join(ROOT, "docs", "桌面桌宠市场补充对标-2026-10-13.md")

DOC_TEXT = """# 桌面桌宠 / 虚拟形象市场：补充对标（2026-10-13）

> 起因：用户点名要补 7 个常见对标 —— 兽耳助手、Live2DViewerEX（Steam）、
> 人工桌面（yoyo鹿鸣）、Shimeji、天选姬（天选桌宠）、虚拟桌宠模拟器（VPet）、BongoCat。
> 原则同前：**只写查到的**；查不到的写"待补"，不编。

## 一、逐个事实（含出处）

### 1. 兽耳助手（Mimikko，兽耳科技）
- 形态：手机端 **App**（魅族应用商店有条目 `com.mimikko.mimikkoui`），另有 4.0 版本分发页；
- 定位：**AI 助手 + 兽耳角色形象**（"助手"为主、形象为辅）；
- 出处：[魅族应用商店](https://app.meizu.com/apps/public/detail?package_name=com.mimikko.mimikkoui)、
  [百度百科·兽耳助手](https://baike.baidu.com/item/%E5%85%BD%E8%80%B3%E5%8A%A9%E6%89%8B/61311781)、
  [4.0 分发页](https://m.youxibao.com/app/19059.html)
- ⚠ 待补：它有没有**长期记忆 / 主动开口**（我这次没查到确证，不替它下结论）。

### 2. Live2DViewerEX（Steam，Pavo Studio）
- Steam **软件**（类别是 *Utilities / Animation & Modeling*，**不是游戏**），AppID **616720**；
- 2017-06-30 抢先体验、2021-12-31 正式；售价 **¥26**，另有 Spine Expansion DLC ¥10；
- 官方自述：**"跨平台 Live2D 方案，三种显示模式（壁纸 / 桌面 / 桌面窗口），
  多平台（Windows / macOS / Android / iOS），高精度面部捕捉"**；支持 **Steam 创意工坊**；
- 口碑：英文评论 211 条、**89% 好评**（Very Positive）；
- 出处：[Steam 商店页](https://store.steampowered.com/app/616720/)
- **这条对我们的意义**：它是"**把模型放出来**"这一类里的天花板 —— 跨平台、面捕、创意工坊都很强，
  但**它不陪聊、不记事、不主动**：它解决"**看得见**"，不解决"**有关系**"。

### 3. 人工桌面（yoyo鹿鸣，米哈游）
- 形态：**厂商出的桌面应用**，主角是 3D 虚拟角色 **yoyo鹿鸣**；
- 出处：[百度百科·yoyo鹿鸣](https://baike.baidu.com/item/yoyo%E9%B9%BF%E9%B8%A3/53536152)、
  [人工桌面条目](https://www.3839.com/a/128259.htm)
- **对我们的意义**：**大厂级别的"桌面伙伴"**，形象质量高；
  但它是**内容型**（看板娘 + 互动演出），不是"会记事、会主动找你"的角色。

### 4. Shimeji（日系开源桌面宠物，多衍生）
- 形态：经典桌面宠物，**开源 + 大量衍生版**（例如 Clover Shimeji、霍星桌宠等都是 Shimeji 系）；
- 出处：[Clover_Shimeji](https://github.com/Stuocs/Clover_Shimeji)、
  [Huo_Xing_Shimeji](https://github.com/elainyilanchen/Huo_Xing_Shimeji_destop_pet)
- **对我们的意义**：它是"桌面宠物"这个**品类的老祖宗**（爬窗口、扔来扔去），
  至今大多数开源桌宠仍是这一路：**行为脚本化、不接大模型**。

### 5. 天选姬 / 天选桌宠（华硕）
- **ASUS 官方支持文档里直接出现"天选桌宠"**（与 Armoury Crate、小硕知道并列），
  说明它是**厂商随机器/软件提供的吉祥物桌宠**；
- 出处：[ASUS 官方 FAQ 1056833](https://www.asus.com.cn/support/faq/1056833/)
- **对我们的意义**：**硬件厂商的流量入口型桌宠** —— 目的是品牌陪伴/预装存在感，
  不是"长期个人助理"。这类产品不会做"记住你昨天说了什么"。

### 6. 虚拟桌宠模拟器（VPet，LorisYounger）
- **开源**（GitHub `LorisYounger/VPet`），Steam AppID **1920960**；
- 技术形态：**C# / WPF**，社区提及其可**内置到 WPF 应用程序**；
- 出处：[GitHub VPet](https://github.com/lorisyounger/vpet)、
  [Steam 1920960](https://store.steampowered.com/app/1920960/)、
  [相关条目](https://github.com/CHINGHE/windows-)
- **对我们的意义**：**开源桌宠里最"产品化"的一个**（有 Steam 页、有养成系统、有创意工坊氛围）。
  它证明"养成 + 开源"这条路能成；但它的核心是**养成数值**，不是**对话与记忆**。

### 7. BongoCat（C × SDL3 × OpenGL）
- **纯开源桌面玩具**：一只跟着你敲键盘/点鼠标动的猫（多个 fork，如 `vladelaina/BongoCat`、
  `xrr2016/BongoCat`）；
- 出处：[vladelaina/BongoCat](https://github.com/vladelaina/BongoCat)、
  [xrr2016/BongoCat](https://github.com/xrr2016/BongoCat)
- **对我们的意义**：**极轻量、零 AI**。它代表另一极：不要模型、不要显存、只要可爱。
  也提醒我们："桌宠"这个词的**默认预期**其实很低（动一动就够了）——
  我们要说服别人的，正是"**她可以不只是动一动**"。

## 二、七条放一起看，得出一句话

| 产品 | 类型 | 有形象 | 接大模型/会聊 | 长期记忆 | 主动开口 | 跨端（手机/IM） | 开源 |
|---|---|---|---|---|---|---|---|
| 兽耳助手 | 商业 App | ✅ | 部分（助手向） | 待补 | 待补 | 手机端 ✅ | ✗ |
| Live2DViewerEX | Steam 商业工具 | ✅（面捕/工坊） | ✗ | ✗ | ✗ | 多平台 ✅ | ✗ |
| 人工桌面（鹿鸣） | 大厂桌面应用 | ✅（3D） | ✗ | ✗ | ✗ | ✗ | ✗ |
| Shimeji 系 | 开源 | ✅ | ✗ | ✗ | ✗ | ✗ | ✅ |
| 天选桌宠 | 厂商吉祥物 | ✅ | ✗ | ✗ | ✗ | ✗ | ✗ |
| VPet 虚拟桌宠模拟器 | 开源（Steam） | ✅（养成） | ✗ | ✗ | ✗ | ✗ | ✅ |
| BongoCat | 开源玩具 | ✅（极简） | ✗ | ✗ | ✗ | ✗ | ✅ |
| **我们** | 开源 + 角色 | ✅（Live2D + 3D/AR） | ✅ **接大模型** | ✅ **长期记忆/日记/习惯** | ✅ **她自己找你** | ✅ **桌面 + 手机 + QQ/微信** | ✅ |

> **一句话**：这七类都在做"**形象**"和"**养成**"，只有我们在做"**关系**" ——
> 形象是入口，关系才是留存。这也正是导师问的"壁垒/优势"能落地的那个点。

## 三、写进 deck 的方式
新增一页（插在"他们 vs 我们"之后），只放 4 行结论 + 这张表的核心几列，
**不逐个念产品**（念了听众记不住）；逐个细节放在本文件里，被追问再答。

## 四、仍然没有查实的（不写进 deck）
- 兽耳助手是否有长期记忆/主动开口（待补）；
- 天选桌宠的具体交互能力（官方文档只提到它存在）；
- VPet 是否接任何 LLM（我查到的是养成系统，未查到 LLM 集成）。
"""

io.open(DOC, "w", encoding="utf-8", newline="\n").write(DOC_TEXT)
print("✓ ① 已写 docs/桌面桌宠市场补充对标-2026-10-13.md")

# ---------- ② 往 deck 插一页（放在第 9 页之后 → 成为新的第 10 页）----------
OUT = os.path.join(ROOT, "dev", "ppt", "outline.json")
o = json.loads(io.open(OUT, encoding="utf-8", errors="replace").read())
slides = o["slides"]
new_slide = {
    "type": "content",
    "title": "更广的同类：都在做「形象」，只有我们在做「关系」",
    "bullets": [
        {"text": "展示工具类", "sub": "Live2DViewerEX（Steam，¥26）：跨平台 + 高精度面捕 + 创意工坊，"
                                     "把模型放出来这件事做到了天花板 —— 但它不聊、不记、不主动"},
        {"text": "养成 / 玩具类", "sub": "Shimeji 系、BongoCat（C+SDL3，纯开源）、"
                                       "虚拟桌宠模拟器 VPet（开源 + Steam）—— 可爱、轻量，核心是动作与数值"},
        {"text": "大厂 / 厂商吉祥物", "sub": "人工桌面（yoyo 鹿鸣，3D 看板娘）、天选桌宠（华硕随机器）"
                                          "—— 形象质量高，但是内容型、不是会记事的个人角色"},
        {"text": "手机端助手", "sub": "兽耳助手：助手向 + 角色形象（记忆与主动性待核实，不替它下结论）"},
        {"text": "共同点", "sub": "这七类都停在「看得见」：有形象、有动作、有养成 —— "
                               "**没有一类把「长期记忆 + 主动开口」当成核心**"},
        {"text": "所以我们的位置", "sub": "形象是入口，关系才是留存；我们做的是她记得你、也会主动找你"},
    ],
}
# 插到第 9 页（index 8）之后
slides.insert(9, new_slide)
json.dump(o, io.open(OUT, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=2)
print("✓ ② 已插入新页（现在是第 10 页），deck 共 %d 页" % len(slides))

# ---------- ③ 讲稿整体后移一位（≥10 的页），并给新页写讲稿 ----------
NT = os.path.join(ROOT, "dev", "ppt", "notes.json")
n = json.loads(io.open(NT, encoding="utf-8", errors="replace").read())
notes = n["notes"]
old_max = max(int(k) for k in notes)
shifted = {}
for i in range(old_max, 9, -1):
    if str(i) in notes:
        shifted[str(i + 1)] = notes[str(i)]
for k, v in shifted.items():
    notes[k] = v
notes["10"] = ("这一页是把同类补齐：展示工具（Live2DViewerEX）、养成与玩具（Shimeji、BongoCat、"
               "虚拟桌宠模拟器 VPet）、大厂吉祥物（人工桌面 yoyo 鹿鸣、天选桌宠）、"
               "手机端助手（兽耳助手）。\n"
               "它们各有各的强：ViewerEX 把跨平台和面捕做到天花板，VPet 把开源养成的产品化做成了，"
               "鹿鸣的形象质量是大厂级。\n"
               "但有一件事它们都没做：**长期记忆 + 主动开口**。都在做「形象」，我们在做「关系」。"
               "形象是入口，关系才是留存。")
n["notes"] = {k: v for k, v in sorted(notes.items(), key=lambda kv: int(kv[0])) if v}
io.open(NT, "w", encoding="utf-8", newline="\n").write(
    json.dumps(n, ensure_ascii=False, indent=2))
print("✓ ③ 讲稿已整体后移一位，并补上新第 10 页（共 %d 页讲稿）" % len(n["notes"]))

# ---------- ④ 操作单里的页码一起后移 ----------
F = os.path.join(ROOT, "dev", "docs", "PPT录屏截图操作单-2026-10-13.md")
t = io.open(F, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
PAGEMAP = {12: 13, 13: 14, 14: 15, 15: 16, 16: 17, 18: 19, 19: 20, 20: 21, 21: 22}
cnt = 0
for old, new in sorted(PAGEMAP.items(), reverse=True):
    # 只改映射表那一列的开头 "| NN |"
    pat = re.compile(r"^\| %d \|" % old, re.M)
    t2, k = pat.subn("| %d |" % new, t)
    if k:
        t = t2
        cnt += k
# 标题里的页数
t = t.replace("（deck 现为 **23 页**", "（deck 现为 **24 页**")
io.open(F, "w", encoding="utf-8", newline="\n").write(t)
print("✓ ④ 操作单映射表页码已后移（改了 %d 行），页数 23→24" % cnt)

MSG = """docs(research)+docs(ppt): 补 7 个对标（兽耳助手/Live2DViewerEX/鹿鸣/Shimeji/天选姬/VPet/BongoCat）+ 新增一页

## 用户点名的 7 个对标（都查了出处）
- **Live2DViewerEX**（Steam 616720，Pavo Studio）：类别是 **Utilities 不是游戏**；
  2017 EA / 2021 正式；¥26；官方自述"跨平台 + 三种显示模式 + 高精度面部捕捉"；Steam 创意工坊；
  英文 211 条评论 89% 好评。⇒ "把模型放出来"这一类的天花板，但**不聊不记不主动**。
- **虚拟桌宠模拟器 VPet**（GitHub LorisYounger/VPet，Steam 1920960）：开源、C#/WPF、
  可内置进 WPF 应用 ⇒ 开源桌宠里最"产品化"的一个，核心是**养成数值**。
- **BongoCat**（C × SDL3 × OpenGL，多 fork）：跟着键鼠动的猫，**零 AI、极轻量**。
- **Shimeji 系**：桌面宠物品类老祖宗，大量衍生（Clover Shimeji / 霍星桌宠…），行为脚本化。
- **人工桌面 yoyo 鹿鸣**（米哈游）：大厂级 3D 桌面看板娘，**内容型**。
- **天选姬 / 天选桌宠**（华硕）：**ASUS 官方支持文档里直接出现"天选桌宠"** ⇒ 厂商吉祥物型。
- **兽耳助手**（兽耳科技）：手机端 AI 助手 + 角色形象；**记忆与主动性未查到确证 ⇒ 写"待补"**。

## 结论一句话（写进 deck 新页）
这七类都在做「**形象**」（展示/养成/吉祥物/玩具），**没有一类把「长期记忆 + 主动开口」当核心**。
⇒ 形象是入口，**关系才是留存**。

## 落地
- 新文档 `docs/桌面桌宠市场补充对标-2026-10-13.md`（逐个事实 + 出处 + 8 行对照表 + "仍没查实的"）；
- deck 插入**新的第 10 页**（放在"他们 vs 我们"之后），deck 23 → **24 页**；
- **讲稿整体后移一位**（≥10 页），并给新页补写讲稿；
- **操作单映射表页码同步后移**（12→13 … 21→22），页数标注 23→24 ——
  这一步不做的话，用户照着旧页码贴图就会全错位（本会话已吃过一次这种亏）。
"""
p = os.path.join(MAP, "_msg_7more.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:170])
nn = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                    capture_output=True, text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条" % nn)
