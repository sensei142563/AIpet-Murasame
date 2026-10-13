# -*- coding: utf-8 -*-
"""① 写 docs/本机环境约定-不用虚拟环境.md（run.py 注释里指向它）
   ② README 加一小节指针
   ③ **关键排查**：venv 与全局 Python 的包差异 —— 找出"venv 缺、全局有"的包，
      因为项目默认跑在 venv 上，缺哪个就会在运行时炸（f5_tts 就是这么炸的）。
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")
GLOBAL = r"C:\Users\ASUS\AppData\Local\Programs\Python\Python310\python.exe"
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")

DOC = """# 本机环境约定：**不用虚拟环境**（2026-10-14 主人明确）

> 这份文档存在的唯一目的：**别再搞混"到底用哪个 Python"**。
> 起因：F5-TTS 长文本语音起不来（`No module named 'f5_tts'`），查了半天，
> 根因就是"探测到了全局 Python 能用、启动时却回去用 `runtime\\venv`"。

## 一、结论（以这段为准）

```
本机跑项目用：**全局 Python 3.10**
    C:\\Users\\ASUS\\AppData\\Local\\Programs\\Python\\Python310\\python.exe
依赖装在哪：**全局的 site-packages**
    （torch / torchaudio / soundfile / f5_tts / pypinyin / onnxruntime … 都在这里）

`runtime\\venv`：**历史遗留，包不全**，默认不要用它。
    （实测：它有 torch，但**没有** f5_tts、pypinyin —— 用了就报 No module named）
```

主人原话（两次都对得上）：
- 「**咱本地不用虚拟环境**」
- 「咱们都是**全局 Python**，都用 GPU 加速」

## 二、⚠ 与代码注释的矛盾（重要，别被带偏）

`run.py` 里有三个函数的注释说"**必须**用 `runtime\\venv`，否则会崩
（Windows 事件日志 MSVCP140 访问违规 / 抢 28565 端口）"：

| 函数 | 现状 |
|---|---|
| `_ensure_project_python()`（run.py:21） | 仍会把解释器**切到 venv** |
| `_project_python()`（run.py:82） | 拉子进程仍**默认 venv** |
| `_f5tts_venv_python()`（run.py:100） | 名字就叫 venv，仍返回 venv 路径 |

**那是历史上的情况**（当年依赖确实装在 venv 里）。现在反过来了：
依赖在全局，venv 反而缺包。

⇒ 处理原则：
1. **保留这三个函数的原行为**（直接改默认值有崩的风险，需要单独验证）；
2. 但**凡是需要新依赖（如 f5_tts）的子进程，必须用全局 Python**；
3. 调用处**不要重复写死 venv** —— 先探测"谁真能 import 这个库"，再用**探测到的那个**
   （`start_f5tts_api` 2026-10-14 就是这么修的：`f5_py = _find_f5tts_python()` 之后，
    启动必须用 `f5_py`，而不是 `_f5tts_venv_python()`）。

## 三、排查同类问题的固定套路（三步）

```bash
# ① 谁在跑？（看报错堆栈里的路径，或看进程命令行）
# ② 这个解释器到底有没有那个包？
<python> -c "import importlib.util as u; print(u.find_spec('包名'))"
# ③ 换个解释器试试（多半全局那个有）
python -c "import 包名; print('OK')"
```

**装包前一定要先 `--dry-run`**：`f5-tts` 带依赖安装会拉 ~70 个包
（transformers 5.x 大版本跳跃 + gradio/wandb/datasets…），**有砸坏现有链路的风险**。
那次就是 dry-run 救回来的（装前就把可疑的三个包从 venv 卸掉了）。

## 四、已知的"装错环境"事故（都是同一类）

| 时间 | 症状 | 真因 |
|---|---|---|
| 2026-09-30 | 日志说「未检测到 f5_tts 库」，但用户明明装了 | f5_tts 装在**系统 Python**，项目却跑在 venv |
| 2026-10-01 | ArcFace 加载失败、回退三哈希 | `onnxruntime`/`onnx` 只装在 `.venv` |
| 2026-10-14 | F5-TTS 服务 `No module named 'f5_tts'` | 探测选了全局，启动却写死 venv（本次已修） |
| 2026-10-14 | GPT-SoVITS 每次预载被白重启 | `data/tts_model.json` 里 gpt/sovits 标签互换（非环境问题，但同属"对错对象"） |

## 五、还有哪些包只在全局（自动体检）

`dev/scripts/compare_envs.py` 会把两个解释器的包列表比一遍，列出
「全局有、venv 没有」的包 —— 那些就是"项目跑在 venv 上时**随时会炸**"的隐患。
（本文件不写死名单，避免过期；跑一下脚本看最新结果。）
"""

p = os.path.join(ROOT, "docs", "本机环境约定-不用虚拟环境.md")
io.open(p, "w", encoding="utf-8", newline="\n").write(DOC)
print("✓ ① 已写 docs/本机环境约定-不用虚拟环境.md")

# ---------- ② README 指针 ----------
R = os.path.join(ROOT, "README.md")
t = io.open(R, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
PTR = ("\n> ⚠ **本机环境约定：不用虚拟环境** —— 项目跑在**全局 Python 3.10** 上，\n"
       "> `runtime\\venv` 是历史遗留且**包不全**。细节与排查套路见\n"
       "> [`docs/本机环境约定-不用虚拟环境.md`](docs/本机环境约定-不用虚拟环境.md)。\n")
if "本机环境约定" not in t:
    # 插在「## 📁 文件与数据位置（重要）」之前
    key = "## 📁 文件与数据位置（重要）"
    if key in t:
        t = t.replace(key, PTR.strip() + "\n\n" + key, 1)
        io.open(R, "w", encoding="utf-8", newline="\n").write(t)
        print("✓ ② README 已加指针")
    else:
        print("✗ ② README 锚点未命中")
else:
    print("· ② README 已有指针")

# ---------- ③ 写对比脚本并立刻跑一次 ----------
CMP = '''# -*- coding: utf-8 -*-
"""对比全局 Python 与 runtime\\venv 的包：列出「全局有、venv 没有」= 潜在炸弹。"""
import json
import os
import subprocess
import sys

ROOT = r"E:\\university\\order\\python\\pet\\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")
GLOBAL = r"C:\\Users\\ASUS\\AppData\\Local\\Programs\\Python\\Python310\\python.exe"
CODE = ("import json, importlib.metadata as m\\n"
        "d = {}\\n"
        "for dist in m.distributions():\\n"
        "    n = (dist.metadata['Name'] or '').strip()\\n"
        "    if n:\\n"
        "        d[n.lower()] = dist.version\\n"
        "print(json.dumps(d))\\n")


def pkgs(py):
    r = subprocess.run([py, "-c", CODE], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=600)
    try:
        return json.loads((r.stdout or "").strip().splitlines()[-1])
    except Exception:
        return {}


g = pkgs(GLOBAL)
v = pkgs(VENV)
print("   全局包数 = %d    venv 包数 = %d" % (len(g), len(v)))
only_g = sorted(set(g) - set(v))
only_v = sorted(set(v) - set(g))
print()
print("=== 全局有、venv 没有（%d 个）—— 项目跑在 venv 上时随时会炸 ===" % len(only_g))
for n in only_g:
    print("   %-34s %s" % (n, g[n]))
print()
print("=== venv 有、全局没有（%d 个）===" % len(only_v))
for n in only_v:
    print("   %-34s %s" % (n, v[n]))
'''
cp = os.path.join(ROOT, "dev", "scripts", "compare_envs.py")
io.open(cp, "w", encoding="utf-8", newline="\n").write(CMP)
print()
print("=== ③ 立刻跑一次环境对比 ===")
r = subprocess.run([sys.executable, cp], cwd=ROOT, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", env=ENV, timeout=900)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n")[:60]:
    print("   " + l[:130])
