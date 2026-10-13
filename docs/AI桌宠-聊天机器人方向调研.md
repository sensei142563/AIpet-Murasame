# AI 桌宠项目 · 市场调研：聊天机器人 / AI 陪伴方向

> 调研时间：2026-10-13
> 数据来源：各项目官方 README（raw.githubusercontent.com）、GitHub REST API、shields.io、ecosyste.ms
> **Star 数为 2026-10-13 通过 shields.io / ecosyste.ms 抓取的约数**（GitHub 官方 API 当日触发限流，故部分采用镜像源；已标注来源）
> 凡未查到的结论，本文一律标注"**未查证**"，不做推测。

---

## 一、机器人框架 / 协议端 / 应用层

### 表 1：协议端与会话框架

| 名称 | 开源 (Star 约数) | 支持平台 | 语音 TTS/STT | 图片理解 | 长期记忆 | 桌宠 / Live2D | 跨设备 | 来源 URL |
|---|---|---|---|---|---|---|---|---|
| **NapCatQQ** | 是（约 11k） | QQ（NTQQ，OneBot 11） | 自身不含；靠上层框架 | 自身不含；靠上层 | 无 | 无 | 服务端进程，任意设备可连 | [README](https://raw.githubusercontent.com/NapNeko/NapCatQQ/main/README.md) · [shields 11k](https://img.shields.io/github/stars/NapNeko/NapCatQQ.json) |
| **LLOneBot**（现名 LLBot / Lucky Lillia Bot） | 是（约 3.7k） | QQ（NTQQ；OneBot 11 / Satori / Milky） | 无（协议端） | 无 | 无 | 无 | 同左 | [README](https://raw.githubusercontent.com/LLOneBot/LLOneBot/main/README.md) · [shields 3.7k](https://img.shields.io/github/stars/LLOneBot/LLOneBot.json) |
| **Lagrange.Core** | 是（约 3.0k） | QQ（NTQQ 协议，纯 C#） | 无 | 无 | 无 | 无 | 同左 | [README](https://raw.githubusercontent.com/LagrangeDev/Lagrange.Core/master/README.md) · [API 2992★](https://api.github.com/repos/LagrangeDev/Lagrange.Core) |
| **go-cqhttp** | 是（约 11k，AGPL-3.0） | QQ（OneBot 11，Mirai/MiraiGo 系） | CQ 码含 `[CQ:record]` `[CQ:tts]`（消息层，非 AI 语音） | CQ 码含 `[CQ:image]`；有 `.ocr_image` 扩展 API | 无 | 无 | 同左 | [README](https://raw.githubusercontent.com/Mrs4s/go-cqhttp/master/README.md) · [shields 11k](https://img.shields.io/github/stars/Mrs4s/go-cqhttp.json) |
| **NoneBot2** | 是（约 7.7k，MIT） | OneBot(QQ)、QQ 频道、Telegram、钉钉、飞书等 | 无内置，靠插件 | 无内置，靠插件 | 无内置，靠插件 | 无 | 服务端 | [ecosyste.ms 7738★](https://repos.ecosyste.ms/api/v1/hosts/GitHub/repositories/nonebot%2Fnonebot2) · [shields 7.7k](https://img.shields.io/github/stars/nonebot/nonebot2.json) |
| **Koishi** | 是（约 6.3k，MIT） | OneBot(QQ)、Telegram、Discord、飞书、Matrix、LINE、邮件等 | 无内置，靠插件 | 无内置，靠插件 | 无内置，靠插件 | 无 | 服务端 + Web 控制台 | [ecosyste.ms 6244★](https://repos.ecosyste.ms/api/v1/hosts/GitHub/repositories/koishijs%2Fkoishi) · [shields 6.3k](https://img.shields.io/github/stars/koishijs/koishi.json) |
| **ZeroBot** | 是（约 395，GPL-3.0） | OneBot（QQ）；Go 框架 | 无内置 | 无内置 | 无内置 | 无 | 服务端 | [ecosyste.ms 395★](https://repos.ecosyste.ms/api/v1/hosts/GitHub/repositories/wdvxdr1123%2FZeroBot) · [shields 395](https://img.shields.io/github/stars/wdvxdr1123/ZeroBot.json) |
| **OneBot 11 协议** | 开放标准（botuniverse/onebot-11） | 协议层，被上述各端实现 | 定义 `record`(语音) 消息段 | 定义 `image` 消息段 | — | — | — | [go-cqhttp README 内引用](https://github.com/botuniverse/onebot-11) |

**注：go-cqhttp 停更状态已查证。** README 明确写：
> "由于 QQ 官方针对协议库的围追堵截, 不断更新加密方案, **我们已无力继续维护此项目**. 建议 Bot 开发者尽快迁移至无头 NTQQ 项目"

仓库本身 `archived` 字段为 `false`（未官方归档），但维护已中止，官方引导迁移。来源：[README](https://raw.githubusercontent.com/Mrs4s/go-cqhttp/master/README.md)、[API](https://api.github.com/repos/Mrs4s/go-cqhttp)（`"archived":false`）。

### 表 2：LLM 机器人应用层（真正的"对话+语音+记忆"发生地）

| 名称 | 开源 (Star 约数) | 支持平台 | 语音 TTS/STT | 图片理解 | 长期记忆 | 桌宠 / Live2D | 跨设备 | 来源 URL |
|---|---|---|---|---|---|---|---|---|
| **AstrBot** | 是（约 42k，AGPL-3.0） | QQ、企业微信、飞书、钉钉、微信公众号、Telegram、Slack、Discord、LINE、Satori、KOOK、Misskey、Mattermost | **TTS 多后端**（OpenAI TTS、Gemini TTS、GPT-SoVITS、FishAudio、Edge TTS、阿里百炼、Azure、MiniMax、小米 MiMo、火山）；**STT**（OpenAI Whisper、SenseVoice、MiMo Omni） | 是（Multimodal） | 是（Auto Context Compression；RAG/知识库；插件生态） | 官方本体**无**；有社区插件 [astrbot_plugin_self_open_llm_vtuber](https://github.com/murphys7017/astrbot_plugin_self_open_llm_vtuber)（约 10★）与 [astrbot-live2d-desktop](https://github.com/lxfight/astrbot-live2d-desktop)（约 25★） | 服务端 + WebUI + 官方桌面版 AstrBot-desktop | [README](https://raw.githubusercontent.com/AstrBotDevs/AstrBot/master/README.md) · [shields 42k](https://img.shields.io/github/stars/AstrBotDevs/AstrBot.json) |
| **LangBot**（原 QChatGPT） | 是（约 18k，Apache-2.0） | Discord、Telegram、Slack、LINE、QQ（个人+官方 API）、微信（个人+公众号）、企业微信、飞书、钉钉、KOOK、Satori、Matrix | 多模态支持；README 未列具体 TTS/STT 后端清单 → **具体语音能力未查证** | 是（multi-modal） | 是（内置 RAG 知识库） | 无 | Web 管理面板 + 云版 + Docker | [README](https://raw.githubusercontent.com/RockChinQ/QChatGPT/master/README.md) · [shields 18k](https://img.shields.io/github/stars/langbot-app/LangBot.json) |
| **QChatGPT** | 是（约 18k） | 同上 | 同上 | 同上 | 同上 | 无 | 同上 | 仓库已指向 LangBot；ecosyste.ms 记录 `previous_names` 含 `rockchinq/qchatgpt` → [ecosyste.ms](https://repos.ecosyste.ms/api/v1/hosts/GitHub/repositories/langbot-app%2FLangBot) |
| **CowAgent**（原 **chatgpt-on-wechat**） | 是（约 47k，MIT） | Web、微信、飞书、钉钉、企业微信、QQ、公众号、Telegram、Slack | 是（多渠道表格中 Telegram/WeChat/飞书/钉钉/企微标注 Voice ✅；ASR/TTS 走模型供应商路由） | 是（Vision 列，多供应商 ✅） | 是（三层：上下文→日志→MEMORY.md + Deep Dream 蒸馏 + 向量/关键词混合检索） | 无（有桌面客户端 CowAgent Desktop，非形象桌宠） | Web 控制台 + 桌面客户端 + 多 IM | [README](https://raw.githubusercontent.com/zhayujie/chatgpt-on-wechat/master/README.md) · [shields 47k](https://img.shields.io/github/stars/zhayujie/CowAgent.json) |
| **MaiBot（麦麦 MaiSaka）** | 是（约 6.2k，GPL-3.0） | QQ（社区群聊为主，依赖 NapCat） | **未查证**（README 未列语音） | **未查证** | 是（"基于心理学人格理论不断积累对你的了解"） | 官方本体无；同组织有 [MaiM-desktop-pet](https://github.com/MaiM-with-u/MaiM-desktop-pet)（约 30★） | 服务端 + WebUI + 一键启动器（Win/Mac） | [README](https://raw.githubusercontent.com/MaiM-with-u/MaiBot/main/README.md) · [shields 6.2k](https://img.shields.io/github/stars/Mai-with-u/MaiBot.json) |
| **chatgpt-on-wechat** | 已更名 CowAgent，见上行 | — | — | — | — | — | — | [README 内 "Project Renaming Notice"](https://raw.githubusercontent.com/zhayujie/chatgpt-on-wechat/master/README.md) |

**关键限定**：表 1/表 2 中 **没有任何一个项目把"Live2D/3D 桌宠形象"作为官方一等公民能力**。所有形象能力都出现在表 3 的伴侣类项目，或表 2 的**第三方插件**里。

---

## 二、AI 桌面伴侣 / 数字人

| 名称 | 开源 (Star 约数) | 形象 | 语音 | 长期记忆 | 即时通讯打通 (QQ/微信) | 跨设备 | 来源 URL |
|---|---|---|---|---|---|---|---|
| **AIRI**（moeru-ai） | 是（约 50k，MIT） | **Live2D + VRM 双支持**（眨眼/视线跟随/待机动画） | 是：客户端 STT、用户说话检测(VAD)、多供应商 TTS（ElevenLabs / Azure / OpenAI 兼容 / 阿里百炼 / 本地 Kokoro） | **部分**：浏览器内数据库（DuckDB WASM / pglite）已 x；"Memory Alaya" 仍 WIP（未勾选） | **Discord ✅ / Telegram ✅**；**QQ、微信：README 进度表未列出（未查证到支持）**。README 顶栏的 QQ/微信链接是**社区群**，不是机器人接入 | Web / macOS / Windows / 移动端(PWA，Capacitor) | [README](https://raw.githubusercontent.com/moeru-ai/airi/main/README.md) · [ecosyste.ms 50220★](https://repos.ecosyste.ms/api/v1/hosts/GitHub/repositories/moeru-ai%2Fairi) |
| **Open-LLM-VTuber** | 是（约 14k） | **Live2D**，桌面客户端支持**透明背景桌宠模式 + 全局置顶 + 鼠标穿透** | 是：语音打断（无需耳机）、ASR（sherpa-onnx / FunASR / Faster-Whisper / Whisper.cpp / Groq Whisper / Azure）、TTS（sherpa-onnx / MeloTTS / GPT-SoVITS / CosyVoice / Edge TTS / Fish Audio / Azure 等） | **明确写着"长期记忆功能暂时下线（即将回归）"**，仅聊天记录持久化 | **无**（本地/网页应用，不接 IM） | Windows / macOS / Linux；web + 桌面客户端；可服务端-客户端分离（需 https 反代才能用手机麦克风） | [README.CN](https://raw.githubusercontent.com/Open-LLM-VTuber/Open-LLM-VTuber/main/README.CN.md) · [ecosyste.ms 14059★](https://repos.ecosyste.ms/api/v1/hosts/GitHub/repositories/Open-LLM-VTuber%2FOpen-LLM-VTuber) |
| **SillyTavern** | 是（约 34k，AGPL-3.0） | 无原生形象（LLM 前端；靠扩展） | 靠浏览器/扩展，非核心 | 是（角色卡 + 世界书 + 向量化扩展） | **无** | Web 前端（本地/服务器） | [ecosyste.ms 34262★](https://repos.ecosyste.ms/api/v1/hosts/GitHub/repositories/SillyTavern%2FSillyTavern) · [shields 34k](https://img.shields.io/github/stars/SillyTavern/SillyTavern.json) |
| **super-agent-party**（SAP） | 是（约 2.7k，AGPLv3 + 商业双授权） | **VRM 3D 桌宠 + Live2D 扩展（sap-live2d）+ THA 2D 形象 + 可联动 VTube Studio** | 是：语音交互 + **对话打断** + 实时语音合成 + 多语音（角色卡分音色） | 是：README 明确 "支持长期记忆"（角色扮演行）；另有工作区记忆 `#<text>` | **是：QQ、微信、飞书、钉钉、Telegram、Discord、Slack 一键部署**（QQ 走官方机器人接口） | Windows/macOS/Linux 桌面版、Web、Docker、`.AppImage`、Docker+轻客户端 | [README](https://raw.githubusercontent.com/heshengtao/super-agent-party/main/README.md) · [README_ZH](https://raw.githubusercontent.com/heshengtao/super-agent-party/main/README_ZH.md) · [shields 2.7k](https://img.shields.io/github/stars/heshengtao/super-agent-party.json) |
| **Neuro-sama**（Vedal987） | **否，闭源** | VTuber 形象（Live2D，第三方直播画面） | 是（直播语音互动） | **未查证** | 无（Twitch 直播形态） | — | 官方仅开放**游戏接入 SDK**：[VedalAI/neuro-game-sdk](https://raw.githubusercontent.com/VedalAI/neuro-game-sdk/main/README.md)（WebSocket，Unity/Godot 官方 SDK + 13 个社区 SDK；已接入 Slay the Spire 2、Inscryption、Hollow Knight、Cyberpunk 2077、Pokémon Platinum 等） |
| **amica** | 是（约 1.6k） | VRM / WebXR | 有（VRM 数字人常用栈）→ 细节**未查证** | **未查证** | **无** | Web | [shields 1.6k](https://img.shields.io/github/stars/semperai/amica.json)（经 AIRI README 的 Similar Projects 引出） |
| **elizaOS/eliza** | 是（约 20k） | 无（Agent 框架） | 靠插件 | 有（Agent memory） | 靠插件（Discord/Twitter 等） | 服务端 | [shields 20k](https://img.shields.io/github/stars/elizaOS/eliza.json) |
| **kimjammer/Neuro** | 是（约 2.1k） | 有（Neuro 复刻，7 天完成） | 有 | **未查证** | **无** | 桌面 | [shields 2.1k](https://img.shields.io/github/stars/kimjammer/Neuro.json) |

---

## 三、"桌宠 + QQ 聊天打通"到底有多少人在做？

**结论：不是空白，但极其稀疏 —— 活跃且有量的只有 1 个主项目 + 2 个低星桥接插件。**

### 证据 A（强）：super-agent-party —— 目前查到的唯一"四件齐全"的活跃项目

README 同时声明：VRM 3D 桌宠 / THA Live2D 风格 / VTS 联动 + 语音交互与打断 + **长期记忆** + **QQ、微信等 IM 一键部署**。
- 约 **2.7k star**，最近提交时间为 shields.io 显示的 "last saturday"（即 2026-10 上旬，**活跃**）。
- 来源：[README](https://raw.githubusercontent.com/heshengtao/super-agent-party/main/README.md)、[last-commit](https://img.shields.io/github/last-commit/heshengtao/super-agent-party.json)

### 证据 B（中）：AstrBot 生态里的两个桌宠桥接插件

AstrBot 本体天然支持 QQ（官方适配器），因此"装一个插件"就能得到"QQ 对话 + Live2D 桌宠"：
1. **astrbot_plugin_self_open_llm_vtuber**（约 **10★**）— 把 Open-LLM-VTuber 适配成 AstrBot 插件，提供 Live2D 渲染 + 语音识别/播放 + **语音打断** + 表情动作联动，前端可桌面可 Web。明确写着"必须放在 AstrBot 插件目录内运行"。
   来源：[README](https://raw.githubusercontent.com/murphys7017/astrbot_plugin_self_open_llm_vtuber/main/README.md)、[shields 10](https://img.shields.io/github/stars/murphys7017/astrbot_plugin_self_open_llm_vtuber.json)
2. **astrbot-live2d-desktop**（约 **25★**）— Electron+Vue 桌面端 + AstrBot WebSocket 适配器，把 AstrBot 消息链转成 `perform.show` 序列（文本/媒体/动作/表情）。
   来源：[文档站](https://lxfight.github.io/astrbot-live2d-desktop/)、[shields 25](https://img.shields.io/github/stars/lxfight/astrbot-live2d-desktop.json)

### 证据 C（弱）：同组织试水项目

**MaiM-desktop-pet**（MaiM-with-u 组织，即 MaiBot 同门）—— 仓库存在，约 **30★**，`main` 分支 README 404（未见完整说明），形态细节**未查证**。
来源：[shields 30](https://img.shields.io/github/stars/Mai-with-u/MaiM-desktop-pet.json)、[仓库页](https://github.com/MaiM-with-u/MaiM-desktop-pet)

### 证据 D（弱）：GitHub 全站搜索几乎为空

用 GitHub Search API 搜 `desktop pet qq bot`（按 star 排序），**全站命中 `total_count: 1`**：`whommm/zero-pet`（1★，Tauri + Web，描述为"零的桌宠 · Live2D Desktop Pet（连接 QQ Bot Gateway）"，2026-08 创建后基本停更）。
来源：[GitHub Search API](https://api.github.com/search/repositories?q=desktop+pet+qq+bot&sort=stars&order=desc&per_page=20)

> ⚠️ 该搜索只覆盖仓库名/描述/README 的英文关键词命中，**不能证明"全站只有 1 个"**，只能证明"英文关键词层面极度稀疏"。

---

## 四、共性能力

1. **QQ 生态高度集中在 OneBot 11 协议上，且已整体迁移到 NTQQ 无头端。** NapCatQQ(约11k)、Lagrange.Core(约3.0k)、LLOneBot(约3.7k) 都是 NTQQ 系；老牌 go-cqhttp(约11k) 因协议加密对抗主动中止维护并引导迁移。来源：[go-cqhttp README](https://raw.githubusercontent.com/Mrs4s/go-cqhttp/master/README.md)。
2. **"多平台 IM 接入"是应用层框架的标配**，且普遍已包含 QQ + 微信：AstrBot（19 个平台）、LangBot、CowAgent、super-agent-party 均覆盖。
3. **语音能力（TTS/STT）在"伴侣类"项目里已普及**：Open-LLM-VTuber、AIRI、super-agent-party 都做到了 TTS + STT + **打断（barge-in）**；AstrBot 提供了极长的 TTS/STT Provider 清单。
4. **形象层已标准化为 Live2D + VRM 两条路线**：AIRI（双支持）、Open-LLM-VTuber（Live2D）、super-agent-party（VRM + Live2D 扩展 + VTS）。
5. **记忆正在从"聊天记录"升级为"分层记忆系统"**：CowAgent 的三层记忆 + Deep Dream 蒸馏、MaiBot 的人格化长期积累、AstrBot 的上下文自动压缩 + 知识库、super-agent-party 的长期记忆。
6. **"透明置顶 + 鼠标穿透"是桌宠形态的既定交互范式**：Open-LLM-VTuber 的"宠物模式"、super-agent-party 的透明推流到 OBS，都是同一套做法。

## 五、普遍缺失

1. **"形象"与"QQ/微信接入"在同一项目里极少同时是一等公民。** 有形象的（AIRI / Open-LLM-VTuber / SillyTavern / amica）基本**不接 QQ/微信**；接 QQ/微信的（AstrBot / LangBot / CowAgent / MaiBot / NapCat）**本体都没有形象**，只能靠第三方低星插件补齐。**唯一例外是 super-agent-party。**
2. **Open-LLM-VTuber 的长期记忆当前是缺位状态**，README 原文："虽然长期记忆功能暂时下线（即将回归）"—— 它是外形+语音最强的开源项目之一，但记忆这条腿现在瘸着。
3. **AIRI 的记忆仍在 WIP**：`Memory` 项下只勾了"纯浏览器内数据库"，"Memory Alaya" 未勾选。
4. **"纯本地 LLM 推理"几乎无人做到端到端**：AIRI 的 "Pure in-browser local (WebGPU) inference" 仍未勾选；super-agent-party README 明确"所有模型可选，也可全部使用云服务商接口"。本地化目前主要落在**记忆与数据存储**，而非推理。
5. **语音 + IM 打通是双重缺口**：CowAgent 的 Channels 表中 **QQ 行的 Voice 列为空**（Telegram/微信/飞书/钉钉/企微有 Voice ✅），即"在 QQ 里发语音、让 AI 用语音回"并非当前默认能力。来源：[CowAgent README Channels 表](https://raw.githubusercontent.com/zhayujie/chatgpt-on-wechat/master/README.md)。
6. **代码质量/维护度参差**：ecosyste.ms 记录 Koishi 的 OpenSSF Scorecard "Maintained" 仅 6/10（近 90 天 3 commits）；NoneBot2 有 11 项已知漏洞告警。来源：[Koishi ecosyste.ms](https://repos.ecosyste.ms/api/v1/hosts/GitHub/repositories/koishijs%2Fkoishi)、[NoneBot2 ecosyste.ms](https://repos.ecosyste.ms/api/v1/hosts/GitHub/repositories/nonebot%2Fnonebot2)。
7. **"手机-电脑跨设备"普遍是"服务端 + Web 前端"的妥协形态**，而非真正的状态同步：Open-LLM-VTuber 需自建 https 反代才能在手机上用麦克风；AIRI 有 Capacitor 移动端 + 无线连接服务端（需 root 启动 tamagotchi）。

---

## 六、一句话结论（只用可查证证据）

> 我们的组合 **"桌宠形象 + Live2D/3D + 语音 + QQ/微信打通 + 本地记忆"** 在市面上**并非首创，但进入了极稀疏地带**：唯一查到把这几条同时做齐且仍在活跃的项目是 **super-agent-party（约 2.7k★，AGPLv3）**；此外只有两个 **10★ / 25★ 级别的 AstrBot 桥接插件**在做"QQ 对话 + Live2D 桌宠"这件事；形象最强的 Open-LLM-VTuber（约 14k★）不接 IM 且**长期记忆当前下线**；IM 最强的 AstrBot（约 42k★）/ LangBot（约 18k★）/ CowAgent（约 47k★）本体都没有形象。**因此我们的位置是"用现有最优组件重新组合的整合者"，差异化必须落在产品整合度、开箱体验与本地化深度上，而不是"我们做了别人没做过的事"这一叙事上。**

---

## 七、"未查证 / 存疑"清单

| # | 事项 | 状态 |
|---|---|---|
| 1 | **MaiBot 的语音(TTS/STT)与图片理解能力** | **未查证** — README/README_CN 均未提及 |
| 2 | **MaiM-desktop-pet 的具体形态**（是否含语音、记忆） | **未查证** — `main` 分支 README 404 |
| 3 | **AIRI 是否支持 QQ / 微信机器人接入** | **未查证** — 进度表列出 Discord、Telegram，未见 QQ/微信；README 顶栏 QQ/微信为社区群链接 |
| 4 | **Neuro-sama 的长期记忆机制与技术栈细节** | **未查证**（闭源，官方仅公开游戏接入 SDK） |
| 5 | **amica 的语音与记忆细节** | **未查证** — 未读其 README，仅取 star 数 |
| 6 | **kimjammer/Neuro 的记忆与语音细节** | **未查证** — 仅取 star 数 |
| 7 | **LangBot 具体支持哪些 TTS/STT 后端** | **未查证** — README 只写 "multi-modal"，未列清单 |
| 8 | **是否存在其他"桌宠+QQ"项目** | **可能存疑** — GitHub Search `desktop pet qq bot` 命中 total_count=1，但该查询仅覆盖英文关键词，**不能作为穷尽性证明** |
| 9 | **Neuro-sama 直播订阅数 / Twitch 排名等影响力数据** | **未查证** — 搜索到二手报道（Daily Dot 等）但未逐条核实原始数据 |
| 10 | **所有 Star 数的精确值** | **存疑** — GitHub 官方 API 当日限流（403），数值取自 shields.io 与 ecosyste.ms 约数；ecosyste.ms 部分记录同步时间较早（如 NapCat 无记录、MaiBot/QChatGPT 无记录） |
| 11 | **"国内 AI 女友 / 数字人"商业产品**（如各类 App） | **未查证** — 本次调研未覆盖闭源商业产品线 |

---

### 附：本次使用的数据源清单

- GitHub REST API：`https://api.github.com/repos/{owner}/{repo}`（Lagrange.Core、NapCatQQ、go-cqhttp 成功；其余被限流）
- GitHub Search API：`https://api.github.com/search/repositories?q=...`
- shields.io 端点：`https://img.shields.io/github/stars/{owner}/{repo}.json`、`.../last-commit/...json`
- ecosyste.ms：`https://repos.ecosyste.ms/api/v1/hosts/GitHub/repositories/{owner}%2F{repo}`
- 各项目官方 README：`https://raw.githubusercontent.com/{owner}/{repo}/{branch}/README*.md`
