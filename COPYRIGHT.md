# 版权、来源与修改声明（COPYRIGHT / NOTICE）

> 本文档依据 **GNU Affero General Public License v3.0（AGPL-3.0）第 5 条** 的要求，醒目声明本仓库
> 是修改后的版本，并说明其直接上游、修改者、修改日期与主要修改内容。

---

## 一、本仓库是修改版本（MODIFIED VERSION NOTICE）

**本仓库 `sensei142563/AIpet-Murasame` 是基于他人作品的修改版本，依据 AGPL-3.0 发布。**

| 项目 | 说明 |
|---|---|
| **本仓库** | `sensei142563/AIpet-Murasame` — <https://github.com/sensei142563/AIpet-Murasame> |
| **直接上游** | `kuxiaowo/AIpet-Murasame` — <https://github.com/kuxiaowo/AIpet-Murasame> |
| **更早上游** | `LemonQu-GIT/MurasamePet` — <https://github.com/LemonQu-GIT/MurasamePet> |
| **修改者** | `sensei142563`（GitHub） |
| **修改开始日期** | 2026-08-10 |
| **最近修改日期** | 2026-09-14 |
| **本声明补充日期** | 2026-09-14 |
| **许可证** | GNU Affero General Public License v3.0（AGPL-3.0），全文见 [`LICENSE`](LICENSE) |

**本仓库的全部修改内容同样以 AGPL-3.0 授权。** 任何获得本作品副本的人，均适用 `LICENSE` 中的
全部条款（含第 13 条：通过网络提供服务时的源码提供义务）。

> This repository is a **modified version** of `kuxiaowo/AIpet-Murasame` (whose earlier upstream is
> `LemonQu-GIT/MurasamePet`). It is licensed under the **GNU Affero General Public License v3.0**.
> Modifications were made by `sensei142563` starting 2026-08-10. See `LICENSE` for full terms.

---

## 二、已核实的来源对应关系

以下对应关系通过 **Git blob SHA（内容哈希）** 核实：blob SHA 相同即表示文件内容**逐字节一致**
（GPL/AGPL 体系下通常表述为 "verbatim copy"）。

| 本仓库文件 | 与上游 `kuxiaowo/AIpet-Murasame` 的对应版本 | Git blob SHA |
|---|---|---|
| `download.py` | 上游历史版本 commit `a23e7177be87f90a928943eefeb9c8ac0365f20a`（上游维护者说明为 2025-11-22 版本） | `197f5bb03d723840f934594ff3b7c3b70be84f28` |
| `tool/stt.py` | 上游同一历史版本 commit `a23e7177…` | `4672d886c5768a0484c7a1872042493bce3d4eb4` |

说明：
- 上表的上游 commit 由上游维护者（`kuxiaowo`）指出；本仓库已用 `git hash-object` / `git rev-parse` 独立核验
  **blob SHA 完全一致**（blob SHA 相同即内容逐字节一致），任何人可自行复核。
- 上表所列文件在本仓库**开源发布时（2026-08-16）即以逐字节一致的形式存在**，此后部分文件已在本仓库中
  继续修改（例如 `tool/stt.py` 在 v1.16 中修改了离线模型检测顺序），当前版本 blob 已与上游不同。
- 除上表外，`classes/Worker_class.py` 等模块沿用了上游历史版本的代码结构与实现，并在此基础上继续修改。
- 本仓库自 2026-08 起在 `kuxiaowo/AIpet-Murasame` 的基础上独立演进，因此**直接上游应表述为
  `kuxiaowo/AIpet-Murasame`**，仅标注更早的 `LemonQu-GIT/MurasamePet` 并不完整。

---

## 三、相对上游的主要修改内容

本仓库相对直接上游的主要修改（按时间顺序，2026-08 至今）：

1. **多桌宠架构**：由单角色改造为「一个引擎 + N 个角色包」（`pets/` + `pet_registry.py`），
   记忆/人设/表情包/语音/模型按角色隔离，并随仓库附赠「丛雨 + 诺瓦」两个示范角色包。
2. **PCL 图形化启动器扩展**：多角色管理页、设置页、记忆管理页、提示词编辑器、人脸管理页。
3. **QQ 通道增强（NapCat / OneBot11）**：离线消息补拉（24 小时窗口 + message_id 去重）、
   断线指数退避自动重连、消息调度器（离线按序补回 / 私聊合并）、按会话分仓记忆、图片识图、
   表情包自主发送、`/clear` 等指令、NapCat token 鉴权、onebot 配置被重置时的环境诊断。
4. **微信通道接入（ClawBot / 官方 iLink 协议）**：扫码登录与免扫续期、待处理收件箱（at-least-once
   防丢消息）、域名白名单、原子写持久化。
5. **语音链路**：GPT-SoVITS（短文本日语）与 F5-TTS（长文本中文流式逐句）双引擎接入、
   F5-TTS 服务自动拉起与解释器探测、torchaudio 不可用时的 soundfile 回退、语音识别离线化。
6. **兼容性与稳定性修复**：AMD/Intel 显卡不再直接退出（转 CPU 模式）、中文路径下 Qt 插件路径修复、
   摄像头识图崩溃修复、uvicorn 事件循环噪音消除、Windows 下 winsound 语音播放兜底等。
7. **文档与构建**：README 重构（新手教程 / 进阶文档分区）、绿色版打包脚本（`build_launcher.py`）、
   隐私数据处理（`config.json` / `data/` / 人脸 / 记忆一律 `.gitignore`，不进入仓库与分发包）。

> 上游的既有功能与实现均予保留；上述修改为增量扩展与缺陷修复，未移除上游的版权与许可证声明。

---

## 四、上游版权与许可证保留

- 本仓库完整保留上游的 `LICENSE` 文件（AGPL-3.0 全文，blob `0ad25db4bd1d86c452db3f9602ccdbe172438f52`）。
- 上游及其更早来源的版权归各自作者所有；本仓库的修改部分由 `sensei142563` 贡献，同样以 AGPL-3.0 授权。
- 本仓库不含任何上游或第三方的私有密钥、账号数据与本地路径。

---

## 五、第三方组件与素材

第三方开源组件的版权与许可证归其各自作者所有，主要包括：
GPT-SoVITS、F5-TTS、faster-whisper / CTranslate2、live2d-py、PyQt5、OpenCV、insightface、
NapCatQQ、UVicorn / FastAPI 等（详见 `requirements.txt` 与各项目主页）。

角色美术与语音素材（丛雨 — 柚子社《千恋＊万花》；诺瓦 — しらたまこ 星白 等）版权归其**原始权利人**所有，
本项目仅限学习交流使用，**禁止任何商业用途**。详见 README「特别感谢」一节。

---

## 六、联系与更正

如上游作者认为本仓库的来源标注、许可证声明或修改说明仍有不准确之处，欢迎通过
[Issues](https://github.com/sensei142563/AIpet-Murasame/issues) 指出，我们会及时核对并更正。
