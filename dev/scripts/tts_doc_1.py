# -*- coding: utf-8 -*-
"""写 TTS 方案文档 + 提交本轮（撤 assets/tts、修 speak 顺序 bug、加离线 TTS 层、推送脚本）。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
CHAT = r"E:\university\order\python\pet\chatter"
MAP = os.path.join(MAIN, "dev", "merge-map")

DOC = """# TTS 方案（2026-10-11）

> 结论：出声按**可靠性分层、逐层降级**，任何一层成功就接手。本轮补上了最关键的一层——
> **手机本机离线 TTS（Kokoro int8）**，于是"拔线/没热点也能出声"成立；同时修掉一个顺序 bug：
> 台词包此前被排在"有没有电脑地址"之后，导致拔线时连已经打进 App 的台词包都不用。

## 一、五层链路（现状）

| 层 | 来源 | 延迟 | 依赖 | 何时用 |
|---|---|---|---|---|
| ① 预生成台词包 | `assets/voice`（19 条 1.85MB，`index.json` 精确匹配）| **秒出** | 无（纯离线）| 固定台词（开机问候、设置页自检等）**最优先** |
| ② 联网缓存 | `cacheDir/tts_<hash>.wav`（电脑合成过的结果）| 秒出 | 曾联过电脑 | 同一句话重复说 |
| ③ 电脑 F5-TTS | 电脑 `POST /infer`（端口 9881）| **约 4–6 s/句** | 电脑在跑 + USB/热点链路 | **她真正的音色**；在线首选 |
| ④ 本机离线 TTS | **Kokoro int8 多语**（sherpa-onnx，`OfflineTtsEngine`）| 数秒（CPU 2 线程）| 无（纯离线）| ③ 失败 / 没配地址（拔线）|
| ⑤ 系统 TTS | Android 自带 | 秒出 | 无 | 以上都不可用时的兜底 |

判定顺序（`VoiceClient.speak`）：**① → (有地址时) ② → ③ 失败落 ④ → 否则 ⑤**；
无地址时 **① → ④ → 否则 ⑤**。

## 二、本轮实测与取证

| 项 | 结果 |
|---|---|
| 台词包 | 已在 APK 内（`assets/voice/index.json` ✓）|
| 离线 TTS 模型 | `kokoro-int8-multi-lang-v1_0.tar.bz2` **132.3 MB** 下载 12 s（github.com 直链 ✓）|
| 解包后 | `model.int8.onnx` 114.2MB / `voices.bin` 28.2MB / `tokens.txt` / `espeak-ng-data/` **120 文件** / `dict/`，合计 **189.9 MB / 377 文件** |
| 放置策略 | **不进 APK**（否则 316MB → 约 500MB）；改 **adb push 到 `Android/data/<pkg>/files/tts`** —— 这正是 `OfflineTtsEngine.modelDir()` 查的第一顺位 |
| APK 取证 | BUILD SUCCESSFUL，316.2MB；含台词包 ✓；**不含** `assets/tts/` ✓ |
| 修掉的 bug | `speak()` 的 `base.isEmpty()` 早退在台词包判定**之前** → 拔线时台词包不生效、直接退化系统 TTS。已把台词包提到最前 |

## 三、显存仲裁（结论：**优先级不高，且原因清楚**）

实测：本机 **6141 MiB 总显存**，F5-TTS 常驻时占用 **5668 MiB**，只剩 **253 MiB** →
faster-whisper **large-v3 装不下**，STT 回落到 CPU int8，于是 PC 路线要 **10–13.5 s/句**。

但这条链**已不再是瓶颈**：

| 能力 | 谁做 | 速度/质量 |
|---|---|---|
| 语音识别 | **手机本机 SenseVoice int8**（已实测相似度 **0.94**，追平 PC large-v3 的 0.93）| 本地、离线 |
| 出声（常规）| **手机本机 Kokoro**（④）+ 台词包（①）| 本地、离线 |
| 出声（最佳音色）| 电脑 F5-TTS（③）| 需链路，4–6 s |

⇒ 因此**不需要**为了 STT 去抢显存（不必做"卸 F5 再载 whisper"这类折腾：F5 重载 40–80 s，得不偿失）。
需要的只是一条**共存规则**：

1. 电脑端同一时刻**只允许一个重型任务**（TTS 合成 / 视觉识别 / large-v3 识别）；
2. 手机侧**优先本机**（识别用 SenseVoice、出声用 台词包→离线 TTS），把电脑留给"她真正的音色"和识图；
3. 只有当用户明确要"最高质量识别"时，才走 PC large-v3，并**接受 10–13.5 s** 的等待（UI 需给进度提示）。

（`docs/plan/03-架构决议` 里写的"TTS/识图必须排队"与此一致；本文件补充了**实测数字**与**手机侧自足**这一变化。）

## 四、未验证 / 待办

1. **手机端离线合成尚未真机跑过**：模型已备好（`dev/tts_model_cache/`），需手机上线后执行
   `dev/scripts/push_tts_model.py` 推送，再看 `files/…/live2d.log` 里的
   `[tts] ready lang=zh sr=… speakers=…` 与 `离线 TTS 返回 N ms`。
2. 音色主观质量（Kokoro 中文女声 vs F5 的丛雨音色）**未试听**；
3. 日语发音路径（`lang="ja"` + espeak-ng-data）**未验证**（她说话混日文时要不要切语言待定）；
4. 合成耗时在手机 CPU 上的实测值**未测**（预期数秒）。
"""
io.open(os.path.join(MAIN, "dev", "docs", "TTS方案-2026-10.md"), "w",
        encoding="utf-8", newline="\n").write(DOC)
print("✓ 写了 dev/docs/TTS方案-2026-10.md")

MSG = """feat(tts): 手机本机离线 TTS（Kokoro int8）接通 + 修台词包顺序 bug + TTS 方案文档

一、修 bug（用户可见）：VoiceClient.speak 里 `base.isEmpty()` 的早退排在台词包判定之前，
    于是"没配电脑地址"（拔线/热点没开）时**连已经打进 App 的离线台词包都不用**，
    直接退化成系统 TTS。现在台词包提到最前，与有没有电脑无关。

二、出声改为五层逐层降级（任何一层成功即接手）：
    ① 预生成台词包 assets/voice（离线秒出）
    ② 联网缓存（电脑合成过的结果）
    ③ 电脑 F5-TTS /infer（她真正的音色，4–6s）
    ④ **本机离线 TTS：Kokoro int8 多语（sherpa-onnx 的 OfflineTtsEngine，原本已写好但没接进链路）**
    ⑤ 返回 false → 调用方回退系统 TTS
    判定：① →(有地址)②→③ 失败落 ④；无地址时 ①→④；④ 不可用才回 ⑤。

三、离线模型放置（不进 APK）：
    · 取证：sherpa-onnx 官方 Release 的 kokoro-int8-multi-lang-v1_0.tar.bz2 = 132.3MB，
      下载 12s（github.com 直链；GitHub API 被限流 403，故改用直链 HEAD 探测）；
      解包后 model.int8.onnx 114.2MB + voices.bin 28.2MB + tokens.txt + espeak-ng-data/(120 文件)
      + dict/ = 189.9MB / 377 文件。
    · 模型**不进 assets**（否则 APK 316MB→约 500MB），而是放在
      Android/data/<pkg>/files/tts —— 正是 OfflineTtsEngine.modelDir() 的第一顺位；
      新增 dev/scripts/push_tts_model.py 一键推送（手机上线后执行）。
    · APK 取证：BUILD SUCCESSFUL 316.2MB，含 assets/voice/index.json ✓，不含 assets/tts/ ✓。

四、文档：dev/docs/TTS方案-2026-10.md
    · 五层链路表 + 本轮实测数字；
    · **显存仲裁结论**：本机 6141MiB 总、F5 常驻占 5668MiB、仅剩 253MiB → large-v3 装不下、
      STT 回落 CPU 10–13.5s；但手机本机 SenseVoice 0.94 已追平 PC large-v3 0.93，
      出声也已本机自足 ⇒ **不需要为 STT 抢显存**，只需一条共存规则（电脑同时只跑一个重型任务、
      手机优先本机、只有要求最高质量识别时才走 PC 并接受等待）；
    · 未验证项 4 条（真机合成、音色试听、日语路径、耗时实测）。
"""
p = os.path.join(MAP, "_msg_tts1.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r1 = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("手机仓:", (r1.stdout or r1.stderr or "").splitlines()[0][:130])
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
r2 = subprocess.run(["git", "-C", MAIN, "commit", "-m",
                     "docs(tts): TTS 方案（五层链路 + 显存仲裁结论 + 离线模型放置与推送脚本）"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
print("桌面仓:", (r2.stdout or r2.stderr or "").splitlines()[0][:130])
for name, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True).stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"],
                        capture_output=True, text=True).stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (name, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
