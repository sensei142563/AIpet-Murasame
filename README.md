# AIpet - 丛雨AI桌宠

# 本项目仅供学习交流使用，各角色立绘/模型/语音版权归其原始权利人所有（详见下方「特别感谢」）
# 本项目严格禁止用于任何商业用途

## 📖 项目简介

一个基于 AI 的多角色桌面宠物引擎（一个引擎 + N 个角色包），随附丛雨（《千恋＊万花》）与诺瓦（《星空列车与白的旅行》）两个示范角色。本项目参考了原项目 [LemonQu-GIT/MurasamePet](https://github.com/LemonQu-GIT/MurasamePet?tab=readme-ov-file)，进行部分重写和新加功能，并根据 GPL-3.0 许可证要求进行开源。

### 🙏 特别感谢

- **B站 UP 主「唐龙丁真孙笑川」**：[https://space.bilibili.com/696040999](https://space.bilibili.com/696040999) — 原始项目来源
- **原项目地址**：
  - GitHub：[LemonQu-GIT/MurasamePet](https://github.com/LemonQu-GIT/MurasamePet)
  - ModelScope：[Murasame](https://modelscope.cn/models/LemonQu/Murasame) / [Murasame_SoVITS](https://modelscope.cn/models/LemonQu/Murasame_SoVITS)
- **@吴基岩BedrockWu** — 设备与训练支持（device & training support）

角色素材来源：
- **丛雨 Live2D 模型**：[B站视频](https://www.bilibili.com/video/BV1mb4y1i7xu/)
- **诺瓦 Live2D 模型**：[B站视频](https://www.bilibili.com/video/BV14TbYzZE4N/)
- **丛雨中文语音包 & 全局兜底音色**：蔚蓝档案「爱理」语音，来源 [gamekee 蔚蓝档案 Wiki](https://www.gamekee.com/ba/)
- **丛雨日语语音**：柚子社《千恋＊万花》
- **诺瓦日语语音**：诺瓦示例语音，来源 [しらたまこ 星白公式](https://shiratamaco.com/hoshishiro/)
- **诺瓦中文语音**：蔚蓝档案「枫香」语音，来源 [gamekee 蔚蓝档案 Wiki](https://www.gamekee.com/ba/)

**技术栈**：
- 短文本语音合成：[GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS)（日语，音色克隆）
- 长文本语音合成：[F5-TTS](https://github.com/SWivid/F5-TTS)（中文，流式逐句）
- 语音识别：[faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- 对话模型：Qwen（云端）/ DeepSeek（云端）/ 本地 Ollama
- 视觉识别：Qwen-VL / qwen3-vl-plus（屏幕、摄像头）
- 人脸识别：ArcFace ONNX（insightface）
- GUI：PyQt5 + Live2D（live2d-py）

---

## 🐾 多桌宠架构新手教程

> 一个引擎 + N 个角色包。跟着本教程做，不需要懂代码。

### 0. 一分钟看懂角色包

- 每个桌宠 = `pets/<id>/` 一个文件夹（叫「角色包」），`<id>` 是英文/数字 ID
- 角色包里放：`pet.json`（配置文件）、`prompt.txt`（短句人设）、`longtext_prompt.txt`（长文本/QQ 人设）、头像图片、`live2d/`（Live2D 模型）、`voices/`（语音）、`biaoqingbao/`（表情包）、`memory/`（记忆，自动生成不用管）
- 角色清单 = 自动扫描 `pets/` 下所有含 `pet.json` 的文件夹（`_` 开头跳过）+ `pet_list.json` 注册表：放进 `pets/` 的角色包本地立即生效；`pet_list.json` 同时是**分发清单**——只有登记在册的角色才会随仓库/绿色版分发（PCL「＋ 添加新桌宠」会自动登记）

仓库 / 绿色版随附 2 个示范角色（教程照做即可套用到任何新角色）：

| ID | 角色 | 来源 | 显示方式 |
|---|---|---|---|
| murasame | 丛雨 | 千恋＊万花 | 2D 立绘默认，Live2D 可选 |
| noir | 诺瓦 | 星空列车与白的旅行 | 纯 Live2D |

### 1. 如何新增一个桌宠角色（推荐：纯 Live2D，3 分钟）

**第 1 步：创建角色包**
- 方式 A（推荐）：打开 PCL → 顶栏「桌宠」→「＋ 添加新桌宠（从模板创建）」→ 输入 ID（英文/数字）和显示名字
- 方式 B：手动把 `pets/_template/` 整个文件夹复制一份，改名为你的 ID（本地立即生效；想随包分发再登记进 `pet_list.json`）

**第 2 步：改 pet.json**（用记事本打开 `pets/<你的ID>/pet.json`）
- `name`、`display_name`：角色名字
- `avatar`：头像图片文件名（把图片放进角色包根目录，例如放 `头像.png` 就填 `"头像.png"`）
- `model.default`：**纯 Live2D 角色填 `"live2d"`**（新手必填这个；只有做了 2D 图层立绘才填 `"2d"`）
- 其余字段照抄现有角色（如 `pets/noir/pet.json`）即可

**第 3 步：放入 Live2D 模型**
1. 把模型的这些文件复制到 `pets/<你的ID>/live2d/`：
   - 必放：`xxx.model3.json`、`xxx.moc3`、贴图 `texture_00.png`（通常在 `xxx.2048/` 或 `xxx.4096/` 这类文件夹里，**整个文件夹一起复制**）
   - 可选：`xxx.physics3.json`（物理）、`xxx.cdi3.json`（显示信息）
2. 表情：把 `.exp3.json` 文件放进 `pets/<你的ID>/live2d/exp/`（没有就跳过）
3. 动作：把 `.motion3.json` 放进 `pets/<你的ID>/live2d/motion/`（需 model3.json 引用，没有就跳过）
4. ⚠ **如果 live2d/ 里多于一个 `.model3.json`**（如备份文件），在 pet.json 的 `model` 里加一行钉死正确的：
   `"live2d_model_json": "live2d/你的模型.model3.json"`

**第 4 步：写人设**
- `pets/<你的ID>/prompt.txt`：短句模式用（照抄 `pets/murasame/prompt.txt` 的七段式：你是谁/故事背景/情感基调/系统与屏幕信息/摄像信息/输出格式/对话示例）
- `pets/<你的ID>/longtext_prompt.txt`：长文本/QQ 用（照抄 `pets/murasame/longtext_prompt.txt` 的【角色背景】【对话要求】【禁止事项】格式改内容）
- `pets/<你的ID>/pet.json` 的 `translate_rules`：翻译规则（丛雨=古日语+「本座→吾輩」等规则；其他角色=自然口语），照抄现有角色即可
- 也可以在 PCL 顶栏「提示词」页里直接编辑保存

**第 5 步：完成**
重开 PCL（或直接点新卡片）→ 点卡片设为活动 →「启动 AIpet」→ 完事。

> 进阶：2D 立绘角色需要 `fgimages/` 图层素材 + `portrait_prompts.json` 映射（参考 murasame 角色包），复杂，新手不建议。

### 2. 如何调试显示（模型大小/位置/文字/窗口）

**图形化（推荐新手）**：PCL → 设置 → 底部「🎭 Live2D 显示调参」→ 下拉选角色 → 拖滑块 → **点「保存到角色」**。桌宠运行中保存会立即生效；没运行则下次启动生效。

**热键（进阶，桌宠运行中，先点一下模型获得键盘焦点，按 `F1` 查看帮助）**：

| 按键 | 功能 |
|---|---|
| **`F1`** | **开启/关闭调参模式**（调参前必须先按；打字时热键自动失效不干扰输入） |
| `+` / `-` | 模型缩放（0.1~4.0） |
| 方向键 | 模型平移（限窗口范围内，不会移丢） |
| `Shift`+方向键 | 文本框位置（仅 Live2D 模式生效，2D 不受影响） |
| `F7` / `F8` | 窗口宽高比 |
| `F2` / `F3` | 窗口高度占屏比（消除上下空白画布） |
| `F4` | 重置模型位置 |
| `,` `.` 或 `F10` `F11` | 字号 |
| `F9` | 画布参考线（边界+中线） |
| `F5` | 保存到当前角色 pet.json（永久生效） |
| `F6` | 控制台打印当前值 |
| `Esc` | 退出输入模式 |

**推荐的调试流程**：`F1` 开启调参 → `F9` 开参考线 → 方向键把模型放红框中间 → `+`/`-` 调大小 → `F2`/`F3` 缩窗口高度消掉上下空白 → `Shift`+方向键 把对话框放到模型旁边 → `,`/`.` 调字号 → 满意后 `F5` 保存 → 再按 `F9` 关参考线、`F1` 关闭调参。调乱了按 `F4` 重来。

**摸头/点击区域不准？** 编辑 pet.json 的 `interaction` 块（相对窗口高度的比例）：
- `head_top` / `head_bottom`：头部区域（摸头）
- `talk_top` / `talk_bottom`：点击进入输入模式的区域
- `edge_margin_x`：左右边缘不响应的留白

**表情/动作跟着情绪走？** 编辑 pet.json 的 `model` 块：
- `emotions`：`"情绪" → ["表情文件名.exp3.json", ...]`（文件名与 live2d/exp/ 里的一致）
- `motions`：`"情绪" → ["动作组名", 序号]`（组名见 model3.json 的 Motions）
- `default_expression`：默认表情文件名（如 noir 的 `"white.exp3.json"`）
短/长文本回复里的【情绪】标签会自动切换对应表情+动作，播完恢复默认。

### 2.5 🎭 Live2D 表情与动作配置（对应 2D 的换装）

Live2D 模型没有「衣服」概念——2D 换装对应的表现是**表情（exp3）+ 动作（motion3）**：

- **表情**（`live2d/exp/*.exp3.json`）：眼睛形状/脸红/眼泪/嘴型等，瞬时切换
- **动作**（`live2d/motion/*.motion3.json`）：点头/挥手/蹦跳等一段动画，播放完自动恢复默认表情

配置都在 pet.json 的 `model` 块：

```json
"emotions": { "生气": ["生气.exp3.json"] },
"motions":  { "生气": ["motion05.motion3.json"] },
"default_expression": "exp1.exp3.json"
```

- `emotions`：情绪 → 表情文件列表（回复中带【情绪】标签时切换）
- `motions`：情绪 → 动作文件名（同情绪标签触发，播完自动回默认表情）
- `default_expression`：默认表情文件名

**想知道每个文件是什么表情/动作？** 运行调试器逐个看效果：

```bash
python debug_live2d.py --pet noir      # 或 murasame / arona / hiyori
```

左画面实时预览，右侧点表情/动作按钮、拖参数滑块；确认每个文件的含义后填进 pet.json 即可。

### 3. 如何放入 / 更换语音

> 给新角色加语音和给现有角色**换声音**是同一套操作：替换参考音频文件即可。

**短语音**（桌面短句模式，GPT-SoVITS 参考克隆）：
1. 目录结构：`pets/<你的ID>/voices/short/<情绪>/`，`<情绪>` = pet.json 里 `voices.short_emotions` 列的名字（默认：高兴/害羞/惊讶/平静/生气/着急）
2. 每个情绪文件夹里放 **2 个文件**：
   - `ref.wav`（或 `ref.mp3`）—— 该情绪的一句话录音（**一句就够**，丛雨每个情绪也只有一句）
   - `asr.txt` —— 新建文本文件，内容 = 这句话的**文字**（UTF-8 一行，必须和录音内容一字不差）
3. ⚠️ **参考音频必须在 3~10 秒之间**（GPT-SoVITS 硬性要求；太短会静默跳过不发声）
4. 重启桌宠生效。短文本对话时 AI 会按情绪挑选参考音，克隆出你的角色声线

**长语音**（长文本模式 + QQ，F5-TTS）：
1. 把一句话录音放成 `pets/<你的ID>/voices/long/long.wav`（中文，建议 3~5 秒、无噪音）
2. 编辑 pet.json 的 `voices` 块：
   - `"long_ref_audio": "voices/long/long.wav"`
   - `"long_ref_text": "这句话的文字"`
3. 不放也没关系——自动用全局兜底音色（`reference_voices/long_chinese/953244.wav`）

**表情包**（QQ）：图片扔进 `pets/<你的ID>/biaoqingbao/`，QQ 回复时随机发送。有图才发图。
⚠️ 只支持 **gif / png / jpg**——**avif 不能发送**（NapCat 富媒体不支持），手上有 avif 可用 ffmpeg 转成 gif。

### 4. PCL 启动器功能一览

- 左侧「模型列表」角色卡片：点卡片切换角色并预览（Live2D/2D），同时设为活动角色
- **QQ 跟随活动角色**：PCL 里选中谁，「启动 QQ AIpet」就用谁的人设 / 表情包 / 语音 / 记忆
- 顶栏导航：模型 / 设置 / 人脸 / 记忆 / 桌宠 / 提示词
- 「桌宠管理」页：设为活动 / 添加 / 删除 / 打开文件夹（**丛雨不可删除**）
- 进程互斥：同时最多一个 AI 桌宠 + 一个 QQ 桌宠（任意组合）
- 「设置」页底部「Live2D 显示调参」：滑块调整显示参数，点「保存到角色」写入 pet.json
- 「提示词」页：按角色查看/编辑短文本与长文本人设
- **「记忆」页**：角色下拉查看各角色记忆（条数/大小/时间）→ 点「查看」预览最近对话 → 单独清除/全清 → 一键备份该角色记忆 zip 到桌面 → 显示 QQ 离线补拉状态（可清空已处理消息 ID）
- **`debug_live2d.py`**：Live2D 表情/动作调试器（见第 2.5 节）

### 5. 常见问题（使用类）

| 症状 | 解决 |
|---|---|
| 新角色启动后空画布/没模型 | pet.json `model.default` 必须填 `"live2d"`；多个 model3.json 时加 `live2d_model_json` 钉死；确认 moc3 在 live2d/ 里 |
| 新角色没出现在 PCL | 角色包根目录必须有 `pet.json`；重开 PCL；文件夹名不能以 `_` 开头 |
| 文字特别大 / 位置不对 | 调 `live2d_font_scale`（字号）与 `interaction.text_offset_x/y`（文本框位置），见第 2 节 |
| 模型上下有空白 | `F2`/`F3` 调窗口高度，或调 `live2d_window_height_ratio` |
| 摸头没反应 / 点错位置 | 调 `interaction` 的 head/talk 区间 |
| 语音没生效 | asr.txt 要和录音同目录、文字与录音一致、情绪文件夹名和 pet.json 的 short_emotions 一致 |
| 语音不发声（无报错） | 参考音频时长必须在 **3~10 秒**之间，太短会被静默跳过 |
| QQ 不发图 | `biaoqingbao/` 文件夹里有 gif/png/jpg 才会发；avif 不支持 |
| 表情不切换 | `model.emotions` 里的文件名必须和 live2d/exp/ 里的文件完全一致（含 .json） |
| 角色之间串设定（诺瓦说"神社"） | 记忆已按角色分仓；若出现串味，清空对应角色 `pets/<id>/memory/` 后重启 |
| QQ 离线消息不补回 | 需至少启动过一次（有基线）；补拉覆盖大号+好友、窗口为上次启动前推 24 小时；首次运行只补最近 10 分钟 |

---

## 🆕 最新版本

**V1.12.1** — 隐私修复与文档完善

### V1.12.1 变更

- **🔒 隐私修复**：移除设置页示例 QQ 号与使用者名称默认值、启动脚本内硬编码的本机路径
- **🐛 PCL 桌宠列表修复**：绿色版 exe 内角色列表/提示词/Live2D 下拉为空、源码版多显示本地角色的问题已修复
- **📖 文档**：新增「绿色版 vs 开源版」下载使用指南；措辞更友好

**V1.12** — 开源发布（GPL-3.0）：仓库与绿色版随附「丛雨 + 诺瓦」两个示范角色

### V1.12 变更

- **📦 开源**：项目以 GPL-3.0 发布；公开仓库为全新单次提交，不含任何隐私数据（config / data / 人脸 / 记忆均已 .gitignore 且从未进入历史）
- **🐾 示范角色**：仓库/绿色版随附丛雨 + 诺瓦两个示范角色
- **🙏 致谢**：补充各角色模型与语音素材来源（见「特别感谢」）

**V1.11** — 多桌宠架构（一个引擎 + N 个角色包），详见上方「🐾 多桌宠架构新手教程」

### V1.11 新功能

- **🐾 多桌宠**：一个引擎 + N 个角色包，PCL 选角色即启动对应桌宠与 QQ（随仓库分发丛雨 / 诺瓦 2 个示范角色）
- **🎭 Live2D 按角色适配**：窗口比例/模型缩放/字号/摸头区域按角色配置；纯 Live2D 角色自动进入 Live2D；文字层点击穿透、对话文字常显
- **🎨 情绪 → 表情/动作**：回复中的【情绪】标签自动切换 Live2D 表情与动作（含 vtube.json 参数范围提取，修复眨眼/口型幅度）
- **🎛 双调参方式**：PCL 设置页图形化滑块（点保存生效）+ 桌宠热键（F1 帮助 / F5 保存 / F9 参考线）
- **📝 PCL 提示词编辑器**：按角色直接编辑短/长文本人设
- **🛡 丛雨保护与进程互斥**：丛雨不可删除；同时最多一个 AI 桌宠 + 一个 QQ 桌宠
- **💬 角色包脚手架**：noir 的表情包/短语音(6情绪)/长语音目录已建好，放文件即用（详见教程第 3 节）

**V1.10.2** — 立绘历史污染根治、数据路径统一

### V1.10.x 修复与增强

- **🎨 立绘历史污染根治**：`cloud_portrait` / `ollama_qwen3_portrait` 不再把完整立绘历史（含历史返回的图层 ID）塞进 prompt，改为**只提炼「上次基础人物 ID」**作衣服连贯参考，并加硬约束「严禁使用历史之外/其他服装的 ID」——彻底解决 AI 偶发跨服装返回 ID 后**滚雪球复读**（如 A 立绘反复输出 B 套 `1475`）导致的僵脸/崩溃
- **🛡 图层文件存在性兜底**：`tool/generate.py` 绘制前对每个图层 ID 检查文件是否存在，缺失则跳过+警告，全缺失返回空画布——未来任何 AI 越界都不会再崩溃
- **📁 数据路径统一（`tool/paths.py`）**：新增公共基准（exe 模式→exe 旁、源码→项目根），统一 `face_shibie/`、`config.json`、`data/qq_memory/` 路径——**根治 PCL 壳（exe）写入 `_internal/` 导致人脸识别不到主人**的问题
- **🔓 资源打包修复**：绿色版重新打包，移除 `_internal/` 内错误残留，桌面/QQ 双端稳定运行

### V1.8.0 新功能

- **📋 消息调度器**：离线消息按序补回 + 多人聊天串行不乱 + 私聊消息合并等待（1.5~5 秒随机）
- **🗂️ 记忆分仓**：大号私聊共享记忆；其他私聊/群聊按会话独立记忆仓（`data/qq_memory/`）
- **🎙 F5-TTS 自动启动**：单独启动 QQ AIpet 时自动拉起语音服务（9881）
- **🎭 表情包自主**：AI 根据语境决定发 0~2 个表情包（无需每次强发）
- **🧹 /clear 指令**：大号私聊发 `/clear` 可清空当前会话记忆
- **💾 PCL 记忆管理页**：可视化查看/清理各分仓记忆 + 共享记忆
- **🔧 设置面板增强**：新增"主人 QQ 号（共享记忆）"配置项，统一记忆轮数

**V1.6.0** — QQ 聊天接入（NapCat）、PCL 双启动按钮

### V1.6.0 新功能

- **💬 QQ 聊天**：通过 NapCat（OneBot11）接入 QQ，小号「丛雨」在私聊/群聊 @ 时用 AI 回复（复用长文本人设 + 共享记忆）
- **🖼️ 表情包**：AI 根据语境从 `biaoqingbao/` 选择 gif 表情随回复发出
- **🔘 PCL 双启动按钮**：启动器可分别启动「桌宠」和「QQ AIpet」，互不干扰，关闭时一键截断进程
- **🧠 共享记忆**：QQ 对话与桌宠共用 `long_history.json`（12 轮），同一个"丛雨"两个入口
- **🤖 长文本模型切换**：长文本对话可在 Qwen 与 DeepSeek 之间切换（`longtext_model`），默认 DeepSeek（更聪明）
- **👁 QQ 图片识别**：私聊发图 → 丛雨自动识别图片内容并回应（`qq_vision_enabled`，使用 qwen3-vl-plus）
- **📝 私聊切句**：QQ 私聊回复按标点逐句发送（模拟真人打字节奏），群聊保持一次性发送
- **▶️ 自动启动 NapCat**：点击「启动 QQ AIpet」自动检测并启动 NapCat（首次需扫码登录）
- **🎛 PCL 设置面板 QQ 配置**：图形化管理 QQ 开关/表情包/语音/图片识别/群聊

### V1.5.0 新功能

- **📝 长文本输出模式（核心）**：长按 **Alt 2秒** 切换。AI 流式输出 → 标点切句 → F5-TTS 中文语音逐句合成播放 → 打字机文字同步显示。输出内容更丰富、更有情感深度（不限定字数）。
- **🖥️ 屏幕识别 → 长文本**：长文本模式下定时截图识别。空闲时截图结果走长文本流式回复；输出中自动跳过不打断。
- **📷 摄像头识别 → 长文本**：长文本模式下摄像头+人脸识别同样接入长文本流式，输出中自动跳过。
- **🧠 优先级记忆机制**：识别（截图/摄像头/空闲）内容写入记忆带 `priority=high`，仅在**下一轮对话有高权重**强注入（system 级"最近的观察"）；该轮结束后自动降为 `low`，权重≈0。
- **🎭 Live2D 长文本文字修复**：长文本输出时文字层正确显示在 Live2D 模型上方（与短文本一致）。
- **⚡ ArcFace GPU 加速**：onnxruntime-gpu 安装到运行环境，人脸识别恢复 CUDA GPU 推理（不再回退三哈希）。

### 历史版本
- **V1.4.0** — ArcFace 人脸识别、对话人称自适应、PCL 导航页切换修复
- **V1.3.0** — 摄像头拍照识别（Ctrl 长按）、Live2D 切换（Shift 长按）
- **V1.2.x** — 屏幕识别、空闲检测、PCL 风格启动器

### 项目指路
- **安装教程（最新）**: [AIpet 多角色桌宠安装教程](https://www.bilibili.com/video/BV1Aybe6GEHP/?vd_source=c2cadbf819021ce34cdfc6948ac18d63)
- **演示视频（最新）**: [AIpet 多角色桌宠演示](https://www.bilibili.com/video/BV1Q1bY6QE5M/?vd_source=c2cadbf819021ce34cdfc6948ac18d63)
- **历史教程视频**:
  - [丛雨AI桌宠V1.2.0部署教程](https://www.bilibili.com/video/BV1F6ykBwEDu)
  - [丛雨AI桌宠V1.2.2部署教程](https://www.bilibili.com/video/BV1ghCMBjEKK)
  - [丛雨AI桌宠V1.3.0部署教程](https://www.bilibili.com/video/BV1iw2XBREpd)

---

## 📥 下载与使用：绿色版 vs 开源版

| | 绿色版（新手推荐） | 开源版（GitHub 源码） |
|---|---|---|
| 是什么 | 打包好的完整目录：启动器 EXE + 桌宠源码 + 语音模型，解压即用 | 完整源代码，环境自己装 |
| 去哪下 | 仓库 **Releases** 页下载（分卷压缩，合并解压，见下方说明） | 仓库首页 **Code → Download ZIP**，或 `git clone https://github.com/sensei142563/AIpet-Murasame.git` |
| 首次使用 | 解压 → 双击 `install.bat` → 填 `config.json` 的 API Key | 解压 → 双击 `install.bat` → 填 `config.json` 的 API Key |
| 日常使用 | 双击 `启动桌宠.bat`（桌宠）/ `启动QQ.bat`（QQ） | 同左，或 `python run_launcher.py` |
| 适合谁 | 想直接玩、不想折腾环境的人 | 想改代码、做新角色包、二次开发的人 |

两个版本功能完全一致，差别只在「环境是否已打包」。绿色版**不含你的 config.json**（API Key 隐私），首次运行会自动生成空白配置，自己填好即可。

---

## 🚀 快速开始

> 详细安装教程见视频：[AIpet 多角色桌宠安装教程](https://www.bilibili.com/video/BV1Aybe6GEHP/?vd_source=c2cadbf819021ce34cdfc6948ac18d63)

### 方式一：一键安装（推荐，Windows）

1. **下载项目文件**：Code > Download ZIP，解压后放到需要的位置（路径不要有特殊符号）。
2. **双击 `install.bat`**：自动完成以下所有步骤：
   - 检测 Python 版本（需 ≥ 3.10）
   - 创建项目本地虚拟环境 `runtime/venv`
   - 安装全部依赖（含 CPU 版 PyTorch，云端对话必需）
   - 自动生成 `config.json`（从 `config.example.json` 复制）
3. **编辑 `config.json`**：填入 API Key（见下方第 4 步）。
4. **双击 `启动桌宠.bat`** 开始使用；QQ 功能双击 `启动QQ.bat`。

> 之后日常使用只需双击 `启动桌宠.bat` 或 `启动QQ.bat`，无需每次重装。

> ⚠️ **绿色版首次启动**：为保护隐私，绿色版**不带你的 config.json**（含 API Key）。首次打开 PCL 会自动从 `config.example.json` 生成一份空白的 `config.json`（在绿色版目录内），请用记事本打开填入**你自己的** API Key 后再使用。`data/` 与 `face_shibie/`（人脸）同样会在绿色版目录内独立生成，与源码版各自独立，互不影响。

> 🐾 **绿色版随附角色**：丛雨 + 诺瓦 2 个示范角色；你自己放到 `pets/` 的角色包同样生效。

> 🗜️ **GitHub Releases 分卷下载说明**：
> 完整绿色版在 GitHub Releases 以**分卷压缩**发布（`.zip` + `.z01` + `.z02`，因单文件超 2GB 上限）。
> - **必须下载全部 3 个分卷**到同一文件夹（缺任何一个都无法解压）
> - 用 **WinRAR** 或 **7-Zip** 打开 `.zip` 分卷，会自动合并后续 `.z01/.z02` 解压
> - 解压后得到 `AIpet-Murasame/` 完整目录（含 F5-TTS 模型 + NapCat）
> - 也可选择网盘单文件版（一个 zip 解压即用，无需合并）

---

### 方式二：手动安装（高级）

#### 1. 下载项目文件
Code > Download ZIP，解压后放到需要的位置（路径不要有特殊符号）。

#### 2. 安装依赖
```bash
pip install -r requirements.txt
```

> 额外需要安装 ArcFace 依赖 + onnxruntime-gpu（GPU 加速）：
```bash
pip install insightface
pip install onnxruntime-gpu==1.23.2
```
> 首次使用需下载 ArcFace ONNX 模型（约 100MB），脚本会自动下载到 `~/.insightface/models/buffalo_l/`

#### 3. 初始化配置（复制模板）

首次使用，先把脱敏模板复制成真实配置：
```bash
# Windows
copy config.example.json config.json

# 或 Linux/macOS
cp config.example.json config.json
```
`config.json` 已被 `.gitignore` 忽略（不会上传泄露），请在其中填入你自己的信息。

#### 4. 获取 API Key

| 服务 | 链接 | 说明 |
|------|------|------|
| DeepSeek | https://platform.deepseek.com/usage | 注册后充值创建 Key |
| Qwen（推荐） | https://bailian.console.aliyun.com/ | 新用户有 100 万 tokens 免费额度，支持图像识别 |

填入 `config.json` 中的 `APIKEY` 字段。

#### 5. 本地 TTS（可选）

- **GPT-SoVITS**（短文本日语）：下载整合包 https://www.yuque.com/baicaigongchang1145haoyuangong/ib3g1e/dkxgpiy9zb96hob4 ，放入项目根目录。
- **F5-TTS**（长文本中文）：模型已内置在 `F5-TTS_Models/`，含 `F5TTS_v1_Base` 权重 + `vocos-mel-24khz` 声码器。

#### 6. 一键启动
```bash
python run_launcher.py
```

---

## 🖱️ 交互方式

### 桌宠窗口
| 操作 | 效果 |
|------|------|
| 点击下半身 | 进入输入模式，键盘输入文字后按回车发送 |
| 按住头部左右晃动 | 摸头互动 |
| 鼠标中键拖动 | 移动桌宠位置 |
| 长按 **Shift 2秒** | 切换 2D 立绘 / Live2D 模式 |
| 长按 **Ctrl 2秒** | 摄像头拍照 + 人脸识别 + AI 搭话 |
| 长按 **Alt 2秒** | 切换长文本输出模式（流式中文 TTS） |
| 长按 **CapsLock 2秒** | 语音输入（需在 config 中开启） |

### 系统托盘
右键托盘图标可快速切换：
- **Do Not Disturb** — 勿扰模式（停止自动搭话）
- **Screenshot** — 屏幕识别开关
- **Clear History** — 清除对话记忆
- **Exit** — 退出

### PCL 启动器
运行 `python run_launcher.py` 打开图形化启动器。功能与多角色操作见上方教程**第 4 节**；启动桌宠后底部会出现功能按钮：按住说话、屏幕识别、摄像头识别、Live2D 切换、长文本模式。

---

## 💬 QQ 聊天

让丛雨通过 QQ 小号与你聊天，**桌宠不开也能用**。

### 准备 NapCat

1. 下载 NapCat Releases 的 **`NapCat.Shell.Windows.OneKey.zip`**：https://github.com/NapNeko/NapCatQQ/releases
2. 解压后放置到项目根目录 `NapCat.Shell.Windows.OneKey/`
3. **下载 `NapCat.Shell.zip`**（运行时本体），解压后放入 `NapCat.Shell.Windows.OneKey/NapCat/`
4. **下载 QQ Windows 版安装程序**（如 `QQ_9.9.33_x64.exe`），放入 `NapCat.Shell.Windows.OneKey/`
5. 运行 `NapCat.Shell.Windows.OneKey/bootmain/napcat.bat` 首次自动解压（若 404 则手动用 7z 解压 QQ 安装包到 `bootmain/`，QQ.exe 需在 `bootmain/QQ.exe`）
6. 运行 **`NapCat.Shell.Windows.OneKey/start_napcat.bat`**（专用启动脚本，无需注册表）→ 弹出二维码 → 手机 QQ 扫码登录小号
7. 确认控制台出现 `WebSocket服务: 127.0.0.1:3001 已启动`

### 启动 QQ 聊天

- **方式一（PCL）**：`config.json` 中 `qq_enabled="true"` → 启动器出现「💬 启动 QQ AIpet」按钮
- **方式二（命令行）**：
  ```bash
  python run_qq.py
  ```

### 使用说明

| 场景 | 行为 |
|------|------|
| 私聊 | 直接回复（AI 人设 = 长文本 prompt） |
| 群聊 | 仅 **@丛雨** 时回复 |
| 表情包 | AI 根据语境从 `biaoqingbao/` 选 gif 发出 |
| 语音消息 | `qq_send_voice="true"` 时 F5-TTS 合成语音（需 F5-TTS 服务 9881 运行） |
| 记忆 | 大号私聊与桌宠共享当前角色长文本记忆；其他私聊/群聊按会话分仓（见下） |

**多角色**：QQ 服务的是 PCL 里选中的**活动角色**——人设、表情包、语音、记忆都来自该角色包；切换角色后需重启 QQ 生效。

**离线消息补拉**：启动时自动补回离线期间的消息（大号 + 其他好友）：
- 窗口 = 上次启动时间往前推 **24 小时**（隔一天再开也能补回；首次运行只补最近 10 分钟防刷历史）
- 每条消息按 message_id 去重，**一生只回一次**
- 状态存于 `data/qq_offline_state.json`（时间基线）与 `data/qq_processed_ids.json`（已处理 ID）

### 表情包
- 放入当前活动角色的 `pets/<id>/biaoqingbao/` 目录（**gif/png/jpg**，avif 不支持发送），文件名即情感标签
- AI 会从文件名列表中选最贴合语境的 1 张随回复发出
- 丛雨内置 20 张：抱抱/鄙视/鞭尸/馋/嘲笑/吃薯片/否定/尴尬/喝奶茶/肯定/哭哭/你认真的？/千恋万花启动/求收养/撒娇/思考/听不懂/偷看你/威胁/无语

---

## 🔧 完整项目功能与实现

### 1. 双对话模式（短文本 / 长文本）

| 特性 | 短文本模式（默认） | 长文本模式（Alt 切换） |
|------|-------------------|----------------------|
| 对话模型 | qwen-plus / deepseek-chat | qwen-plus / deepseek-chat（流式，`longtext_model` 控制） |
| TTS 引擎 | GPT-SoVITS（日语，音色克隆） | F5-TTS（中文，流式逐句） |
| TTS 服务端口 | 9880 | 9881 |
| 输出特点 | 短（≤3句），立绘/情感/翻译并行 | 长（不限字数），标点切句逐句合成播放 |
| 触发方式 | 默认 | Alt 长按 2 秒 或 PCL 按钮 |

**长文本流式管线**（7 段流水线，防卡死设计）：
```
Qwen 流式 token（后台 QThread）
  → 按标点(。！？，)切句
  → clause_ready 信号 → 主线程显示文字
  → LongTextTTSManager 串行合成队列
  → F5-TTS HTTP 服务（9881，GPU 优先）
  → pygame.mixer 后台播放线程（只创建一次，24000Hz）
  → 播完回调 → 显示下一句
```

**切句算法**（`longtext/longtext_manager.py`）：
- 强断句：`。！？…；;` 换行（无条件切断）
- 弱断句：逗号（短文本直接切，超长文本 20 字后找逗号切，避免碎片化）
- 兜底：30 字强制切（防止 buffer 无限膨胀）
- **引号闭合**：断句符后紧跟的右引号（`” ’ 」 』 " '`）和**反引号**（`` ` ``，markdown 代码标记）连续并入前句，杜绝 "引号被单独切成 1 字无意义片段"
- **连续省略号**：`……` 合并为一个整体（不断句断在中间、不残留第二颗 `…`）
- **流末清扫**：流结束时的纯符号残留（引号/省略号/标点/空白）直接丢弃，不输出为无意义片段
- **断点延迟**：断句符恰在 buffer 末尾时延迟一拍切句，等可能的右引号到达后一起切出
- **调试日志**：每次切句前打印完整 buffer（`repr` 格式，特殊字符可见），便于定位拆分问题

### 2. 双 TTS 引擎

**GPT-SoVITS**（短文本日语）：
- 对话回复 → 句子分割 → 情感分析 → 日文翻译 → 并发 TTS 合成（3 线程）
- 参考音频按情感分类（当前角色包 `pets/<id>/voices/short/<情绪>/`）

**F5-TTS**（长文本中文）：
- 零样本音色克隆（参考音频 `reference_voices/long_chinese/953244.wav`）
- GPU 优先（CUDA），CPU 回退
- 启动时后台预加载模型（避免首次合成卡顿）
- 声码器 `vocos-mel-24khz` 本地化（避免 HF 超时）
- **数字转中文**：合成前将阿拉伯数字转为中文读音（`cn2an`，需 `pip install cn2an`），
  例如 `第31次，0.4秒` → 音频念"第三十一次，零点四秒"；**显示文本保持原文不变**，仅语音朗读转换。
  > 若未安装 cn2an 则安全跳过（数字原样传给 TTS，可能读不准）。

**多音字手动添加教程**（F5-TTS 朗读某些词读错时用）：

1. 打开 `longtext/f5tts_server.py`
2. 找到 `load_model()` 函数里的 `load_phrases_dict({...})`
3. 向字典中追加词条，格式为：`"词语": [["拼音1"], ["拼音2"], ...]`
   ```python
   load_phrases_dict({
       "重庆": [["chong2"], ["qing4"]],      # 重庆（重=chóng）
       "音乐": [["yin1"], ["yue4"]],          # 音乐（乐=yuè）
       "行": [["xing2"]],                     # 单字默认读音
       "我数过": [["wo3"], ["shu3"], ["guo4"]],  # 数=shǔ（数数），不是 shù（数字）
       "数着数着": [["shu3"], ["zhe5"], ["shu3"], ["zhe5"]],
        # 在这里按相同格式添加你发现读错的词
   })
   ```
4. 保存文件，重启 `restart_longtext.bat` 生效（F5-TTS 服务重建时加载词典）

> 拼音数字代表声调：1=一声，2=二声，3=三声，4=四声，5=轻声。
> 例："王" = `[["wang2"]]`，"重" 单独 = `[["zhong4"]]`（重量）。

### 2.5 🎨 更换角色声音（自定义语音包）

> 多桌宠架构下，**每个角色的参考音频都在自己的角色包内**：`pets/<id>/voices/`。给任何角色（含丛雨）换声音 = 替换对应音频文件，方法见上方教程**第 3 节**。要点：
> - **短文本日语语音（GPT-SoVITS）**：替换 `pets/<id>/voices/short/<情绪>/` 里的 `ref.wav/mp3`，并把 `asr.txt` 改成该音频的准确文本；**音频 3~10 秒**
> - **长文本中文语音（F5-TTS）**：替换 `pets/<id>/voices/long/` 的 wav，并在 pet.json 填 `long_ref_audio` + `long_ref_text`；F5-TTS 是零样本音色克隆，3~5 秒清晰音频即可
> - 丛雨未配置角色包内长语音时会用全局兜底 `reference_voices/long_chinese/953244.wav`
> - 改完重启桌宠（或 `restart_longtext.bat` 重建 F5-TTS）生效

---

### 3. 人脸识别（ArcFace + 三哈希回退）

**主引擎：ArcFace ONNX**（`tool/face_recognition.py`）：
1. **人脸检测**：OpenCV Haar Cascades（`haarcascade_frontalface_default.xml`）
2. **特征提取**：insightface `buffalo_l` 模型 → 512 维 embedding（ONNX Runtime GPU 推理）
3. **比对**：余弦相似度
   - 主人：最大相似度 ≥ 0.28
   - 他人：最大相似度 ≥ 0.35（且明显高于主人匹配度）
4. **决策**：检测到主人 → 称呼"主人"；检测到他人 → 说出人名+关系；未注册 → unknown

**回退引擎：三哈希投票**（ArcFace 加载失败时）：
- dHash + aHash + pHash 三算法哈希比对 + 汉明距离投票
- 精度低于 ArcFace，仅作保底

> ⚠️ **依赖**：`pip install insightface`、`onnxruntime-gpu`、`onnx`（必须装在**运行所用的 Python 环境**，本项目为全局 Python 310）。之前 `onnxruntime`/`onnx` 只装在 `.venv`，导致 ArcFace 加载失败回退三哈希——已修复。

### 4. 屏幕识别 / 摄像头识别

**识别触发源**（统一走 `start_thread(t=True)`）：
- 常开截图线程 `ScreenWorker`（间隔 `screen_interval` 秒）
- 常开摄像头线程 `CameraWorker`（间隔 `camera_interval` 秒，含人脸识别）
- PCL 按钮「屏幕识别」「摄像头识别」
- Ctrl 长按即时拍照
- 空闲检测（发呆/离开问候）

**长文本模式下的行为**：
- **空闲时**：识别 → 走长文本流式回复（"看到主人xxx"）
- **输出中**：跳过识别（不打断，线程继续抓取，输出结束后自动恢复）

**识别内容 → 记忆**：
- 识别触发写入 `priority=high`（长文本写入 `long_history.json` + 同步 `history.json`；短文本写入 `history.json`）
- 下一轮对话组装消息时：high 提取为 system「最近的观察」强注入（最多 5 条）；low 完全过滤
- 该轮对话结束后：high → low（`_demote_all_high()` 内存 + 文件降权）

### 5. 记忆系统

| 文件 | 用途 |
|------|------|
| `pets/<角色>/memory/history.json` | 短文本对话记忆（按角色分仓）+ 长文本同步写入 |
| `pets/<角色>/memory/long_history.json` | 长文本专属记忆（12 轮高权重，与 QQ 大号私聊共享） |
| `pets/<角色>/memory/qq/` | QQ 其他私聊/群聊的分仓记忆（按会话独立，互不串味） |

- 长文本对话：AI 回复 → `_save_long_history()` → 写入 `long_history.json` + 同步到 `history.json`
- 清除：托盘「Clear History」清短文本；长文本可调用 `clear_long_history()`
- 旧版共享记忆 `data/history.json` 已自动迁移（仅丛雨一次）

### 6. Live2D 模式

- 长按 **Shift 2秒** 切换 2D / Live2D
- Live2D 模式：点击触发说话、摸头互动、表情切换（情感标签 `[开心]` 等）、口型同步
- 文字层：pet 窗口透明化叠加在 Live2D 之上，长文本/短文本均正确提升到最上层

### 7. 空闲检测

- `GetLastInputInfo` 计算系统全局空闲时间
- 发呆阈值（`idle_thinking_minutes`）：温柔关心搭话
- 离开阈值（`idle_away_minutes`）：问候"还在不在"+提醒休息
- 回来 30 秒后：欢迎回来

### 8. 语音输入

- **CapsLock 长按 2 秒**（或 PCL 按钮）→ 录音 → faster-whisper 转写 → 触发对话
- 支持 GPU（float16）/ CPU（int8）自动切换

### 9. 架构速览

```
run.py (启动器：环境检测 → 依赖安装 → TTS 服务启动 → main.py)
main.py (PyQt5 主窗口 + FastAPI 28565 + 快捷键监听 + 托盘)
├─ classes/murasame_class.py   核心桌宠类（立绘/打字机/输入/对话分发/识别/记忆）
├─ classes/Worker_class.py     短文本对话线程 + 屏幕/摄像头定时线程
├─ pets/                       角色包（pet_registry.py 注册中心 + 各角色 pet.json/人设/模型/语音/记忆）
├─ longtext/                   长文本模块（manager / f5tts_server / longtext_tts / history）
├─ qq/                         QQ 聊天（NapCat 桥接 / 分仓记忆 / 离线补拉 / 视觉 / 指令）
├─ tool/                       工具集（chat / cloud_API_chat / camera / face_recognition / stt / voice_trigger）
├─ api.py                      FastAPI（/cloudAPI /tts /control 等）
├─ pcl_launcher/               图形化启动器
├─ Live2d/                     Live2D 渲染引擎（各角色模型在 pets/<id>/live2d/）
└─ GPT-SoVITS/                 短文本 TTS 引擎
```

---

## 👤 人脸识别使用指南

### 注册人脸
1. 运行 `python run_launcher.py` 打开 PCL 启动器
2. 点击导航栏 **"人脸"** 标签
3. 点击 **"+ 添加主人照片"**，选择你的正脸照片（推荐多角度：正面/侧面/低头/仰头）
4. 点击 **"+ 添加其他人"**，输入姓名和关系，选择对方的正脸照片
5. 所有配置保存在 `face_shibie/faces.json`，照片保存在 `face_shibie/master/` 和 `face_shibie/others/`

### 识别触发方式
- **常开摄像头**：`camera_enabled = "true"` 时定时拍照 + 识别
- **长按 Ctrl 2秒**：即时拍照 + 人脸识别 + AI 搭话
- **PCL 按钮"📷 摄像头识别"**：同上

### 识别效果
- 检测到主人 → 丛雨评论主人的穿着/动作，自然搭话
- 检测到他人 → 丛雨说出具体人名和关系（如 "xxx(同学)"）
- 未注册的人 → 返回 unknown，不会随意匹配

---

## ⚙️ 配置文件说明 (config.json)

所有配置项存储在项目根目录的 `config.json` 中，可通过 PCL 启动器的设置页面图形化修改，也可手动编辑。

```json
{
  "local_api": {
    "ollama": "http://localhost:28565/ollama",
    "qwen3_lora": "http://localhost:28565/qwen3-lora",
    "gpt_sovits_tts": "http://localhost:28565/tts",
    "cloud_api": "http://localhost:28565/cloudAPI",
    "longtext_tts": "http://localhost:28565/tts_long"
  },
  "APIKEY": {
    "deepseek": "sk-your-deepseek-key",
    "qwen": "sk-your-qwen-key"
  },
  "portrait": "b",
  "user_name": "你的名字",
  "model_type": "qwen",
  "tts_type": "local",
  "force_gpu_check": "false",
  "screen_type": "false",
  "voice_trigger": "false",
  "stt_model": "large-v3",
  "screen_interval": 150,
  "DEFAULT_PORTRAIT_SCREEN_RATIO": 0.8,
  "screen_index": 0,
  "idle_thinking_minutes": 6,
  "idle_away_minutes": 10,
  "live2d_enabled": "false",
  "camera_enabled": "false",
  "camera_interval": 100,
  "camera_id": 0,
  "face_recognition_enabled": "false",
  "longtext_enabled": "true",
  "longtext_tts_type": "f5tts",
  "longtext_max_history_turns": 12,
  "longtext_ref_voice": "reference_voices/long_chinese/953244.wav",
  "longtext_ref_text": "能和老师在一起，我真的，好高兴！",
  "longtext_model": "deepseek",
  "qq_owner_id": "你的大号QQ号",
  "qq_enabled": "false",
  "qq_napcat_ws": "ws://127.0.0.1:3001",
  "qq_napcat_http": "http://127.0.0.1:6099",
  "qq_send_sticker": "true",
  "qq_send_voice": "false",
  "qq_vision_enabled": "true",
  "qq_allow_groups": "true"
}
```

### 关键配置项详解

> 💡 **对话模型推荐用 `qwen`**：项目的全部 prompt（立绘/情感/翻译/切句）均为 **Qwen 调优**，输出格式稳定。`deepseek` 亦可用，但**偶发格式不兼容**（如：立绘缺脸/表情层丢失、短文本切句失败整段显示、摄像头识别走错 key 分支），遇到此类异常请切回 `qwen`。

| 配置项 | 说明 |
|--------|------|
| `model_type` | `qwen`（推荐）/ `deepseek` / `local`（本地 Ollama） |
| `tts_type` | `local`（GPT-SoVITS）/ `cloud`（云端 TTS） |
| `longtext_enabled` | 长文本模式总开关（`"true"` 启用） |
| `longtext_tts_type` | 长文本 TTS 引擎（当前仅 `f5tts`） |
| `longtext_ref_voice` | F5-TTS 参考音频（音色克隆，3-5 秒最佳） |
| `longtext_ref_text` | 参考音频对应文本 |
| `longtext_model` | 长文本对话模型：`qwen`（Qwen-plus）/ `deepseek`（DeepSeek-chat，默认，更聪明） |
| `qq_owner_id` | 主人 QQ 号（大号私聊共享记忆，且 `/clear` 指令仅大号可用） |
| `qq_enabled` | QQ 功能总开关（PCL 显示「启动 QQ AIpet」按钮） |
| `qq_napcat_ws` | NapCat WebSocket 地址（默认 `ws://127.0.0.1:3001`） |
| `qq_napcat_http` | NapCat HTTP API 地址（默认 `http://127.0.0.1:6099`） |
| `qq_send_sticker` | QQ 回复是否附带表情包 gif |
| `qq_send_voice` | QQ 回复是否附带 F5-TTS 语音（需 9881 服务运行） |
| `qq_vision_enabled` | QQ 私聊图片识别（收到图片用 qwen3-vl-plus 识别并回应） |
| `qq_allow_groups` | QQ 群聊开关（仅 @丛雨 时回复） |
| `screen_type` | 常开屏幕截图识别开关 |
| `camera_enabled` | 常开摄像头识别开关 |
| `face_recognition_enabled` | 人脸识别开关（ArcFace） |
| `live2d_enabled` | Live2D 模式开关（需 pip install live2d-py） |

> 关闭人脸识别后注册信息不会清除，重新开启即可恢复。

---

## 📁 文件与数据位置（重要）

知道文件放哪儿，才能顺利解锁功能、管理数据：

| 路径 | 用途 |
|------|------|
| `config.json` | **核心配置**（API Key / 开关 / 模型选择），首次运行自动从 `config.example.json` 生成 |
| `api.py` / `main.py` / `run.py` | 桌宠本体：启动器 / FastAPI 后端 / 主窗口 |
| `pets/<角色>/` | **角色包**（多桌宠核心）：pet.json + 人设 + 头像 + live2d/ + voices/ + biaoqingbao/ + memory/ |
| `pets/<角色>/live2d/` | 该角色 Live2D 模型（model3.json + moc3 + 贴图 + exp/ + motion/） |
| `pets/<角色>/fgimages/` | 2D 立绘素材（仅丛雨有，分 `a`/`b` 两套服装） |
| `pets/<角色>/biaoqingbao/` | 该角色 QQ 表情包（gif/png/jpg），文件名即情感标签 |
| `pets/<角色>/voices/short/<情绪>/` | **短文本音色**（GPT-SoVITS 按情感分类的参考音频 + asr.txt） |
| `pets/<角色>/voices/long/` | **长文本音色**（F5-TTS 参考音频，配 pet.json 的 long_ref_audio/text） |
| `reference_voices/long_chinese/953244.wav` | 长文本**全局兜底**音色（角色包没配长语音时使用） |
| `pcl_launcher/` | 图形化启动器（PCL 风格），改设置 / 管人脸 / 管记忆都在这里 |
| `F5-TTS_Models/` | F5-TTS 模型（`F5TTS_v1_Base` 权重 + `vocos-mel-24khz` 声码器） |
| `GPT-SoVITS/` | 短文本日语 TTS 整合包（体积大，需自行下载放入） |
| `face_shibie/faces.json` | 人脸注册数据（主人/他人），照片在 `face_shibie/master/` + `others/` |
| `pets/<角色>/memory/history.json` | 短文本对话记忆（按角色分仓） |
| `pets/<角色>/memory/long_history.json` | 长文本对话记忆（与 QQ 大号私聊共享） |
| `pets/<角色>/memory/qq/` | QQ 分仓记忆（其他人的私聊 + 群聊独立会话；旧 `data/qq_memory/` 为兜底） |
| `data/qq_offline_state.json` | QQ 离线补拉的时间戳 |
| `data/qq_processed_ids.json` | QQ 已处理消息 ID（防重复回复） |
| `NapCat.Shell.Windows.OneKey/` | QQ 机器人运行环境（NapCat） |
| `runtime/venv/` | 项目本地虚拟环境（`install.bat` 自动创建） |
| `restart_longtext.bat` | 一键重启 F5-TTS 语音服务（改了音色/词典后用它） |

---

## 🌟 解锁全部功能清单

| 功能 | 需要做什么 | 配置文件开关 |
|------|-----------|-------------|
| 💬 云端对话 | 填 API Key（`APIKEY.qwen` 或 `APIKEY.deepseek`） | `model_type="qwen"/"deepseek"` |
| 🗣 长文本中文语音 | 项目自带 F5-TTS 模型 + 参考音频 | `longtext_enabled="true"` |
| 🇯🇵 短文本日语语音 | 下载 GPT-SoVITS 整合包放入根目录 | `tts_type="local"` |
| 🖥 屏幕识别 | 开启 | `screen_type="true"` |
| 📷 摄像头识别 | 开启 + 插好摄像头 | `camera_enabled="true"` |
| 👤 人脸识别 | PCL「人脸」页添加主人/他人照片 | `face_recognition_enabled="true"` |
| 🎭 Live2D | 需 `pip install live2d-py` | `live2d_enabled="true"` |
| 🎤 语音输入 | 需装 sox/ffmpeg + faster-whisper | `voice_trigger="true"` |
| 💬 QQ 聊天 | 准备 NapCat（见上方章节） | `qq_enabled="true"` |
| 🖼 QQ 表情包 | 往活动角色 `pets/<id>/biaoqingbao/` 加 gif | `qq_send_sticker="true"` |
| 🎙 QQ 语音 | F5-TTS 服务运行 | `qq_send_voice="true"` |
| 👁 QQ 图片识别 | 用 Qwen Key（支持视觉） | `qq_vision_enabled="true"` |

---

## 🔓 开源说明

### 开源协议
本项目采用 **GPL-3.0** 许可证，参考了 [LemonQu-GIT/MurasamePet](https://github.com/LemonQu-GIT/MurasamePet)。
仓库随附角色：丛雨（版权归 **YuzuSoft**）与诺瓦（模型/语音来源见「特别感谢」）；各角色素材版权归其原始权利人所有，仅限学习交流，**禁止商业用途**。

### 使用前提
- 需自备 **DeepSeek / Qwen API Key**（填入本地 `config.json`，无需提交）
- 本地 TTS 模型（GPT-SoVITS / F5-TTS）体积较大，建议 `.gitignore` 排除后单独分发或引导下载
- QQ 功能需自行准备 NapCat 环境
- 微信接入：另行**单开项目**（OpenClaw Clawbot），不随本仓库维护；丛雨人格提示词参考见 `提示词.md`（含未来蒸馏为 skill 的要点）

---

## 🤖 本地模型（可选）

如需要使用本地 AI 对话（model_type = "local"），需安装 Ollama 并拉取模型：

```bash
ollama pull qwen3:14b
ollama pull qwen2.5vl:7b  # 如需本地屏幕识别
```

---

## 💬 常见问题（安装/环境类）

### 人脸识别不工作 / 回退三哈希
> **解决**：确保 `insightface`、`onnxruntime-gpu`、`onnx` 已装到**运行桌宠所用的 Python 环境**。验证：
> ```bash
> python -c "import onnxruntime; print(onnxruntime.get_available_providers())"
> ```
> 期望输出包含 `CUDAExecutionProvider`。

### GPU 不可用
> 有显卡但提示 `Warning: CUDA is not available, set device to CPU.`
> **解决**：更新显卡驱动，确保 CUDA 与 PyTorch 匹配。

### F5-TTS 长文本不发声
> **解决**：确认 `longtext_enabled="true"`，F5-TTS 服务在 9881 端口运行（`restart_longtext.bat` 可一键重启）。模型首次加载约 10-30 秒。

### SoVITS 响应慢
> **解决**：下载与显卡对应的版本——50 系列用专用版，40 系及以下用通用版。

### Conda 激活错误
> **解决**：建议使用 Miniconda 而非完整版，或运行 `conda init`。

### API Key 报错
> **解决**：检查 API Key 是否有效、余额是否充足；若编码问题，重新保存为 ANSI 编码。

### 路径含特殊符号导致闪退
> **解决**：确保项目路径中没有中文名、括号、感叹号等特殊符号。

---

### ⭐ 如果觉得有用，请点个 Star！