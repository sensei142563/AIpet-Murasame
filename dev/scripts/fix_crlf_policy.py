# -*- coding: utf-8 -*-
"""固化今晚的发现：两仓行尾策略不同。给 normalize_crlf.py 加保险；写文档；提交。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
MAP = os.path.join(MAIN, "dev", "merge-map")

# ① 给 normalize_crlf.py 加保险：桌面仓 core.autocrlf=false/eol=lf 时拒绝转换
P = os.path.join(MAIN, "dev", "scripts", "normalize_crlf.py")
t = io.open(P, encoding="utf-8").read().replace("\r\n", "\n")
if "SAFETY_GUARD" not in t:
    t = t.replace('''def to_crlf(path):''',
                  '''def repo_policy(repo):
    """读仓库行尾策略。桌面仓实测 core.autocrlf=false + core.eol=lf ⇒ 仓库本体就是 LF。"""
    def cfg(k):
        r = subprocess.run(["git", "-C", repo, "config", k], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        return (r.stdout or "").strip()
    return cfg("core.autocrlf"), cfg("core.eol")


def safety_ok(repo, label):
    """SAFETY_GUARD：若仓库本体是 LF（autocrlf=false 且 eol=lf），把工作区转成 CRLF 会制造
    整文件翻动（实测桌面仓 1904 行差异）。所以这种仓库**拒绝转换**。"""
    ac, eol = repo_policy(repo)
    if ac.lower() in ("false", "") and eol.lower() == "lf":
        print("   [SKIP] %s：core.autocrlf=%s core.eol=%s ⇒ 仓库本体为 LF，"
              "转 CRLF 会造成整文件差异，已拒绝（这是实测教训）" % (label, ac or "(空)", eol))
        return False
    return True


def to_crlf(path):''', 1)
    t = t.replace('''print("=== 桌面仓 ===")''',
                  '''print("=== 桌面仓 ===")
if not safety_ok(MAIN, "桌面仓"):
    main_files = []
else:''', 1)
    io.open(P, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ normalize_crlf.py 已加 SAFETY_GUARD")

# ② 文档化
DOC = os.path.join(MAIN, "dev/docs", "行尾与编码纪律-2026-10.md")
io.open(DOC, "w", encoding="utf-8", newline="\n").write("""# 行尾与编码纪律（2026-10 实测）

本机 shell 是 **Windows PowerShell 5.1**（不是 pwsh 7），中文 Windows 下有一串固定翻车点。
本文只记**本项目实测确认过**的条目；通用条目见技能 `windows-powershell-traps`。

## 1. 两个仓库的行尾策略**不同**（实测）

| 仓库 | `core.autocrlf` | `core.eol` | 仓库本体 | 工作区现象 |
|---|---|---|---|---|
| 桌面 `AIpet-Murasame-main` | `false` | `lf` | **LF** | 转成 CRLF 会造成 **整文件翻动**（实测 `api.py` 839 行全变） |
| 手机 `chatter` | `true` | （空） | LF 存储、检出 CRLF | 转成 CRLF **无差异**（git 自动归一化，`diff --numstat` 为 0） |

**结论**：用 Python 改文件时统一写 **LF**（`io.open(..., "w", encoding="utf-8", newline="\\n")`）
是**正确且安全**的 —— 对桌面仓正是其本体格式，对手机仓由 git 归一化。
**不要**为了"统一成 CRLF"去批量转换（`dev/scripts/normalize_crlf.py` 已加 SAFETY_GUARD 拒绝这种仓库）。

判据（别只看 `--numstat`，它也受 git 归一化影响）：
```powershell
git -C <repo> config core.autocrlf ; git -C <repo> config core.eol
git -C <repo> diff --numstat        # 每文件 1~3 行才算正常
git -C <repo> diff -w --numstat     # 忽略空白后应为空 ⇒ 确认是纯行尾差异
python -c "d=open(r'文件','rb').read();print(d.count(b'\\r\\n'), d.count(b'\\n')-d.count(b'\\r\\n'))"
```

## 2. Python 的 stdout：控制台是 UTF-8，管道是 GBK（本会话踩 3 次）

- 真控制台：`sys.stdout.encoding == utf-8`，打印 ✓/✗/emoji 不崩（字形缺失只显示成 `�`）；
- **重定向/管道**：`cp936` ⇒ `UnicodeEncodeError: 'gbk' codec can't encode character`，
  而且会**打断进程**，看起来像"被验证的功能挂了"。
- 对策（每条自写脚本开头都加）：
  ```python
  import sys; sys.stdout.reconfigure(encoding="utf-8", errors="replace")
  ```
- **跨进程**同理：`subprocess.run(..., text=True, encoding="utf-8", errors="replace")`
  —— 漏写这个参数，父进程会拿 GBK 去解子进程的 UTF-8，或在子进程里直接抛 UnicodeDecodeError
  （本会话 `ast.parse` 核验脚本就是这么挂的）。

## 3. PowerShell 侧的三条硬规矩

1. **文本查询/替换一律用 Python 脚本**，不用 `powershell` 内联字符串：
   双引号串里放双引号、反引号被当转义符、`$` 被插值 —— 本会话为此浪费了 4 次调用。
2. **不要用 `| Select-Object -Last N` 收脚本输出**：它会截掉结论行，还会让退出码失真
   （技能 §11.3）。改为让脚本打印 `RESULT_xxx:` 行，并**看脚本自己的退出码**。
3. **复杂命令写成文件再跑**（`.py`），不用 `python -c @"..."@`。

## 4. 判据要选"不会撒谎"的那个

- 判接线是否生效：**看接口返回里的字段**（本轮就是靠 `/stt` 返回的 `vad` 字段仍是能量法文案，
  才发现 `analyze_smart` 没接上），不是看"编译通过"；
- 判代码插到哪：打印**带缩进的原文** + 从函数头数**花括号嵌套深度**；
- 判 CLAUDE 类断言：写**黄金值/互证**测试（如 ArGround 与 three.js 逐角 0.00px）。
""")
print("✓ 新增 dev/docs/行尾与编码纪律-2026-10.md")

# ③ 验证保险有效（在桌面仓跑应被拒绝）
print()
print("=== 验证 SAFETY_GUARD（桌面仓应被拒绝）===")
r = subprocess.run([sys.executable, "-u", P], capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=600)
out = (r.stdout or "") + (r.stderr or "")
for l in out.splitlines():
    if "SKIP" in l or "RESULT_CONVERTED" in l or "桌面仓" in l:
        print("   " + l.strip()[:150])

# ④ 提交
MSG = """docs(env): 实测两仓行尾策略不同；给 normalize_crlf 加保险；新增行尾与编码纪律文档

起因：按技能 windows-powershell-traps §14.1 的建议做自查，发现我改过的文件在工作区都是 LF-only，
于是写了个 normalize_crlf.py 想统一成 CRLF —— **结果差点制造事故**：

  桌面仓 core.autocrlf=false + core.eol=lf ⇒ 仓库本体就是 LF
     转 CRLF 后 git diff --numstat 显示 api.py 839/839、合计 **1904 行** 全变（整文件翻动）
     ⇒ 已 `git checkout -- .` 回滚，仓库恢复干净（内容未变，diff -w 忽略空白后为空可证）
  手机仓 core.autocrlf=true ⇒ 转 CRLF 后 diff 为 **0 行**（git 自动归一化，无害）

结论（与技能默认假设相反，故必须记录）：
  · 我用 Python 改文件统一写 LF 的写法是**正确的** —— 对桌面仓正是本体格式，对手机仓被 git 归一化；
  · 不要为了"统一 CRLF"去批量转换。normalize_crlf.py 已加 SAFETY_GUARD：
    检测到 core.autocrlf=false 且 core.eol=lf 的仓库直接拒绝转换。

新增 dev/docs/行尾与编码纪律-2026-10.md，固化本会话实测的三类翻车：
  ① 两仓行尾策略不同的判据与处置；② Python stdout 控制台 UTF-8 / 管道 GBK（含跨进程必须显式
  encoding="utf-8"）；③ PowerShell 三条硬规矩（文本改动用 Python、别用 Select-Object -Last 收输出、
  复杂命令写文件）；④ 判据要选不会撒谎的那个（看接口字段而非"编译通过"）。
"""
p = os.path.join(MAP, "_msg_crlf.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("DESKTOP_COMMIT:", (rc.stdout or rc.stderr or "").splitlines()[0][:130])
n = subprocess.run(["git", "-C", MAIN, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", MAIN, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("RESULT_REPO: 未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
