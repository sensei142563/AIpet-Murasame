# -*- coding: utf-8 -*-
"""在 chatter 仓提交：删除已无引用的第二套 ASR 模型（实测省 20.34 MB）。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = r"E:\university\order\python\pet\chatter"
MAP = os.path.join(REPO, "..", "AIpet-Murasame-main", "dev", "merge-map")

MSG = """chore(apk): 删除已无引用的第二套 ASR 模型 assets/asr-zh-14M —— 实测省 20.34 MB

背景：包体分析（见主仓 dev/docs/安卓包体分析-2026-10-13.md）发现 APK 313 MB，
其中 `assets/asr-zh-14M/*.onnx` 占 24.13 MB。

删除前的三项确认（避免误删真功能）：
  ① **git 已跟踪**该目录 5 个文件 ⇒ 删错可 `git checkout -- app/src/main/assets/asr-zh-14M` 恢复；
  ② 全仓检索 `asr-zh-14M` / `zh-14M` / `zipformer`（kt/java/xml/gradle/txt/json/md/cmake/pro/properties/kts）
     ⇒ 只有 `OnlineAsr.kt:16` 一条**历史注释**，没有任何加载代码；
     该注释自述："换模型历史：最初是 streaming-zipformer-zh-14M（tiny 级，效果一般）
     → bilingual zipformer（流式）→ 现在 SenseVoice（非流式）" ⇒ 它已被取代；
  ③ 目录内容：encoder 20.62 + decoder 1.80 + joiner 1.71 + selftest.wav 0.17 + tokens.txt 0.05 = 24.13 MB。

实测结果（**不是估算**）：
    app-debug.apk 328,430,626 字节（313.22 MB）
                 → 307,107,506 字节（292.88 MB）
    节省 **20.34 MB**
  拆包复核：包里 `asr-zh-14M` 条目数 = **0**。
  （24.13 MB 未压缩 → 20.34 MB 进包，因为 tokens.txt / selftest.wav 还能压缩。）

⚠ 踩坑记录：第一次重建后 APK **大小没变**，原因是 Gradle 的打包任务 **up-to-date 没重跑**。
  正确做法是**先删掉 app-debug.apk 再 assembleDebug**，拿到的才是真实数字。
  以后凡是"改了 assets 要验证包体"，都先删 APK 再构建。

下一步（见主仓文档）：SenseVoice（228 MB）改按需下载；release 开 R8 + shrinkResources；
`assets/Murasame` 与 `assets/pets/murasame/live2d` 的重复素材去重。
"""
p = os.path.abspath(os.path.join(MAP, "_msg_chatter_del.txt"))
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", REPO, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", REPO, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("手机仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:170])
n = subprocess.run(["git", "-C", REPO, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", REPO, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
