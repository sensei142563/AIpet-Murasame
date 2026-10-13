# -*- coding: utf-8 -*-
"""查：项目目录为什么从 7GB 长到 34.8GB。
   输出：总量 → 一级目录 TOP → 二级目录 TOP → 最大的单个文件 TOP → 可疑项（缓存/临时/重复模型）
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"


def du(path, depth=0, limit=2):
    """返回 (总字节, 子项列表[(字节, 路径)])，递归到 limit 层。"""
    total = 0
    sub = []
    try:
        with os.scandir(path) as it:
            for e in it:
                try:
                    if e.is_dir(follow_symlinks=False):
                        sz, _ = du(e.path, depth + 1, limit)
                        total += sz
                        sub.append((sz, e.path))
                    else:
                        sz = e.stat(follow_symlinks=False).st_size
                        total += sz
                except OSError:
                    pass
    except OSError:
        pass
    return total, sub


def gb(n):
    return n / (1024 ** 3)


def mb(n):
    return n / (1024 ** 2)


print("=== 总量 ===")
total, level1 = du(ROOT)
print("   %s  =  %.2f GB" % (ROOT, gb(total)))

level1.sort(reverse=True)
print()
print("=== 一级目录 / 文件 TOP 20 ===")
print("   %-42s %10s  %6s" % ("名称", "GB", "占比"))
for sz, p in level1[:20]:
    print("   %-42s %10.2f  %5.1f%%" % (os.path.basename(p)[:42], gb(sz),
                                        100.0 * sz / total if total else 0))

print()
print("=== 二级（把前 6 个一级目录再拆一层）===")
for sz, p in level1[:6]:
    if not os.path.isdir(p):
        continue
    _, sub = du(p, 0, 1)
    sub.sort(reverse=True)
    print("   ── %s（%.2f GB）" % (os.path.basename(p), gb(sz)))
    for s2, p2 in sub[:10]:
        if s2 > 50 * 1024 * 1024:
            print("        %-40s %9.2f GB" % (os.path.basename(p2)[:40], gb(s2)))

print()
print("=== 最大的单个文件 TOP 25（> 100MB）===")
big = []
for dp, dn, fn in os.walk(ROOT):
    for f in fn:
        p = os.path.join(dp, f)
        try:
            s = os.path.getsize(p)
        except OSError:
            continue
        if s > 100 * 1024 * 1024:
            big.append((s, p))
big.sort(reverse=True)
for s, p in big[:25]:
    print("   %9.2f GB  %s" % (gb(s), p.replace(ROOT + os.sep, "")[:110]))
print("   （>100MB 的文件共 %d 个，合计 %.2f GB）" % (len(big), gb(sum(x[0] for x in big))))

print()
print("=== 可疑项：缓存 / 临时 / 日志 / 备份 / git ===")
SUS = ["__pycache__", ".pytest_cache", "_import_tmp", "tts_model_cache", ".git",
       "tmp", "temp", "backup", "dist", "build", "logs", "cache", "venv"]
import collections  # noqa: E402
agg = collections.Counter()
cnt = collections.Counter()
for dp, dn, fn in os.walk(ROOT):
    base = os.path.basename(dp)
    if base in SUS:
        sz, _ = du(dp)
        agg[base] += sz
        cnt[base] += 1
        dn[:] = []          # 不重复计入子目录
        continue
    for f in fn:
        if f.endswith((".log", ".tmp", ".bak", ".old", ".zip", ".7z", ".rar")):
            try:
                agg["*" + os.path.splitext(f)[1]] += os.path.getsize(os.path.join(dp, f))
                cnt["*" + os.path.splitext(f)[1]] += 1
            except OSError:
                pass
for k, v in agg.most_common():
    print("   %-20s %10.2f GB  （%d 处）" % (k, gb(v), cnt[k]))
