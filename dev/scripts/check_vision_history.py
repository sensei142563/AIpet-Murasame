# -*- coding: utf-8 -*-
"""① 视觉模型名的变更史（主人说"之前让我改成新模型" ⇒ 查是不是被回退了）
   ② D:\\下载\\AI桌宠\\vision\\Qwen2-VL-2B-Instruct 是否真实存在、多大、什么时候来的
   ③ config.json 有没有被提交进 git（里面有 API key！）
   ④ 我自己的文档里有没有"下载本地视觉模型"的记录
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"


def sh(args, cwd=ROOT):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return (r.stdout or "") + (r.stderr or "")


print("=== ① vision_model_name 的变更史 ===")
out = sh(["git", "log", "--all", "--oneline", "-Svision_model_name", "--", "config.json"])
print("   改过 vision_model_name 的提交：")
for l in out.split("\n")[:14]:
    if l.strip():
        print("      " + l[:110])
print()
print("   每次改动的内容：")
out2 = sh(["git", "log", "--all", "-p", "--format=COMMIT %h %ad %s", "--date=short",
           "-Svision_model_name", "--", "config.json"])
cur = ""
for l in out2.split("\n"):
    if l.startswith("COMMIT"):
        cur = l
        print("   " + l[:120])
    elif re.search(r'^[+-].*vision_model_name', l):
        print("      " + l.strip()[:110])

print()
print("=== ①-b config.json 当前值 & 是否被 git 跟踪 ===")
print("   被跟踪？", sh(["git", "ls-files", "config.json"]).strip() or "✗ 没有（好，key 没进库）")
cfg = io.open(os.path.join(ROOT, "config.json"), encoding="utf-8", errors="replace").read()
for l in cfg.split("\n"):
    if re.search(r"vision|vl|model_name", l):
        print("      " + l.strip()[:110])

print()
print("=== ② 本地视觉模型目录 ===")
for d in (r"D:\下载\AI桌宠\vision\Qwen2-VL-2B-Instruct", r"D:\下载\AI桌宠\vision",
          r"D:\下载\AI桌宠"):
    if os.path.isdir(d):
        try:
            sz = sum(os.path.getsize(os.path.join(dp, f))
                     for dp, dn, fn in os.walk(d) for f in fn
                     if os.path.exists(os.path.join(dp, f)))
            n = sum(len(fn) for _, _, fn in os.walk(d))
            mt = os.path.getmtime(d)
            import time
            print("   ✓ 存在 %s" % d)
            print("        %d 个文件 / %.2f GB / 修改时间 %s"
                  % (n, sz / 1073741824, time.strftime("%Y-%m-%d %H:%M", time.localtime(mt))))
        except Exception as e:
            print("   ? %s （统计失败 %s）" % (d, e))
        if d.endswith("Qwen2-VL-2B-Instruct"):
            for f in sorted(os.listdir(d))[:14]:
                p = os.path.join(d, f)
                if os.path.isfile(p):
                    print("        %-42s %10.1f MB" % (f[:42], os.path.getsize(p) / 1048576))
    else:
        print("   ✗ 不存在 %s" % d)

print()
print("=== ③ 我的文档里有没有下载本地视觉模型的记录 ===")
PAT = re.compile(r"Qwen2-VL|Qwen2VL|本地视觉模型|vision_local|28460|本地视觉")
n = 0
for sub in ("dev/docs", "dev/merge-map", "docs"):
    d = os.path.join(ROOT, *sub.split("/"))
    if not os.path.isdir(d):
        continue
    for f in sorted(os.listdir(d)):
        if not f.endswith((".md", ".txt")):
            continue
        p = os.path.join(d, f)
        t = io.open(p, encoding="utf-8", errors="replace").read()
        hits = [l for l in t.split("\n") if PAT.search(l)]
        if hits:
            print("   ── %s/%s" % (sub, f))
            for l in hits[:5]:
                print("      " + l.strip()[:104])
            n += 1
            if n > 8:
                break
if n == 0:
    print("   （无命中 ⇒ 我没有下载过它的记录）")
