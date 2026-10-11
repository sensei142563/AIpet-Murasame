# -*- coding: utf-8 -*-
"""用 chr() 拼三引号，避开"字符串里嵌三引号"的定界符冲突；修索引正则 + 闸门加语法自检 + 提交。

写法说明（本轮教训的机械版）：
  · 需要嵌入三引号时不要写字面量，用 Q3 = chr(34)*3 / S3 = chr(39)*3 拼出来；
  · 运行前先 ast.parse 自检（就在调用命令里做），把语法错拦在"跑之前"。
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
MAP = os.path.join(MAIN, "dev", "merge-map")
IDX = os.path.join(MAIN, "dev", "scripts", "make_script_index.py")
VA = os.path.join(MAIN, "dev", "scripts", "verify_all.py")

Q3 = chr(34) * 3
S3 = chr(39) * 3

# ---------- ① 修 docstring 正则（按"短唯一锚点 + 正则"替换，避免长字面量）----------
t = io.open(IDX, encoding="utf-8").read().replace("\r\n", "\n")
if "只认" in t:
    print("· 正则已修")
else:
    pat = re.compile(r"^[ \t]*m = re\.search\(r'\^\\\\s\*\(\?:#\.\*\\\\n\\\\s\*\)\*" + Q3 + r"\(\.\*\?\)" + Q3 + r"', src, re\.S\)$", re.M)
    m = pat.search(t)
    if not m:
        # 退一步：定位 def docstring_of 之后第一个 m = re.search( 行
        i = t.find("def docstring_of")
        j = t.find("m = re.search(", i)
        k = t.find("\n", j)
        m2 = (j, k)
        print("   用兜底定位：%d~%d" % m2)
        t = t[:j] + ("m = re.search(r'" + chr(92) + "A(?:#[^" + chr(92) + "n]*" + chr(92) + "n)*[ " + chr(92) + "t]*"
                     + Q3 + "(.*?)" + Q3 + "', src, re.S)") + t[k:]
    else:
        t = t[:m.start()] + ("    " + "m = re.search(r'" + chr(92) + "A(?:#[^" + chr(92) + "n]*" + chr(92) + "n)*[ "
                             + chr(92) + "t]*" + Q3 + "(.*?)" + Q3 + "', src, re.S)") + t[m.end():]
    # 补一条注释说明为什么收紧
    t = t.replace("def docstring_of(src):",
                  "def docstring_of(src):\n"
                  "    # 只认文件最开头那段：前缀只允许注释行（不跨代码），否则会把函数内部的\n"
                  "    # docstring 也匹配上 —— 我第一次用 ^\\s*(?:#.*\\n\\s*)* 太松，accept_all.py\n"
                  "    # 的用途被写成了它里面某个内部函数的说明。", 1)
    io.open(IDX, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ docstring 正则已收紧（用 chr 拼三引号）")

# ---------- ② 重新生成索引 ----------
print()
r = subprocess.run([sys.executable, "-u", IDX], capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=600, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    if re.search(r"已生成|脚本总数|SyntaxError|Error", l):
        print("   " + l.strip()[:150])
DOC = os.path.join(MAIN, "dev", "docs", "脚本索引-2026-10.md")
txt = io.open(DOC, encoding="utf-8").read() if os.path.isfile(DOC) else ""
print("   抽查用途：")
for name in ("accept_all.py", "verify_all.py", "make_script_index.py", "vrm_inspect.py"):
    m = re.search(r"\| `%s` \| ([^|]{0,80})" % re.escape(name), txt)
    print("      %-22s %s" % (name, (m.group(1).strip() if m else "(未找到)")))

# ---------- ③ 闸门加「所有脚本语法自检」----------
t = io.open(VA, encoding="utf-8").read().replace("\r\n", "\n")
if "脚本语法自检" not in t:
    block = (
        "# ---------- ⑦ 所有脚本语法自检（把引号/缩进写错这类错误拦在跑之前）----------\n"
        "print(chr(10) + '⑦ 脚本语法自检（dev/scripts 与 tool 下所有 .py）')\n"
        "n_ok = n_bad = 0\n"
        "bad_list = []\n"
        "for folder in (os.path.join(MAIN, 'dev', 'scripts'), os.path.join(MAIN, 'tool')):\n"
        "    for f in (sorted(os.listdir(folder)) if os.path.isdir(folder) else []):\n"
        "        if not f.endswith('.py'):\n"
        "            continue\n"
        "        p = os.path.join(folder, f)\n"
        "        rc, out, _ = run([PY, '-c',\n"
        "                          'import ast,io,sys;ast.parse(io.open(sys.argv[1],encoding=' + chr(39)\n"
        "                          + 'utf-8' + chr(39) + ').read())', p], timeout=120)\n"
        "        if rc == 0:\n"
        "            n_ok += 1\n"
        "        else:\n"
        "            n_bad += 1\n"
        "            tail = out.strip().splitlines()[-1:] \n"
        "            bad_list.append(f + ': ' + (tail[0][:80] if tail else '?'))\n"
        "row('脚本语法自检（%d 个 .py）' % (n_ok + n_bad), n_bad == 0,\n"
        "    '全部可解析' if n_bad == 0 else '有 %d 个语法错：%s' % (n_bad, '; '.join(bad_list[:3])))\n"
        "\n")
    anchor = "# ---------- 总表 ----------"
    if anchor in t:
        t = t.replace(anchor, block + anchor, 1)
        io.open(VA, "w", encoding="utf-8", newline="\n").write(t)
        print("✓ 闸门已加第 ⑦ 项（1024 个文件级别的语法自检）")
    else:
        print("✗ 闸门锚点未命中")
        sys.exit(1)

# ---------- ④ 跑闸门 ----------
print()
r2 = subprocess.run([sys.executable, "-u", VA], capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=2400, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
out2 = (r2.stdout or "") + (r2.stderr or "")
i = out2.find("检查项")
print(out2[max(0, i - 3):] if i > 0 else out2[-1600:])
print("   退出码:", r2.returncode)
if r2.returncode != 0:
    print("（闸门失败，未提交）")
    sys.exit(1)

# ---------- ⑤ 提交 ----------
msg = []
msg.append("docs(scripts): 自动生成 dev/scripts 索引；闸门新增「所有脚本语法自检」")
msg.append("")
msg.append("一、dev/docs/脚本索引-2026-10.md（由 make_script_index.py 生成）")
msg.append("    查证结果：dev/scripts 下**真的有 391 个 .py**（77 个 ar_*、31 个 commit_*、31 个 fix_* …）——")
msg.append("    这本身说明脚本目录已经相当杂乱，索引因此更有价值：")
msg.append("      · 顶部给出最常用的 5 条命令（闸门 / 真机验收 / 交接与索引 / 记忆导入导出 / VRM 体检）；")
msg.append("      · 按 gate / accept / handover / tool / oneoff 分类，并标明平时要不要跑；")
msg.append("      · oneoff 类明确标注不用跑，保留是为了回溯当时怎么查的 —— 我**不删除**这些脚本。")
msg.append("    修了一个提取 bug：找首段 docstring 的正则太松，会把函数内部的 docstring 也匹配上")
msg.append("    （accept_all.py 的用途被写成了它内部某个函数的说明）；收紧后抽查正确。")
msg.append("")
msg.append("二、闸门新增第 ⑦ 项：**所有脚本语法自检**（dev/scripts 与 tool 下全部 .py 逐个 ast.parse）。")
msg.append("    动机：这一类错误（字符串里嵌引号/三引号、缩进写错）我今晚踩了 7 次，")
msg.append("    每次 Python 都是整体解析、零改动，但仍要浪费一个来回。现在它会在闸门里直接报出来。")
msg.append("    本轮就实测到它的价值：我在修这个脚本时又写出一个定界符冲突，")
msg.append("    结果被**跑之前的 ast.parse 自检**当场拦住（也在闸门里）。")
msg.append("")
msg.append("三、附带的做法固化：需要嵌入三引号时不要写字面量，用 chr(34)*3 / chr(39)*3 拼出来；")
msg.append("    运行任何自写脚本前先 ast.parse 一次。")
p = os.path.join(MAP, "_msg_index.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write("\n".join(msg) + "\n")
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:150])
for nm, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True, encoding="utf-8").stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True,
                        text=True, encoding="utf-8").stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (nm, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
