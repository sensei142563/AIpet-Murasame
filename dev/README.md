# dev/ —— 开发辅助区与使用说明

主战场就是这个仓库（`AIpet-Murasame-main`）。这里放开发/验收用的脚本、截图与文档。
（此前辅助脚本一度放在临时实验区 `_audit_fish9269`，容易与主仓库脱节，已收回。）

---

## 一、本次新增/改造的功能清单

| 功能 | 实现 | 状态 |
|---|---|---|
| **Jev（本地判断）** | 电脑端 `api.py` 暴露 `POST /jev/choose` → `tool/jev.py`（双契约）→ 本地 NanoJev（Qwen3-0.6B 微调，`/api/evaluate`）；手机端 `JevClient` 把"这条回复配哪个表情包"作为封闭选择题发过去，答案必须落在候选集内 | ✅ **端到端已验证**（手机日志出现「选中「馋」置信度=0.094」；电脑端 `POST /jev/choose 200 OK`；`provider_calls: 0` 全本地） |
| **手机 AR + Live2D** | AR 页把相机预览与 Live2D 叠在一起：GL 表面用 `setZOrderMediaOverlay(true)`（压在相机表面之上、仍留在窗口内，位置跟随布局）+ `holder.setFormat(TRANSLUCENT)` + `setEGLConfigChooser(8,8,8,8,16,0)`，并把 native 每帧清屏 `glClearColor(...,1.0)` 改为 alpha=0（`app/src/main/cpp/LApp/LAppDelegate.cpp`，该目录被 gitignore，需 `git add -f`） | ✅ **真机截图验收**（丛雨全身、背景完全透明、实景透出） |
| **情绪 → 动作** | native 桥没有"直接播动作"的接口，动作由 C++ 的**命中区触摸**驱动；因此在 `Live2DView` 内按情绪合成一次 touch（hair/face/chest/skirt/leg 五区相对坐标）；仅丛雨启用（诺瓦模型未声明动作） | ✅ 完成（真机可触发） |
| **拍摄** | `＋` 面板「拍摄」→ 申请 CAMERA 权限 → 系统相机（`ACTION_IMAGE_CAPTURE`）→ 照片写入 `filesDir/captures/` 并作为一条消息进会话；FileProvider + `res/xml/file_paths.xml` | ✅ 完成 |
| **朗读 = 电脑 F5-TTS** | 手机 `VoiceClient` → 电脑 `longtext/f5tts_server.py` `POST /infer`（支持 `pet` 参数按角色取权威范例）→ wav → MediaPlayer；失败自动回退系统 TTS | ⚠ **接线完成、服务已验证**（health 0.17s、合成 6.26s、合法 RIFF）；**待确认**：需把设置页「朗读」打开后听一次 |
| **手机端日志** | `JevClient` / `VoiceClient` 都写：`files/*.log`、**外部可 pull 的** `getExternalFilesDir()/*.log`、logcat（标签 `JevClient`/`VoiceClient`）、App 的 `LogBus` | ✅ 完成（`adb pull /sdcard/Android/data/com.aipet.murasame/files/jev.log`） |
| 离线 ASR | sherpa-onnx zipformer（`assets/asr-zh-14M`） | ✅ 已有 |

---

## 二、怎么把电脑端拉起来（一键）

双击 **`dev/一键启动-本地Jev与语音.bat`**，它会：
1. 启动 NanoJev（`127.0.0.1:8765`）
2. 启动 F5-TTS（`127.0.0.1:9881`）
3. 启动 `api.py`（`0.0.0.0:28565`，**必须带** `TYPESAFE_BASE_URL=http://127.0.0.1:8765/api/evaluate`）
4. 等待并探测端口，然后建立手机到电脑的 USB 反向转发

手机端（设置页）填：
- 「Jev 电脑地址」= `http://127.0.0.1:28565`
- 「语音服务地址」= `http://127.0.0.1:9881`
- 「朗读」= **开**（否则不会朗读）

> **校园网做了客户端隔离**（手机与电脑互相 ping 不通，实测 100% 丢包），所以一律走
> **USB 反向转发**（`adb reverse`）。拔线/重启手机后重跑
> **`dev/手机连电脑-一键重连.bat`**。

### 健康检查
- `http://127.0.0.1:8765/api/health` → `{"ready":true, "provider_calls":0}`（0 = 全程本地，未调任何云服务）
- `http://127.0.0.1:9881/health` → `{"status":"ok","ready":true,"device":"cuda"}`
- 电脑端日志：`_api_serve.log`（`POST /jev/choose`）、NanoJev 的 `_serve.log`（`POST /api/evaluate`）、`_f5serve.log`（`POST /infer`）

---

## 三、脚本索引（`dev/scripts/`，python + adb，全部可复跑）

| 脚本 | 作用 |
|---|---|
| `一键启动-本地Jev与语音.bat` / `手机连电脑-一键重连.bat` | 拉起三服务 / 重建 USB 转发 |
| `phone_camera_component.py` | 加「拍摄」能力（权限 → 系统相机 → 进会话）并装机 |
| `ar_live2d_restore2.py` / `ar_mediaoverlay2.py` / `ar_transparent.py` / `ar_remove_black.py` | AR Live2D 叠加：MediaOverlay、透明 EGL 配置、native 清屏 alpha=0 |
| `emotion_to_motion.py` / `motion_wire2.py` | 情绪 → 动作（合成命中区触摸）+ 接线 |
| `fix_voice_riff2.py` / `voice_logging.py` | 修 VoiceClient 的 RIFF 判断 / 给语音链路加可取证日志 |
| `phone_send_pet.py` / `f5_pet_param3.py` | 朗读按角色选音色（手机传 pet / 服务端解析权威范例） |
| `fix_coldstart_load.py` / `fix_load_baseurl.py` / `fix_cleartext.py` / `fix_jev_timeout.py` | Jev 四个真 bug：冷启动加载、`load()` 写回 baseUrl、明文 HTTP 放行、超时放宽 |
| `jev_probe.py` / `e2e_final4.py` / `final_jev_confirm.py` | 探针 + 端到端验收（发消息、点 ↑ 发送、拉手机日志） |
| `restart_nanojev.py` | NanoJev 卡死（GPU 100% 不答健康检查）时重启并计时 |
| `final_install_verify.py` | 装机后**比对 `lastUpdateTime`** 核实是否真的装上（ad 静默失败时用） |
| `tts_enable_and_check.py` | 打开「朗读」并拉 `voice.log` 判定语音链路 |
| 其它 `find_*` / `check_*` / `look_*` | 源码与 APK 取证（含从 dex 里核对字符串） |

**经验教训（写在案，供以后）**
1. 改 Kotlin 不要用模糊字符串替换：按**行号/整行**改；多行参数表注意**前一个参数的尾逗号**。
2. 失败回滚要**最小范围**（`git checkout -- <单个文件>` 会把同文件里已成功的改动一起冲掉 —— AR 的 Live2D 就这样丢过一次）。
3. `adb shell input text` **不支持中文**（会被丢弃），验收脚本用 ASCII。
4. 聊天页发送按钮是 `↑`，**只在输入框有内容时出现**；点它即可发送。
5. `adb install` 可能静默不生效 → 装上后用 `dumpsys package ... lastUpdateTime` 核实；必要时加 `--no-streaming`。
6. 长跑的本地模型（NanoJev / F5）在大量并发测试后可能**僵死**（GPU 100%、健康检查不答）→ 重启即可。
