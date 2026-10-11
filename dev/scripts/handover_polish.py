# -*- coding: utf-8 -*-
"""改进未验证项的提取：按句子取、去重、注明来源提交；重新生成文档并提交。"""
import io
import os
import re
import subprocess
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
G = os.path.join(MAIN, "dev", "scripts", "make_handover.py")

t = io.open(G, encoding="utf-8").read().replace("\r\n", "\n")
old = '''unverified = []
for repo, label in ((CHAT, "手机仓"), (MAIN, "桌面仓")):
    log = sh(["git", "-C", repo, "log", "-60", "--format=%h%x09%s%x09%b"])
    for line in log.split("\\n"):
        if "未验" in line or "需上机" in line or "无法在 JVM 单测" in line:
            s = re.sub(r"\\s+", " ", line.strip())
            if len(s) > 20 and s not in unverified:
                unverified.append(s[:200])'''
new = '''# 未验证项：按**句子**提取（提交正文整段捞进来会出现"三、诚实标注：…"这种碎片），
# 再去重，并保留来源提交号，便于回溯。
KEYS = ("未验", "需上机", "无法在 JVM 单测", "上机确认")
unverified = []
seen = set()
for repo, label in ((CHAT, "手机仓"), (MAIN, "桌面仓")):
    log = sh(["git", "-C", repo, "log", "-80", "--format=%h%x1f%s%x1f%b%x1e"])
    for rec in log.split("\\x1e"):
        parts = rec.split("\\x1f")
        if len(parts) < 3:
            continue
        h, subj, body = parts[0].strip(), parts[1].strip(), parts[2]
        for sent in re.split(r"[。；\\n]", subj + "。" + body):
            s = re.sub(r"\\s+", " ", sent).strip(" -·\\t")
            if not s or len(s) < 12:
                continue
            if not any(k in s for k in KEYS):
                continue
            s = re.sub(r"^[（(【\\[]?[一二三四五六七八九十0-9]+[）)】\\].、:：]?\\s*", "", s)
            key = s[:40]
            if key in seen:
                continue
            seen.add(key)
            unverified.append((h, s[:180]))'''
if old in t:
    t = t.replace(old, new, 1)
    print("✓ 提取逻辑改为按句子 + 去重 + 带来源提交")
else:
    print("⚠ 提取段锚点未命中")

# 渲染处同步（unverified 现在是 (hash, text) 元组）
t = t.replace('''if unverified:
    for u in unverified[:20]:
        L.append("- %s" % u)''',
              '''if unverified:
    for h, u in unverified[:16]:
        L.append("- `%s` %s" % (h, u))''', 1)
io.open(G, "w", encoding="utf-8", newline="\n").write(t)

print()
print("=== 重新生成文档 ===")
r = subprocess.run([sys.executable, "-u", G], capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=600, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
out = (r.stdout or "") + (r.stderr or "")
for l in out.split("\n"):
    if re.search(r"已生成|单测：|验收项|未验证项检索|✗|Error", l):
        print("   " + l.strip()[:160])

DOC = os.path.join(MAIN, "dev", "docs", "交接清单-2026-10.md")
txt = io.open(DOC, encoding="utf-8").read()
i = txt.find("## 四、")
j = txt.find("## 五、")
print()
print("=== 新的第四节 ===")
print(txt[i:j] if i > 0 and j > i else "(未找到)")

print("=== 提交 ===")
MSG = """docs(handover): 未验证项改为按句子提取（去碎片、去重、带来源提交号）

第一次生成的第四节把提交正文整段捞了进来，出现"三、诚实标注：…"这类碎片。
改为：按句号/分号/换行切句 → 只保留含关键词（未验/需上机/上机确认/无法在 JVM 单测）的**完整句**
→ 去重（按前 40 字）→ 每条带来源提交短号，便于回溯。上限 16 条。
"""
p = os.path.join(MAIN, "dev", "merge-map", "_msg_handover2.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:140])
n = subprocess.run(["git", "-C", MAIN, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", MAIN, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  桌面仓：未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
