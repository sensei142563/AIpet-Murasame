# -*- coding: utf-8 -*-
"""提交 STT 升级第一版（换 bilingual zipformer + 自检按钮 + selfTest 修正），如实记录未完成项。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
CHAT = r"E:\university\order\python\pet\chatter"
MAP = os.path.join(MAIN, "dev", "merge-map")

MSG1 = """feat(asr): 手机端 STT 从 14M tiny 换成中英双语 zipformer（int8 约 198MB）

用户反馈"STT 效果一般"，要求多找开源社区现成的东西。取证结论：
  · 现用 sherpa-onnx-streaming-zipformer-zh-14M（encoder int8 21.6MB）——tiny 级，这就是效果一般的原因；
  · 换成 sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20（encoder 181.9 + decoder 13.1
    + joiner 3.2 MB）——社区经典模型，中英双语，**同一套 OnlineRecognizer/transducer API**，
    代码只改模型目录常量（文件名相同）；
  · 本仓库 AAR sherpa-onnx-v1.13.5 还暴露 OfflineRecognizer / OfflineParaformerModelConfig /
    OfflineSenseVoiceModelConfig 等 66 个识别相关类 —— 非流式更强模型（paraformer-zh-2024-03-09 int8
    227MB、SenseVoice）留作下一步，因为 App 是"录完再识别"，非流式其实更合适。

配套改动：
  · OnlineAsr.DIR 指向 assets/asr-zh-bilingual，并放了 16kHz/单声道 selftest.wav（由已知台词的 F5 输出
    「本座等你好久了。」重采样得到，作为验收真值）；
  · selfTest 改为**每次都从 assets 重新复制**样例——原来"存在就跳过"，换了模型还在识别旧样例，
    导致自检结果失真（实测踩到）；
  · 设置页（聊天 → ☰ → 设置）新增「识别自检」按钮，结果写 files/live2d.log 的 [asr] selftest text=[...]，
    便于 adb 自动验收。

验收状态（如实）：
  ✓ 新模型已打进 APK 并加载成功（日志 recognizer ready）；
  ✓ 自检能跑出结果，且日志里能辨认出样例内容（"本座…你…好久"）；
  ✗ 但与真值相比有重复/串音（如"本座车座我等等你好久啦"）。两个原因已定位：
    ① 验收音频是 24kHz F5 输出线性重采样到 16kHz，音质有损，应改用正常 16k 录音；
    ② 流式 zipformer 喂整段 + enableEndpoint 易出现重复，而本 App 是"录完再识别"，
       更适合非流式 paraformer/SenseVoice（下一步换 OfflineRecognizer）。
  对照：同一段音频走电脑 /stt（faster-whisper large-v3）得到「本座等你好久了」，与真值相似度 0.93。
"""
p1 = os.path.join(MAP, "_msg_asr1.txt")
io.open(p1, "w", encoding="utf-8", newline="\n").write(MSG1)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r1 = subprocess.run(["git", "-C", CHAT, "commit", "-F", p1], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("手机仓:", (r1.stdout or r1.stderr or "").splitlines()[0][:130])

MSG2 = """chore(stt): STT 选型与升级的调研脚本（模型体积取证 / AAR API 盘点 / 升级与验收）

dev/scripts/：
  · stt_survey.py        候选模型在 hf-mirror 的体积 + 本仓库 sherpa-onnx AAR 暴露的识别类 +
                          selfTest 的界面入口（这三份取证决定了升级方案）
  · stt_upgrade_1..5.py  下载模型/造 16k 样例/换模型/加自检按钮/逐步验收（含我踩的坑：
                          多设备 adb install 必须 -s；点按钮前必须等页面渲染；重试逻辑别选错标签；
                          selfTest 的"存在即跳过"会让换了模型的验收失真）
用途：下次换非流式模型（paraformer-zh / SenseVoice）时，这套取证与验收脚本可直接复用。
"""
p2 = os.path.join(MAP, "_msg_asr2.txt")
io.open(p2, "w", encoding="utf-8", newline="\n").write(MSG2)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
r2 = subprocess.run(["git", "-C", MAIN, "commit", "-F", p2], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("桌面仓:", (r2.stdout or r2.stderr or "").splitlines()[0][:130])

for name, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True).stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"],
                        capture_output=True, text=True).stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (name, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
