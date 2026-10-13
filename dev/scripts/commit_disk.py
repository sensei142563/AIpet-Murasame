# -*- coding: utf-8 -*-
"""提交：deck 定稿 + 体积审计脚本。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

MSG = """chore: deck 定稿（24 页）+ 体积审计脚本；顺带 git gc 回收 1.62 GB

## 主人问："为什么这个文件夹从 7GB 长到 34.8GB"
查了一遍（`dev/scripts/disk_audit.py`，实测 34.56 GB）：

| 目录 | 体积 | 占比 | 是什么 |
|---|---|---|---|
| GPT-SoVITS | 13.44 GB | 38.9% | 短语音整合包（含 torch/CUDA）+ 预训练模型 |
| F5-TTS_Models | 6.33 GB | 18.3% | 长语音；**装了 4 套权重** |
| runtime\\venv | 4.17 GB | 12.1% | torch + CUDA dll |
| models\\stt | 2.88 GB | 9.0% | faster-whisper-**large-v3** |
| .git | 2.51 GB | 7.3% | 松散对象 2.14 GiB（这一百多次提交攒的） |
| .venv | 1.81 GB | 5.2% | **第二套 venv** |
| NapCat | 1.46 GB | 4.2% | QQ 环境（含 0.29 GB 安装包） |
| dev | 1.12 GB | 3.2% | 含 dev\\tmp\\venv_junk 等临时物 |

⇒ **不是泄漏**：每一项都对应一个已经装上的功能（短语音/长语音/语音识别/QQ）。
   从 7GB 到 34.8GB 主要是"后来装了这些模型"。

## 立刻做的（安全，无需商量）
`git gc` —— 松散对象 7356 个 / 2.14 GiB 打包成 pack：
```
回收前 .git = 2.51 GB（loose 2.14 GiB，in-pack 368 MB）
回收后 .git = 0.88 GB（count 0，in-pack 10628，packs 2）
⇒ 省 1.62 GB；未推送提交仍是 155 条、HEAD 不变、工作区仅本次文件变动
```

## 可以安全回收、但需要主人点头的（我列了证据，没动手）
| 项 | 体积 | 依据 |
|---|---|---|
| F5-TTS 里多余的 **3 套**权重 | ~5.03 GB | 代码只用 `F5TTS_v1_Base`：`longtext/f5tts_server.py:159/210/220`、`build_launcher.py:454`；其余 `F5TTS_Base` / `F5TTS_Base_bigvgan` / `F5TTS_v1_Base_no_zero_init` 无人引用 |
| `__pycache__` | 0.49 GB | 6737 个目录，自动重建 |
| `dev\\tmp`（含 venv_junk） | 0.35 GB | 临时物 |
| NapCat 里的 QQ 安装包 | 0.29 GB | 已安装，安装包留着没用 |
| 合计 | **~6.16 GB** | 都不影响任何在用功能 |

## 需要商量、**不建议直接删**的
- **`.venv`（1.81 GB）**：**被 `build_launcher.py` 引用**（打包时"优先 .venv"，
  还 `--add-data .venv/Lib/site-packages/live2d/...`）—— 但 README 又说"本项目为全局 Python 310"。
  ⇒ 这是个**隐患**（打包可能用错环境），不是垃圾 ⇒ 建议先核对打包流程再决定。
- **`models\\stt`（2.88 GB）**：whisper-**large-v3**；换 medium 可省 ~1.4 GB，但识别质量会降。
- **`dev\\tts_model_cache`（0.30 GB）**：用途待确认。

## deck 定稿
主人关了 WPS 后：`Deck_24.pptx → Deck.pptx` ✓
核对：**24 页，24 页都有讲稿** ✓
"""
p = os.path.join(MAP, "_msg_disk.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:170])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
r = subprocess.run(["powershell", "-NoProfile", "-Command",
                    "(Get-ChildItem 'E:\\university\\order\\python\\pet\\AIpet-Murasame-main' "
                    "-Recurse -File -Force -ErrorAction SilentlyContinue | "
                    "Measure-Object -Property Length -Sum).Sum / 1GB"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
print("  当前项目总大小: %s GB" % (r.stdout or "").strip())
