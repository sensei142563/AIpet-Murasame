# -*- coding: utf-8 -*-
"""查两件"丢失"的东西：
  ① 诺瓦（pets/noir）的头像为什么变成乱码 —— 看文件现状 + 谁在什么时候改的
  ② "沫子的日常"（视频主题）去哪了 —— 全仓 + git 历史（含已删除文件）里找"沫子"
"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"


def sh(args, cwd=ROOT):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return (r.stdout or "") + (r.stderr or "")


print("=== ① pets/ 下有哪些角色 ===")
pets = os.path.join(ROOT, "pets")
for d in sorted(os.listdir(pets)):
    p = os.path.join(pets, d)
    if os.path.isdir(p):
        print("   %s" % d)

print()
print("=== ② 诺瓦是哪个目录？（找名字含 诺瓦 / nova / noir 的）===")
for d in sorted(os.listdir(pets)):
    p = os.path.join(pets, d)
    if not os.path.isdir(p):
        continue
    pj = os.path.join(p, "pet.json")
    if os.path.isfile(pj):
        try:
            t = io.open(pj, encoding="utf-8", errors="replace").read()
        except Exception:
            t = ""
        nm = ""
        for line in t.split("\n")[:30]:
            if '"name"' in line or '"display_name"' in line:
                nm += line.strip()[:60] + " "
        if "诺" in t or "nova" in d.lower() or "noir" in d.lower():
            print("   %-12s %s" % (d, nm[:90]))
    # 头像文件
    for cand in ("avatar.png", "avatar.jpg", "avatar.webp", "head.png", "icon.png"):
        fp = os.path.join(p, cand)
        if os.path.isfile(fp):
            print("        %s  %d 字节" % (cand, os.path.getsize(fp)))

print()
print("=== ③ pets/noir 目录内容 + pet.json 的 name 字段 ===")
noir = os.path.join(pets, "noir")
if os.path.isdir(noir):
    for dp, dn, fn in os.walk(noir):
        for f in sorted(fn):
            fp = os.path.join(dp, f)
            print("   %-52s %9d 字节" % (fp.replace(noir + os.sep, "")[:52], os.path.getsize(fp)))
    pj = os.path.join(noir, "pet.json")
    if os.path.isfile(pj):
        raw = io.open(pj, "rb").read()
        print()
        print("   pet.json 原始字节前 200：", raw[:200])
        try:
            print("   utf-8 解码：", raw.decode("utf-8")[:200])
        except Exception as e:
            print("   utf-8 解码失败 ✗", e)
            print("   gbk 解码：", raw.decode("gbk", "replace")[:200])

print()
print("=== ④ pets/noir 的提交历史（谁改的）===")
print(sh(["git", "log", "--oneline", "-12", "--", "pets/noir"]))

print()
print("=== ⑤ 全仓搜 '沫子'（工作区）===")
hits = 0
for dp, dn, fn in os.walk(ROOT):
    if any(x in dp for x in ("\\.git", "\\runtime", "\\GPT-SoVITS", "\\_internal", "\\build",
                             "\\.venv", "\\NapCat", "\\__pycache__", "\\F5-TTS_Models")):
        continue
    for f in fn:
        fp = os.path.join(dp, f)
        try:
            if os.path.getsize(fp) > 8 * 1024 * 1024:
                continue
            t = io.open(fp, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        if "沫子" in t or "沫子的日常" in t:
            print("   命中：", fp.replace(ROOT + os.sep, ""))
            hits += 1
            if hits > 20:
                break
print("   （命中 %d 处）" % hits)

print()
print("=== ⑥ git 历史里搜 '沫子'（含已删除文件）===")
print("   --- 提交信息里 ---")
print(sh(["git", "log", "--all", "--oneline", "--grep=沫子", "-i"])[:1200])
print("   --- 历史文件路径里 ---")
print(sh(["git", "log", "--all", "--diff-filter=AD", "--name-only", "--pretty=format:"])[:400] and
      "\n".join([l for l in sh(["git", "log", "--all", "--diff-filter=AD", "--name-only",
                                "--pretty=format:"]).split("\n") if "沫" in l][:30]))
print("   --- 历史内容里（pickaxe）---")
r = sh(["git", "log", "--all", "--oneline", "-S沫子", "--", "."])
print(r[:1500] if r.strip() else "   （没有）")
