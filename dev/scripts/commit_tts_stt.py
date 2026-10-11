# -*- coding: utf-8 -*-
"""提交本轮 TTS 台词包 + STT 借电脑 large-v3 的成果（两仓），并打印状态。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
CHAT = r"E:\university\order\python\pet\chatter"
MAP = os.path.join(MAIN, "dev", "merge-map")

MSG1 = """feat(voice): 预生成台词包（离线秒出声）+ VoiceClient 台词包优先

用户要求：TTS 继续推进；APK 体积约束取消（"瘦身不做，放弃约束"）。

· assets/voice/：用电脑 F5 预生成 19 条固定台词（丛雨 13 + 诺瓦 6，1.85 MB，平均 2.24s，
  含 App 固定会说的「你好，我是丛雨。」），索引 assets/voice/index.json：
  {"schema":"aipet.voicepack/1","index":{"<pet>":{"<文本>":"<sha1>.wav"}}}
· VoiceClient.speak 变为四层：① 预生成台词包（assets，命中即播，不联网）
  → ② 联网缓存 → ③ 电脑 F5 → ④ 交回系统 TTS；
  新增 packed() 读索引并解到 cacheDir 播放，日志写「命中预生成台词 …（不联网）」。
· 生成器 dev/scripts/gen_voice_pack.py（在桌面仓）：台词表 → F5 /infer（带 pet 选音色）
  → 存 wav + 索引，并逐个校验 RIFF/时长。

意义：设置页「测试电脑语音」这类固定台词**不插线也能出声**；配合热点/USB 时仍走 F5 原声。
真机：已装机（lastUpdateTime 16:58:33）。台词包命中与离线播放的日志验收在下一轮补。
"""
p1 = os.path.join(MAP, "_msg_voicepack.txt")
io.open(p1, "w", encoding="utf-8", newline="\n").write(MSG1)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r1 = subprocess.run(["git", "-C", CHAT, "commit", "-F", p1], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("手机仓:", (r1.stdout or r1.stderr or "").splitlines()[0][:120])

MSG2 = """feat(stt): api.py 新增 POST /stt —— 手机录音借用桌面端 faster-whisper large-v3

用户要求：STT 效果一般，学 QQ 那边怎么做，现成能抄则抄。

调研结果：桌面端（QQ 线）的 STT 是 tool/stt.py + faster-whisper **large-v3**，
权重已在本地 models/stt/hub（2948 MB），无需任何下载。手机端目前只有 sherpa 14M（tiny 级）。
⇒ 最小改动：给 api.py 加 POST /stt，收原始 WAV 字节 → 复用 tool/stt.py 的 transcribe_full()
   → 返回 {"text","ms","engine"}。手机连得上电脑时改走这条路，质量直接对齐桌面端。

实现要点（都踩过）：
  · 模型必须**只加载一次**：最初每次请求都用 importlib 重新执行 tool/stt.py，
    等于每条都重建模型 → 单条 23~37 秒；改为模块级单例 + 启动后台预热后降到 10 秒级。
  · api.py 需要 import time（第一版漏了 → 500 NameError）。
  · 用 asyncio.to_thread 跑识别，不阻塞事件循环。

实测（用预生成台词当标准答案，5 条）：相似度 0.71~0.93（平均 0.83，差异都是标点/语气词，
如「你回来啦」→「你回来了」），质量可用。

⚠ 已知瓶颈（下一轮解决）：nvidia-smi 显示 6141 MiB 显存已用 5668 MiB（F5 等占满），
   large-v3 的 float16（约 3GB）装不下 → tool/stt.py 回落到 CPU int8 → 单条约 10 秒。
   两条路：① 下载 small/medium（体积约束已取消）走 GPU；② 做显存仲裁（STT 时让 F5 让出显存），
   即规划文档 03/ADR 里"6GB 装不下两件事，TTS 与识图排队"那条。
"""
p2 = os.path.join(MAP, "_msg_stt.txt")
io.open(p2, "w", encoding="utf-8", newline="\n").write(MSG2)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
r2 = subprocess.run(["git", "-C", MAIN, "commit", "-F", p2], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("桌面仓:", (r2.stdout or r2.stderr or "").splitlines()[0][:120])

for name, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True).stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"],
                        capture_output=True, text=True).stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (name, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
print()
print("服务状态（给用户参考）：")
for p in (8765, 9881, 28565):
    r = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
    hit = [l for l in r.splitlines() if ":%d " % p in l and "LISTENING" in l]
    print("   %d: %s" % (p, "在听 ✓" if hit else "没在听 ✗"))
