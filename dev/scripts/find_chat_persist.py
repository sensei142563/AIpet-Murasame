# -*- coding: utf-8 -*-
"""定位聊天/记忆的持久化实现（按函数名与文件名搜索，而不是猜路径）。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
SRC = os.path.join(PET, "chatter", "app/src/main/java/com/aipet/murasame")

print("=== 定义了聊天会话存取的文件 ===")
for base, dirs, files in os.walk(SRC):
    for f in files:
        if not f.endswith(".kt"):
            continue
        fp = os.path.join(base, f)
        body = io.open(fp, encoding="utf-8", errors="replace").read()
        if re.search(r"fun (save|load|delete)\w*\(\s*ctx[^)]*petId", body) or "ChatSession" in body:
            fns = re.findall(r"fun (\w+)\(([^)]{0,80})\)", body)
            io_lines = [i + 1 for i, l in enumerate(body.split("\n"))
                        if re.search(r"writeText|readText|outputStream|renameTo|\.tmp", l)]
            print("   %-46s %6d B  I/O 行 %s" % (os.path.relpath(fp, SRC), len(body), io_lines[:8]))
            print("      函数：%s" % ", ".join(n for n, _ in fns[:14]))

print()
print("=== 是否有任何地方用了原子写（tmp + rename/replace）===")
found = False
for base, dirs, files in os.walk(SRC):
    for f in files:
        if not f.endswith(".kt"):
            continue
        fp = os.path.join(base, f)
        body = io.open(fp, encoding="utf-8", errors="replace").read()
        if re.search(r"renameTo|os\.replace|Files\.move", body):
            for i, l in enumerate(body.split("\n"), 1):
                if re.search(r"renameTo|os\.replace|Files\.move", l):
                    print("   %-40s %4d| %s" % (os.path.relpath(fp, SRC), i, l.strip()[:110]))
            found = True
if not found:
    print("   ✗ 手机端没有任何原子写（tmp+rename）—— 写到一半被杀会截断文件")

print()
print("=== 写文件的调用点（writeText / outputStream）===")
for base, dirs, files in os.walk(SRC):
    for f in files:
        if not f.endswith(".kt"):
            continue
        fp = os.path.join(base, f)
        body = io.open(fp, encoding="utf-8", errors="replace").read()
        for i, l in enumerate(body.split("\n"), 1):
            if re.search(r"writeText\(|\.outputStream\(\)", l):
                print("   %-38s %4d| %s" % (os.path.relpath(fp, SRC), i, l.strip()[:120]))
