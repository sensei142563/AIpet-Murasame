# -*- coding: utf-8 -*-
"""写调研报告：冷热值 + 记忆检索（只调研，不实现）。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

DOC = r'''# 调研：① 好感度 → 冷热值　② 记忆能不能"像数据库那样查"

> 状态：**仅调研，未动任何代码**（主人 2026-10-14：「以上两件事仅调研」）。
> 起因：① 提示词里的好感度已经拉满（没有张力了）→ 想改成冷热值：冷了话少、热了话多更亲密，
> 冷了偶尔触发「思念」。② 记忆想参考"数据库查找"这类做法，主人提到 `E:\111\--main`。
> 素材来源：本地克隆的三个真实实现（见文末来源），**不是空想**。

---

## 〇、结论速览（先看这个）

| 你的想法 | 现状的病根 | 最优参考 | 建议路线 |
|---|---|---|---|
| 好感度 → 冷热值 | `affinity` **只会慢慢涨、掉得很慢**（`tool/state.py` 自己写的），**必然而不是偶然**拉满 | **AnimaFlux**（情感/关系状态运行时） | **双轴 + 有界增量 + 每字段半衰期**，durable 维度只由事件驱动、不被动漂移；「思念」交给一个**缓慢衰减的心结字段**驱动 |
| 记忆像数据库 | 记忆**只按时间截断**（`[-200:] / [-60:] / [-limit:]`），**全仓库 0 处检索** | **jixia-kernel**（BM25 词法检索） | **先做零依赖 BM25**（中文用 bigram，不要分词器）→ 再加 AnimaFlux 式「显著度摘要 + 记忆引用」→ 图数据库**暂不做** |

两个想法其实是**一件事的两面**：冷热值决定"**她此刻愿不愿意多说**"，检索决定"**她此刻想起什么**"。
AnimaFlux 的管线把这两者串成了一条线：`事件 + 检索到的记忆 → 衰减 → 评估 → 有界增量 → 新状态 + 表达指引`。

---

## 一、好感度 → 冷热值

### 1.1 我们现在的实现（已核实）

```
tool/state.py（312 行）
  mood      心情 0~100，基线 60，**每小时衰减 6.0**（MOOD_DECAY_PER_HOUR）
  affinity  好感度 0~100，基线 20，**只会慢慢涨、掉得很慢**   ← 病根
  mood_label() / affinity_label()；state.feel(±N, 原因) 记一次变化并写日志

qq/qq_galgame.py（183 行）
  好感度按「群 × QQ号」存，0~100，初始 50
  **每轮由模型给出 [好感±N] 标记**，本模块负责 clamp + 持久化
  约会玩法：成功率 30% + 每点好感 0.6%（上限 90%）；成功 +15~25 / 失败 -15~25；同人同群 60 分钟冷却
  白名单主人恒定 100（不参与养成）

tool/attention.py
  mood / affinity 参与"要不要主动说话"的权重（mood < 30 有分支）
```

**病根一句话**：`affinity` 被设计成**单调上升**（"掉得很慢"），所以只要互动够多，
**一定**会到 100 —— 到了 100 之后它就不再提供任何信息量，提示词里写死"好感度拉满"只是把这个结果
提前兑现了。**不是提示词写坏了，是机制本身没有上限后的状态。**

还有一个隐患：QQ 侧的数值**由模型每轮自己给**（`[好感±N]`），
模型可以一路给 `+10`，也可以某轮情绪化地给 `-50` —— **没有限幅就不会稳定**。

### 1.2 参考实现：AnimaFlux（最贴合你的想法）

仓库：`baiyan09110/animaflux` —— 自称 *provider-neutral affective and relational state runtime*
（"把瞬时情绪 / 关系状态 / 自我定位 / 记忆影响 / 昼夜节律 / 表达指引放在**人格提示词之外**"）。

**核心管线（顺序是刻意的）**：

```
event + retrieved memory
        ↓
decay previous state          ← 先让旧状态随时间衰减
        ↓
cognitive appraisal            ← 再用"衰减后的状态"去解读这次事件
        ↓
bounded state delta            ← 增量**有界**（不许一步到位）
        ↓
new state + expression texture ← 新状态 + 只改"怎么说"的表达质感
```

原文："The ordering is deliberate: the decayed previous state participates in the
appraisal before a new delta is applied."

**可直接借用的机制**（源码里都有）：

| 机制 | 源码位置 | 内容 |
|---|---|---|
| **指数趋近** | `engine.py:53` | `_toward(value, target, hours, half_life) = target + (value-target) * 0.5 ** (hours/half_life)` |
| **每字段独立半衰期** | `engine.py:84` | `decayed()` 对每个字段按自己的 `(target, half_life)` 各自衰减 |
| **有界增量** | `engine.py:103/116` | `bounded_delta()`：先 `_clamp` 再累加，记录被夹掉的字段 |
| **心结的缓慢衰减** | `concerns.py:137/144` | `intensity * exp(-ln2 * decay_hours / easing_half_life_hours)`，默认半衰期 **24h** |
| **durable 维度只由事件驱动** | README | `affection / trust / security / attachment_depth / familiarity` **默认不被动漂移** |
| **shared_history 不是计数器** | `docs/architecture.md` | = **有界显著度摘要 + 指向有意义记忆的引用** |
| **评估器输出视为不可信** | `docs/architecture.md` | 限幅、允许字段、衰减动力学都由 policy 掌握；记录 `proposed_delta` 与 `applied_delta` |
| **昼夜节律** | `circadian.py` | `wind_down / sleepy / asleep`；1~3 次交互 = half_awake，≥4 = waking；深夜互动造成"越来越困"而不是"被消息叫精神" |
| **存储** | `storage.py` | `JsonStore`（原型）/ `SQLiteStore`（状态 + 不可变转移事件同一事务） |

### 1.3 给我们的设计草案（冷热值）

```
双轴，别再用一根"好感度"：
  轴 1  温度 warmth（-100 ~ +100，0 = 常温）
         热 → 话多、主动、亲昵称呼、愿意分享
         冷 → 话少、被动、客气、只答不问
  轴 2  耐久维度（不参与漂移，只由事件改）
         trust 信任 / security 安全感 / attachment 依恋 / familiarity 熟悉
         —— 好处：冷下来的时候"她仍然认得你、仍然信你"，
            温度只是**当下愿意说多少**，不是"关系坏了"

更新公式（照 AnimaFlux）：
  warmth ← target + (warmth - target) * 0.5 ** (Δ小时 / 半衰期)      # 先衰减
  Δ = clamp(模型给出的增量, -Δmax, +Δmax)                          # 再限幅
  warmth ← clamp(warmth + Δ, -100, +100)                          # 再截断

思念：单开一个"心结/想念"字段（对应 AnimaFlux 的 unresolved_tension）
  · 只有它**有缓慢被动衰减**；温度低 + 久未互动 ⇒ 它的强度回升
  · 强度过阈值就**主动触发一次**（"主人今天……没怎么理我"）——这就是你说的"冷了偶尔思念"
  · 触发后强度清零/回落，避免连续刷屏（配合 attention.py 现有的主动说话权重）

表达侧（expression texture）：只改"怎么说"，不改事实与能力
  · 温度映射到句长/语气/主动提问率/称呼；**别写进人格提示词**，而是作为**附加指引**注入
  · 这样"提示词里写死好感度"那套就可以删掉
```

### 1.4 与我们现有代码的对接点

- `tool/state.py`：`mood` 已有衰减（6/小时）可保留为**短周期情绪**；新增 `warmth` 作为**关系温度**；
  `affinity` 建议**改名为耐久维度**或直接复用为 `attachment`（避免"单调上升"语义）。
- `qq/qq_galgame.py`：模型给的 `[好感±N]` **加限幅**（现在是直接 clamp 到 0~100，没有单轮上限）；
  白名单主人恒 100 的逻辑要跟着新语义走（否则主人永远是"最热"）。
- `tool/attention.py`：主动说话的触发条件从 `affinity` 改为 `warmth + 思念强度`。
- `tool/chat.py`：现在提示词里写死的关系描述改为**读状态生成**。

### 1.5 风险 / 开放问题

1. **冷会不会让主人觉得"她变冷了、不好玩了"？** ⇒ 建议：冷时**减少主动发言量**但**不减少回应质量**；
   且耐久维度不掉，"冷"只体现在节奏上。
2. **数值要不要可见？** 现在状态页有五页签；冷热值可加一个温度条（或先只在日志里可见）。
3. **半衰期多长？** AnimaFlux 明说它的默认值"是透明的起步值、不是心理学标定" ⇒ 我们也照此声明，
   先给一组能跑的（例如温度半衰期 12~24h、心结 24~72h），再用实际对话体感调。
4. **模型给的增量不可信** ⇒ 必须限幅 + 记录（照 AnimaFlux 的审计做法），否则会重演"一轮拉满"。

---

## 二、记忆能不能"像数据库那样查"

### 2.1 我们现在的实现（已核实）

```
存：JSON 文件
    data/long_history.json                 （桌宠与 QQ 共享的长期记忆）
    pets/<id>/memory/{history,long_history}.json
    QQ 分仓 private_<QQ>.json（白名单主人走共享）
    tool/self_learn.py：notes / diary / episodes（eps [-200:]、diary 最近 60、summary_text(limit=10)）

取：**只按时间截断** —— load_long_history(max_turns=...)、[-200:]、[-60:]、[-limit:]、[-3:]
    **全仓库 0 处检索**（没有 search / embed / top_k / 相似度）
```

**病根一句话**：记忆是"**最近优先的队列**"，不是"**可查询的库**"。
所以早期重要的事（"主人说过他要考研"）会被后面 200 条闲聊挤出去。

### 2.2 三条参考路线（都来自真实仓库）

#### 路线 A：BM25 词法检索（jixia-kernel，**零依赖，最推荐先做**）

`E:\111\--main\jixia-kernel`（Rust）：

```
crates/kernel/src/retriever.rs   → trait KnowledgeRetriever（接口）
crates/stdio/src/tools.rs        → 实现 WikiRetriever
   「课程知识检索：**BM25（词条名加权 + 正文）+ 别名命中 + 关系图一跳扩展**」

打分（可直接翻成 Python）：
  K1 = 1.2, B = 0.75, NAME_WEIGHT = 3.0
  name_tokens = tokenize(词条名) + tokenize(每个别名)
  body_tokens = tokenize(正文)
  idf = ln(1 + (n - df + 0.5) / (df + 0.5))
  饱和项 sat(tf, dl) = tf*(K1+1) / (tf + K1*(1 - B + B*dl))     # dl = 长度/平均长度，名与正文各自归一
  score = Σ_token idf * (3.0 * sat(tf_name, dl_n) + sat(tf_body, dl_b))
        + **9.0** 若整名命中（term ⊆ query 或 query ⊆ term）
        + **6.0** 若别名命中
        + 关系图一跳扩展：取 3 个种子，关联项 += seed_score * 0.4

中文怎么切（关键，**不需要分词器**）：
  · ASCII 字母数字 → 攒成词（长度 ≥ 2 才保留，转小写）
  · CJK 字符 → 攒成串：长度 1 就单字；长度 ≥ 2 就输出**所有相邻二元组**
    例：「记忆检索」→ ["记忆","忆检","检索"]
  · 其它字符当分隔符
  ⇒ 好处：无词典、无依赖、召回率高；精度靠 IDF + 词条名加权补

工程细节：top_k 默认 8，clamp(1, 12)（engine.rs）
```

**对我们意味着什么**：把"词条"换成"记忆条目"（一条记忆 = {标题/主题, 正文, 别名, 关联}），
BM25 + 整名/别名加成就是"**像数据库一样查**"的最小可用版本，**不用装任何东西**。

#### 路线 B：结构化画像 + 事件 gist（memobase）

```
memobase 自述：**user profile-based memory system**，并明说"**不是为 RAG/检索任务设计的**"
  · 每个用户 = 一组**结构化 profile**（topic / sub_topic …），直接塞进 system prompt
  · 另有 **event gist**（事件摘要）支持按时间线细查；context 检索约 500~1000ms
  · 仓库里自带与 mem0 的对比实验（docs/experiments/…）
⇒ 适合"她记住主人是谁"（画像），不适合"从一千条记忆里捞出那一条"
```

#### 路线 C：时序知识图谱（graphiti / Zep）

```
graphiti（Python，192 个相关文件）
  · 用 LLM **抽取实体与关系** → 存成**时序知识图谱**（nodes / edges，带时间有效性）
  · graphiti_core/search/ ：多路检索（语义 + BM25 + 图遍历）+ 可选 reranker
⇒ 能力最强，但**重**：要 LLM 抽取、要图/向量库、要维护时间有效性
⇒ 对一个桌宠，**现在不做**（记住它在"未来规划"里当储备即可）
```

#### 补充：AnimaFlux 的 `shared_history`（最小巧的一条）

```
"shared_history is **not a counter**: it combines a **bounded salience summary** with
 **references to meaningful memories**."
⇒ 即：长期记忆 = 一小段"显著度摘要"（有字数上限）+ 若干**指向原始记忆的引用**（id）
   ⇒ 既省 token，又能在需要时"顺着引用回去查原文" —— 和路线 A 天然互补
```

### 2.3 建议的落地顺序（分三步，每步都能独立见效）

```
第 1 步（零依赖，1 个模块）：把现有 JSON 记忆**索引化**，加 BM25 检索
    · 一条记忆 = {id, 时间, 主题, 正文, 别名[], 关联[]}（现有 JSON 字段映射即可）
    · tokenize 用 bigram；打分照抄上面的公式
    · 对外一个函数：search(query, top_k=8) → [记忆条目]
    · 与"最近 N 条"**混合**：最近 N 条保底 + 检索到的 top_k 补充（防止只检索不连贯）

第 2 步：显著度与引用（照 AnimaFlux）
    · 给每条记忆算一个**显著度**（情绪强度 / 是否被反复提起 / 是否被标"重要"）
    · 长期上下文里只放"**有界显著度摘要 + 引用**"；需要细节时再按引用取全文

第 3 步（可选，远期）：只有当第 1、2 步不够用时，才考虑图/向量

### 2.4 对接点

- `qq/qq_memory.py` / `longtext/longtext_history.py`：这两个是"取记忆"的统一入口
  ⇒ 把 `load_*` 内部从"切最近 N 条"改成"最近 N 条 + search() 命中"，**调用方不用改**。
- `tool/self_learn.py`：notes / diary / episodes 已经是有结构的条目 ⇒ 正好当"记忆条目"的语料。
- `tool/memory_transfer.py`：导入导出格式里已经有 history / long_history ⇒ 加 memo 字段即可向后兼容。
- 需要"按人分仓"的记忆（QQ 非白名单）⇒ 索引也要**按仓**建，别串味。

### 2.5 风险 / 开放问题

1. **bigram 会不会误召回？** 会（"记忆"和"记性"都命中"记忆"）⇒ 靠 IDF + 整名/别名加成压；
   真要更准再加"两点：条目名加权"和"一次只取 top_k=5~8"。
2. **什么时候检索？** 每轮都检索（快，毫秒级）or 只在"话题跳变/被问起"时检索？
   ⇒ 建议先每轮都跑，但**只在命中分数超过阈值时才注入**，避免无相关也被塞进来。
3. **注入多少？** 检索到的条目要**截断到字数上限**（AnimaFlux 表达式编译默认 ≤1200 字符、≤6 条规则，
   这个"有界"的思路值得抄）。
4. **隐私/分仓**：检索必须尊重现有的分仓规则（白名单主人共享、其他人隔离）。
5. **向量要不要？** 本地跑 embedding 会**再引入一个大依赖**（本机已因 f5-tts/onnx 吃过环境的亏）
   ⇒ 在 BM25 够用之前**不引入**；真要用也优先"已有依赖能做的"（如 sentence-transformers 已在全局？待查）。

---

## 三、来源与许可证

| 来源 | 用途 | 许可证提示 |
|---|---|---|
| `baiyan09110/animaflux`（本地克隆到 `E:\university\order\research-refs\animaflux`） | 冷热值 / 状态衰减 / 有界增量 / 心结 / 昼夜节律 / shared_history | **PolyForm Noncommercial 1.0.0**：可学习、可改、可非商业再分发；**商业用途未授权** ⇒ **只借思路，代码自己写** |
| `E:\111\--main` → `jixia-kernel`（Rust） | BM25 检索实现（含中文 bigram 切分） | 主人自己的项目 |
| `memodb-io/memobase`（本地克隆） | 结构化画像 + event gist 路线 | 见其仓库 LICENSE（未逐一核对） |
| `getzep/graphiti`（本地克隆） | 时序知识图谱路线（储备） | 见其仓库 LICENSE（未逐一核对） |

> 三个仓库都克隆在 `E:\university\order\research-refs\`（**仓库外**，不入 git）。
> 参考代码**不要直接拷进项目**：一是许可证，二是架构不同（主人原话：毕竟是不同的项目，
> 实现肯定不同）—— **只取机制，按我们的数据结构重写**。

---

## 四、待主人拍板的问题

1. 冷热值：**双轴**（温度 + 耐久）这个拆法认不认？还是只要一根温度？
2. 冷的时候：**减少主动发言量**但保持回应质量 —— 这个尺度对吗？
3. 「思念」的触发：只在"久未互动"时，还是"温度低 + 久未互动"都要？（前者更温和）
4. 记忆检索：先做**第 1 步（BM25）**吗？要不要**同时**把"最近 N 条保底"保留？
5. 数值与检索结果要不要在**启动器状态页**可视化（方便你调参、也方便答辩展示）？
'''

p = os.path.join(ROOT, "dev", "docs", "调研-冷热值与记忆检索-2026-10-14.md")
io.open(p, "w", encoding="utf-8", newline="\n").write(DOC)
print("✓ 已写 %s" % p)
print("   %d 字符 / %d 行" % (len(DOC), DOC.count("\n") + 1))

# 行尾自查（本仓库是 LF）
d = open(p, "rb").read()
print("   行尾：CRLF=%d LF=%d （本仓库约定 LF ✓）" % (d.count(b"\r\n"),
                                                   d.count(b"\n") - d.count(b"\r\n")))

MSG = """docs(research): 调研「好感度→冷热值」与「记忆像数据库一样查」（仅调研，未改功能代码）

## 主人要求
"关于好感度…在考虑把好感度换成冷热值…冷了偶尔触发思念。
 另一个想法是咱们记忆能不能参考数据库查找之类的东西？之前做的 E:\\111\\--main 或许可以参考。
 **以上两件事仅调研**"

## 做法
1. 看了主人提到的 `E:\\111\\--main` ⇒ 命中 `jixia-kernel`（Rust）的检索实现：
   `WikiRetriever` = **BM25（词条名权重 3.0 + 正文）+ 整名命中 +9 + 别名命中 +6 + 关系图一跳 ×0.4**，
   top_k 默认 8、clamp(1,12)；**中文用 bigram 切分，不需要分词器**。
2. 按主人提示去 GitHub 找同类（网页抓不动 ⇒ 改用 git 克隆到仓库外 `research-refs\\`）：
   - `baiyan09110/animaflux`（情感/关系状态运行时）—— **正好是"冷热值"要的架构**：
     管线 `事件+检索记忆 → 衰减 → 评估 → 有界增量 → 新状态+表达指引`；
     `_toward = target + (value-target) * 0.5**(hours/half_life)`（每字段独立半衰期）；
     durable 维度只由事件驱动；`unresolved_tension` 才有缓慢被动衰减
     ⇒ **直接对应"冷了偶尔触发思念"**；`shared_history` = 有界显著度摘要 + 记忆引用。
     许可证 **PolyForm Noncommercial** ⇒ 只借思路、代码自己写。
   - `memodb-io/memobase`（画像 + 事件 gist）、`getzep/graphiti`（时序知识图谱，储备）
3. 核实我们自己的现状（不靠猜）：
   - `tool/state.py`：mood 有衰减（6/小时），但 **affinity「只会慢慢涨、掉得很慢」⇒ 必然拉满**（病根）
   - `qq/qq_galgame.py`：好感度由**模型每轮给 [好感±N]**，只有 0~100 截断、**没有单轮限幅**
   - 记忆：**全仓库 0 处检索**，全部是"最近优先截断"（`[-200:]`/`[-60:]`/`[-limit:]`）

## 产出
`dev/docs/调研-冷热值与记忆检索-2026-10-14.md`：
结论速览表 / 现状（含代码位置）/ AnimaFlux 机制表（公式与出处）/ 冷热值设计草案（双轴 + 有界增量 +
每字段半衰期 + 思念触发器）/ 三条记忆路线对比 / **分三步的落地顺序**（先零依赖 BM25，
再显著度+引用，图暂不做）/ 对接点 / 风险 / 来源与许可证 / 5 个待拍板问题。

## 顺手修掉一个我自己闯的祸（重要）
按技能里"本仓库是 CRLF"的提示，我写了个脚本把所有文本文件改成 CRLF —— **错了**：
本仓库 `core.autocrlf = false`、无 `.gitattributes`、索引里是 **LF**，
那条提示说的是**另一个仓库**。结果 981 个文件被标成改动。
已用"先断言全部是纯行尾（增删行数相等）再回退"的安全闸整体回退，排除 `dev/ppt/out/`（成品图），
现工作区只剩本轮的未跟踪脚本 + 一张重新生成的总览图。**结论：本仓库用 LF。**
"""
mp = os.path.join(MAP, "_msg_research.txt")
io.open(mp, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", mp], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("✓ 提交：", (rc.stdout or rc.stderr or "").splitlines()[0][:140])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("   未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
