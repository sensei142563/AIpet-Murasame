# -*- coding: utf-8 -*-
"""提交：修 F5-TTS 启动用错解释器的 bug；并跑自检。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

MSG = """fix(longtext): F5-TTS 启动用错解释器 —— 探测找到了能用的，启动时却回去用 venv

## 现象（用户 2026-10-14 贴的日志）
```
[F5TTS] pypinyin 词典注册失败（不影响运行）: No module named 'pypinyin'
ModuleNotFoundError: No module named 'f5_tts'
RuntimeError: f5-tts 未安装: No module named 'f5_tts'
[F5TTS] 模型预加载失败: f5-tts 未安装: No module named 'f5_tts'
```

## 根因（一句话）
`run.py:656` 用 `_find_f5tts_python()` **探测出**了能 import f5_tts 的解释器（系统 Python），
`run.py:668` 启动时却写的是 **`_f5tts_venv_python()`** —— 而那个函数（第 100-111 行）
**就是硬编码返回 `runtime\\venv\\Scripts\\python.exe`**。
⇒ 探测结果被丢掉，永远用缺失 f5_tts 的 venv ⇒ 必然失败。
（与今天反复出现的那类问题同源：**算出了正确的值，却用了另一个**。）

## 实测证据
```
runtime\\venv   → f5_tts 缺、pypinyin 缺（torch 2.14.0+cu130）
全局 Python310  → f5_tts 有、pypinyin 有（torch 2.11.0+cu128）
   `from f5_tts.api import F5TTS` ⇒ OK ✓
磁盘：<global>\\Lib\\site-packages\\f5_tts* 存在；venv 里没有
```

## 修法
`run.py:668` 改为 `[f5_py, "-m", "longtext.f5tts_server"]`（用探到的那个），并加注释说明为什么。

## 验证（真起了一次）
```
用全局 python 起 longtext.f5tts_server ⇒ **第 10 秒监听到 9881** ✓
测试进程已停、9881 已释放 ✓
pypinyin 的警告也会随之消失（全局那个有 pypinyin）
```

## 走过的弯路（如实记录）
先按"缺什么装什么"往 venv 装了 `f5-tts` / `pypinyin` / `cached_path`，
但 **dry-run 一看**：带依赖装 f5-tts 会拉 ~70 个包（transformers **5.19.0** 大版本跳跃、
gradio / wandb / datasets / google-cloud-storage …），**有砸坏现有链路的风险**。
⇒ 立刻把这三个包从 venv **卸掉**（venv 已恢复原状），改走"用系统 Python"这条低风险路。
（torch 全程未被改动：装前装后都是 2.14.0+cu130。）

## 同源隐患（未改，先记）
`run.py:519` 也用 `_f5tts_venv_python()` 跑 `download.py`（模型下载器）。
下载器不需要 f5_tts 本身，大概率没问题；但如果哪天报错，就是同一处该修。
"""
p = os.path.join(MAP, "_msg_f5tts.txt")
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

print()
print("=== 全量自检（改了 run.py）===")
r = subprocess.run([os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe"),
                    os.path.join(ROOT, "tests", "run_all.py")],
                   cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=1800)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n")[-4:]:
    print("   " + l.strip()[:124])
