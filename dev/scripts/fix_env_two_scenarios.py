# -*- coding: utf-8 -*-
"""按主人澄清更正注释与文档：
   虚拟环境 = **发布给用户**用的（装机版装 venv）+ **协作者**也在用 venv；
   **咱们俩本地开发**一直用全局 Python。
   ⇒ run.py 里"用 venv"的逻辑对发布场景是**对的**，不要改。
"""
import io
import os
import py_compile
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
RUN = os.path.join(ROOT, "run.py")
DOC = os.path.join(ROOT, "docs", "本机环境约定-不用虚拟环境.md")

# ---------- ① 更正 run.py 顶部那段注释 ----------
t = io.open(RUN, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
OLD_HEAD = "# ⚠⚠⚠ 重点：本机的「虚拟环境」约定（2026-10-14 主人明确 + 本机实测）"
NEW_HEAD = "# ⚠⚠⚠ 重点：关于「虚拟环境」——**两种场景，别混为一谈**（2026-10-14 主人澄清）"
if OLD_HEAD in t:
    t = t.replace(OLD_HEAD, NEW_HEAD, 1)
    print("✓ ① 标题已改")

# 把「主人原话/结论」那一段整体换成正确版本
import re  # noqa: E402
old_block = re.search(r"# ⚠⚠⚠ 重点：关于「虚拟环境」[\s\S]*?# ═{20,}\n", t)
NEW_BLOCK = """# ⚠⚠⚠ 重点：关于「虚拟环境」——**两种场景，别混为一谈**（2026-10-14 主人澄清）
#
#   ① **发布给用户**：装机版会**装一个虚拟环境**（runtime\\venv），依赖装在里面。
#      ⇒ 所以本文件里 _ensure_project_python / _project_python / _f5tts_venv_python
#        三个函数"优先用 runtime\\venv"的逻辑，**对发布场景是对的，不要改**。
#   ② **协作者**：他自己的机器上也是**虚拟环境**（依赖装在 venv 里）。
#      ⇒ 这就是为什么"他那边能跑、咱们这边不行" —— 环境不同，不是代码对错。
#   ③ **咱们俩本地开发**：一直用**全局 Python 310**
#      （C:\\Users\\ASUS\\AppData\\Local\\Programs\\Python\\Python310\\python.exe），
#      依赖都装在**全局** site-packages 里。
#      ⇒ **本机这份 runtime\\venv 是残缺的**：实测 126 个包，全局有 390 个，
#        「全局有、venv 没有」= **273 个**（含 f5-tts / cn2an / edge-tts / datasets …）。
#        ⇒ 本地跑时若走到 venv，凡是依赖那 273 个的功能都会报 No module named。
#
#   ✅ 实用判断法（照这个来就不会错）：
#      · 要**复现用户/协作者的环境**（测装机版行为） → 用 runtime\\venv；
#      · 要**本地开发/调试/录素材**                     → 用全局 Python 310；
#      · 起**需要新依赖**的子进程（如 F5-TTS）时，**先探测谁能 import，再用探到的那个**，
#        不要把 venv 写死（2026-10-14 的 F5-TTS 事故就是这么修的）。
#
#   📄 详细说明：docs/本机环境约定-不用虚拟环境.md
# ══════════════════════════════════════════════════════════════════════════════
"""
if old_block:
    t = t[:old_block.start()] + NEW_BLOCK + t[old_block.end():]
    print("✓ ① 注释正文已换成两种场景版本")
else:
    print("· ① 没匹配到原注释块（可能已改）")

# 三个函数的指针也改一下口径
t = t.replace(
    "    # ⚠ 本机约定见文件顶部「虚拟环境」注释：**本机不用 venv**；\n"
    "    #   这个函数仍会把解释器切到 runtime\\venv（历史行为，暂不改，改了有崩的风险）。",
    "    # ⚠ 见文件顶部「虚拟环境」注释：venv 是**发布/协作者**的场景；\n"
    "    #   咱们本地开发用全局 Python（本机 venv 残缺，缺 273 个包）。此逻辑保留。")
t = t.replace(
    "    # ⚠ 本机约定见文件顶部：**本机不用 venv**（依赖在全局）。此函数保留历史行为。",
    "    # ⚠ 见文件顶部：venv 面向**发布/协作者**；本地开发用全局 Python。此逻辑保留。")
t = t.replace(
    "    # ⚠ 本机约定见文件顶部：**本机不用 venv**。\n"
    "    #   名字虽然叫 venv，但 2026-10-14 起 F5-TTS 已改为用**探测到的**解释器\n"
    "    #   （见 start_f5tts_api），不再无条件用它。",
    "    # ⚠ 见文件顶部：venv 面向**发布/协作者**。\n"
    "    #   注意：2026-10-14 起 F5-TTS 已改为用**探测到的**解释器（见 start_f5tts_api），\n"
    "    #   不再无条件用它 —— 因为本机 venv 缺 f5_tts。")
io.open(RUN, "w", encoding="utf-8", newline="\n").write(t)
try:
    py_compile.compile(RUN, doraise=True)
    print("✓ ① py_compile OK")
except Exception as e:
    print("✗ py_compile:", e)
    sys.exit(1)

# ---------- ② 重写文档 ----------
DOC_TEXT = """# 本机环境约定：**虚拟环境 vs 全局 Python**（2026-10-14 主人澄清）

> 这份文档存在的唯一目的：**别再搞混"到底用哪个 Python"**。
> 起因：F5-TTS 长文本语音起不来（`No module named 'f5_tts'`），查半天，
> 根因是"探测到全局能用、启动时却回去用 `runtime\\venv`"。

## 一、两种场景，别混为一谈（主人原话）

> 「因为**给用户是装虚拟环境**的，**咱们一直是本地**，**包括协作者也是虚拟环境**。」

| 场景 | 用哪个 Python | 说明 |
|---|---|---|
| **发布给用户**（装机版） | **虚拟环境** `runtime\\venv` | 安装包会建 venv，依赖装在里头。所以 `run.py` 里"优先用 venv"的逻辑**对发布是对的，不要改** |
| **协作者** | **虚拟环境** | 他自己机器上也是 venv ⇒ **这就是"他那边能跑、咱们这边不行"的原因**（环境不同，不是代码对错） |
| **咱们俩本地开发** | **全局 Python 3.10** | `C:\\Users\\ASUS\\AppData\\Local\\Programs\\Python\\Python310\\python.exe`；依赖都在全局 site-packages |

## 二、本机 venv 是**残缺的**（实测数据）

```
全局 Python：390 个包          runtime\\venv：126 个包
「全局有、venv 没有」= 273 个，含：
   f5-tts / cn2an / cached_path / edge-tts / budoux / fast-langdetect /
   datasets / bigvgan / encodec / auraloss / aliyun-* / boto3 / transformers 相关 …
```
⇒ **本地**跑时若走到 venv，凡是用到那 273 个的功能都会报 `No module named 'xxx'`。
（F5-TTS 就是其中一个；日志里那句"需要 pip install cn2an"也是同一个病。）

## 三、✅ 实用判断法（照这个来就不会错）

1. 要**复现用户/协作者的环境**（测装机版行为） → 用 `runtime\\venv`；
2. 要**本地开发 / 调试 / 录素材** → 用**全局 Python 310**；
3. 起**需要新依赖**的子进程（如 F5-TTS）时 → **先探测谁能 import，再用探测到的那个**，
   **不要把 venv 写死**。（`start_f5tts_api` 2026-10-14 就是这么修的：
   `f5_py = _find_f5tts_python()` 之后必须用 `f5_py`。）

## 四、排查同类问题的固定套路（三步）

```bash
# ① 谁在跑？看报错堆栈里的路径，或看进程命令行
# ② 这个解释器到底有没有那个包？
<python> -c "import importlib.util as u; print(u.find_spec('包名'))"
# ③ 换个解释器试试（本机多半全局那个有）
python -c "import 包名; print('OK')"
# ④ 一条命令看两个环境差在哪：
python dev/scripts/compare_envs.py
```

**装包前先 `--dry-run`**：`f5-tts` 带依赖安装会拉 ~70 个包
（transformers 5.x 大版本跳跃 + gradio/wandb/datasets…），有砸坏现有链路的风险。
那次就是 dry-run 救回来的。

## 五、历次"装错环境 / 对错对象"事故

| 时间 | 症状 | 真因 |
|---|---|---|
| 2026-09-30 | 日志说「未检测到 f5_tts 库」，但用户明明装了 | f5_tts 装在系统 Python，项目却跑在 venv |
| 2026-10-01 | ArcFace 加载失败、回退三哈希 | `onnxruntime`/`onnx` 只装在 `.venv` |
| 2026-10-14 | F5-TTS `No module named 'f5_tts'` | 探测选了全局，启动却写死 venv（**已修**） |
| 2026-10-14 | GPT-SoVITS 每次预载被白重启 | `data/tts_model.json` 里 gpt/sovits 标签互换（同属"对错对象"） |
"""
io.open(DOC, "w", encoding="utf-8", newline="\n").write(DOC_TEXT)
print("✓ ② 文档已按两种场景重写")

MSG = """docs(env): 更正为「两种场景」—— venv 是发布/协作者用的，咱们本地用全局 Python

## 主人澄清（关键）
"因为**给用户是装虚拟环境**的，**咱们一直是本地**，**包括协作者也是虚拟环境**。"

⇒ 之前我理解反了一半：
- `run.py` 里"优先用 runtime\\venv"的逻辑，**对发布场景是对的** ⇒ **不该改默认行为**；
- **协作者也用 venv** ⇒ 这正是"他那边能跑、咱们这边不行"的原因（环境不同，不是代码对错）；
- **咱们俩本地开发**一直用**全局 Python 310**；本机那份 venv 是**残缺的**。

## 实测数据（支持这个判断）
```
全局 Python：390 个包      runtime\\venv：126 个包
「全局有、venv 没有」= **273 个**：f5-tts / cn2an / cached_path / edge-tts / budoux /
fast-langdetect / datasets / bigvgan / encodec / auraloss / aliyun-* / boto3 …
```
⇒ 本地若走到 venv，凡是用到这些的功能都会 `No module named`（F5-TTS 就是其中之一）。

## 改了哪些
1. `run.py` 顶部注释**重写为"两种场景"**（发布=venv / 协作者=venv / 本地=全局），
   并明确写上"**发布场景的逻辑不要改**"，避免以后有人把 venv 逻辑"修"没了；
2. 三个函数的指针同步更正口径；
3. `docs/本机环境约定-不用虚拟环境.md` 重写：两种场景对照表、实测包差、
   **实用判断法**（复现用户环境用 venv；本地开发/录素材用全局；
   起需要新依赖的子进程先探测再启动）、排查三步走、历次事故表；
4. 新增 `dev/scripts/compare_envs.py`（一条命令看两个环境差在哪）。

## 撤回
上一条我给的 A/B/C（把默认行为翻成全局）**撤回** —— 那是基于"本地也不用 venv"的误判；
venv 对发布与协作者是**必需**的。
"""
p = os.path.join(ROOT, "dev", "merge-map", "_msg_env2.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
import subprocess  # noqa: E402
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("✓ ③ 提交：", (rc.stdout or rc.stderr or "").splitlines()[0][:140])
