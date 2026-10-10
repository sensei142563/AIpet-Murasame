# 版权、来源与修改声明（COPYRIGHT / NOTICE）

> 本仓库是修改后的作品。除文件或组件另有声明外，本仓库源代码依据
> **GNU Affero General Public License version 3（AGPL-3.0）** 发布。
> 本声明整理日期：**2026-10-10**；所核对的公开代码基准为
> [`a4a5f8e0191e7094a72192af0be2f9495027b228`](https://github.com/sensei142563/AIpet-Murasame/commit/a4a5f8e0191e7094a72192af0be2f9495027b228)。

## 1. 来源与权利范围

| 项目 | 说明 |
|---|---|
| 本仓库 | [sensei142563/AIpet-Murasame](https://github.com/sensei142563/AIpet-Murasame) |
| 直接上游 | [kuxiaowo/AIpet-Murasame](https://github.com/kuxiaowo/AIpet-Murasame) |
| 已核对的上游历史版本 | [`a23e7177be87f90a928943eefeb9c8ac0365f20a`](https://github.com/kuxiaowo/AIpet-Murasame/commit/a23e7177be87f90a928943eefeb9c8ac0365f20a)，2025-11-22 |
| 更早上游 | [LemonQu-GIT/MurasamePet](https://github.com/LemonQu-GIT/MurasamePet)，按直接上游及本仓库既有来源说明保留 |
| 历史来源核对快照 | [`06e0869637079ef25aa0cb2e759b6140824009c5`](https://github.com/sensei142563/AIpet-Murasame/commit/06e0869637079ef25aa0cb2e759b6140824009c5) |
| 原来源声明补充日期 | 2026-09-14，见 [issue #4](https://github.com/sensei142563/AIpet-Murasame/issues/4) |
| 本次声明整理日期 | 2026-10-10；具体代码修改日期以对应提交及文件说明为准 |
| 源代码许可证 | AGPL-3.0，完整正文见 [LICENSE](LICENSE) |

**本仓库继承了直接上游的代码，并在其基础上继续修改；新增文件或重写部分并不消除继承代码的版权。**

- `kuxiaowo` 对其在直接上游中完成的原创贡献保留版权；其[上游声明](https://github.com/kuxiaowo/AIpet-Murasame/blob/26858fae94cfa6e5f8e1d763ea9e1fb0fe1c2641/COPYRIGHT.md)记载为
  **Copyright © 2025–2026 kuxiaowo**。
- `sensei142563` 及其他实际贡献者对各自完成的原创修改保留版权；本声明不把协作者的贡献
  统一归属于仓库维护者，也不改变上游或第三方的权利。
- 更早上游作者、第三方库作者、字体作者、角色与素材权利人分别保留其权利。
- 以上署名只适用于各自依法可受著作权保护的贡献，不表示任何账号拥有整个文件、全部资源
  或整个仓库的排他版权。

Git 历史中还出现 `developer`、`dsh-sync`、`zcode` 等作者标识，以及旧历史中的协作者整合记录。
这些标识可以定位提交，但不足以确认真实作者或推断版权转让。各贡献的署名与日期应保留原有记录；
有更具体的作者说明时，应按证据补充。不能仅凭一个提交的 author 字段，把其他来源的代码归给该账号。

This repository is a **modified version** of `kuxiaowo/AIpet-Murasame`, whose earlier
upstream is `LemonQu-GIT/MurasamePet`. Unless a file or component states otherwise,
its source code is distributed under the **GNU Affero General Public License version 3**.
Upstream authors and downstream contributors retain copyright in their respective
contributions. Third-party assets and components are not relicensed by this notice.
This notice was reviewed on **2026-10-10** against the public revision linked above.

## 2. 已核实的代码继承关系

以下表格说明**历史快照**的对应关系，不表示当前 main 中这些文件仍与上游逐字节一致：

| 文件 | 上游 `a23e7177…` 与本仓库历史快照 `06e08696…` 的相同 Git blob SHA |
|---|---|
| `download.py` | `197f5bb03d723840f934594ff3b7c3b70be84f28` |
| `tool/stt.py` | `4672d886c5768a0484c7a1872042493bce3d4eb4` |

在本次核对基准 `a4a5f8e0…` 中，`download.py` 和 `tool/stt.py` 均已继续修改。
`tool/voice_trigger.py` 仍与上述上游历史版本内容一致（blob
`6a149774617bfe761352ac8aee5cd40b22ea8924`）。
`classes/Worker_class.py`、`classes/murasame_class.py`、`main.py`、`run.py`、`api.py`、
`tool/chat.py`、`tool/config.py`、`tool/generate.py` 等同路径模块也在继承基础上演进。

相同 blob SHA 能核实文件内容一致，但不能单独证明最初创作者、全部修改者或授权链完整。
空的 `__init__.py` 文件不作为实质代码来源的独立证据。
完整核对范围、统计口径及限制见 [版权核对记录](docs/COPYRIGHT_AUDIT.md)。

## 3. 相对上游历史版本的主要修改

下表描述本仓库在核对基准中可见的功能与代码变更，不把所有改动归功于单一作者，
也不将 README 的计划、外部仓库或本地未公开文件算作本仓库已经发布的实现。

| 修改范围 | 可核对的实现位置 | 主要变化 |
|---|---|---|
| 多角色与资源组织 | `pets/pet_registry.py`、`pets/*/pet.json`、`pcl_launcher/pet_slots.py` | 将角色配置、立绘、Live2D、人设、记忆和语音路径按角色组织；当前存在丛雨、夏目、诺瓦及模板角色包 |
| 启动器与编辑工具 | `pcl_launcher/`、`run_launcher.py` | 页面导航、角色向导、主题与字体选择、立绘和触摸区域编辑、模型状态、更新日志及后台 HTTP 请求 |
| 语音与对话 | `chat.py`、`tool/chat.py`、`longtext/`、`tool/stt.py`、`tool/tts_service.py` | GPT-SoVITS 与 F5-TTS 接入、长文本流式切句与播放、按角色选择参考音频/权重、离线识别与缓存处理 |
| QQ 通道 | `qq/`、`run_qq.py` | NapCat/OneBot 接入、离线补拉、会话记忆与消息调度、图片识别、音乐和自主学习等通道功能 |
| 微信通道 | `wechat/`、`run_wechat.py` | iLink 协议客户端、登录与续期、消息接收、待处理收件箱及持久化处理 |
| 状态、记忆与主动行为 | `tool/state.py`、`tool/attention.py`、`tool/desire.py`、`tool/care.py`、`tool/habits.py`、`tool/self_learn.py`、`tool/experience.py`、`tool/reminder.py`、`classes/status_window.py` | 心情与关系状态、开口时机、习惯和经验记录、自主学习、关怀、提醒与状态展示 |
| 电脑操作与视觉 | `tool/pc_control.py`、`tool/pc_task.py`、`tool/autonomy.py`、`tool/file_access.py`、`tool/music.py`、`tool/uia.py`、`tool/vision_*.py` | 键鼠与任务执行、操作档位、文件读取、音乐控制、本地/云端视觉接入与诊断 |
| 立绘与运行兼容 | `tool/portrait_*.py`、`tool/paths.py`、`tool/pet_lock.py`、`tool/msvc_runtime.py`、`classes/` | 多套立绘与装扮处理、合成画布修复、路径与进程锁处理、Windows 运行时和 Qt 生命周期修复 |
| 构建、验证与文档 | `build_launcher.py`、`tool/pack/`、`tests/`、`docs/`、`更新日志/` | 绿色版与安装包构建、配置/界面/生命周期等检查，以及开发规划和修改记录 |

当前目录包含互相重叠的旧入口和新模块；列出路径不意味着所有入口都已统一或所有功能都经过运行验证。
README 提及的 `chatter` 安卓端属于外部项目；本次核对基准中没有 Kotlin/Android 实现，
其代码、SDK、素材和发布包的许可应在对应仓库单独说明。

## 4. 源代码许可与再发布

完整条款以 [LICENSE](LICENSE) 为准。本文记录来源和权利范围，**不新增许可限制**。
在适用 AGPL 的传播或修改场景中，应保留既有版权、许可及无担保声明，随附许可证全文，
对修改后的作品作出醒目说明并给出相关日期；传播非源码版本时还须满足相应的对应源代码要求。
适用第 13 条时，应向通过网络远程交互的用户提供取得对应源代码的机会。

**AGPL-3.0 允许商业使用。** 这不表示第三方角色、模型、语音、字体、SDK 或其他素材
也获得相同授权。代码、依赖、模型权重与素材的许可证或授权条件必须分别核对。
“学习交流”“非商业用途”或提供来源链接本身，都不等于已经取得素材权利人的授权。

## 5. 第三方组件、字体与素材

详细路径与已确认的许可见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

- Python 依赖及外部服务保留各自许可；`requirements.txt` 是依赖清单，不是完整授权清单。
- `fonts/` 的五款字体为 SIL OFL 1.1；根目录旧版 `思源黑体Bold.otf` 的内嵌许可为
  **Apache-2.0**。版本、内嵌版权与对应许可文本见 [字体声明](third_party/fonts/NOTICE.md)。
- `Live2d/Live2DCubismCore.dll` 是独立的原生组件，须核对其版本对应的 Live2D 条款，
  不能因本仓库采用 AGPL 或 Python 包采用开源许可，就推定该 DLL 也按 AGPL 授权。
- 丛雨与夏目的角色、立绘和相关游戏素材涉及柚子社等原始权利人；诺瓦（`noir`）角色包的
  既有来源说明见 README。模型制作、角色原作和语音数据可能涉及不同权利人。
- `场景素材/`、图标、表情图片、角色资源以及随附的 NLTK 标注数据，均不能自动视为
  本仓库作者的原创内容或归入 AGPL 授权。

本次整理补充可核实的字体许可文本，**不声称已获得或完成核实所有第三方素材、模型和二进制的授权**。
尚缺来源或再分发条件的项目已在第三方声明和核对记录中列明，需由维护者或相应权利人补充证据。

## 6. 分发与后续维护

分发源码、绿色版或安装包时，应保留本文件、`LICENSE`、第三方声明以及随附的字体许可文本。
外部运行时、模型、角色语音和本地新增资源也应携带其适用的版权与许可信息，不能仅复制本仓库的 AGPL。
本仓库构建脚本的 Git 文件收集路径会收集追踪文件；无 Git 环境时的手工清单也应包含上述声明。

新增贡献、替换字体/SDK/模型、增加角色包或变更素材来源后，应同步更新相关说明。
核对基准日期只说明本次检查覆盖的公开版本，不替代各文件与后续提交的修改日期。

## 7. 更正

发现来源、署名、修改范围或第三方条件不准确时，请通过
[Issues](https://github.com/sensei142563/AIpet-Murasame/issues) 提供文件路径、版本及可核对依据。
后续更正应保留真实的来源和贡献记录，不将历史继承关系改写为全部原创。
