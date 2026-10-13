# -*- coding: utf-8 -*-
"""拆开 APK，按目录/类型统计占用，找出 302 MB 到底是谁占的。
输出：dev/docs/安卓包体分析-2026-10-13.md 的数据来源（也打印到终端）。
"""
import collections
import io
import os
import zipfile

APK = r"E:\university\order\python\pet\chatter\app\build\outputs\apk\debug\app-debug.apk"
OUT_MD = None

print("APK =", APK)
size = os.path.getsize(APK)
print("总大小 = %.2f MB" % (size / 1024 / 1024))

groups = collections.Counter()
top = []
with zipfile.ZipFile(APK) as z:
    for info in z.infolist():
        n = info.filename
        parts = n.split("/")
        if n.startswith("lib/"):
            key = "lib/" + (parts[1] if len(parts) > 1 else "?")
        elif n.startswith("assets/"):
            key = "assets/" + "/".join(parts[1:3]) if len(parts) > 2 else "assets/(根)"
        elif n.startswith("res/"):
            key = "res/（资源）"
        elif n.endswith(".dex"):
            key = "classes*.dex（Kotlin/Java 代码）"
        elif n.startswith("META-INF/"):
            key = "META-INF/"
        elif n.startswith("kotlin/"):
            key = "kotlin/（标准库元数据）"
        else:
            key = "(其他)"
        groups[key] += info.file_size
        top.append((info.file_size, info.compress_size, n))

print()
print("=== 按分组（原始大小 / 压缩后）===")
for k, v in groups.most_common(20):
    print("   %-34s %9.2f MB" % (k, v / 1024 / 1024))

print()
print("=== 单个最大的 25 个条目 ===")
top.sort(reverse=True)
for fs, cs, n in top[:25]:
    print("   %9.2f MB (压缩 %7.2f)  %s" % (fs / 1024 / 1024, cs / 1024 / 1024, n[:96]))

# 顺便统计源码目录里的素材（构建前）
SRC = r"E:\university\order\python\pet\chatter\app\src\main"
print()
print("=== 源码目录 app/src/main 的占用（前 12 个子目录）===")
if os.path.isdir(SRC):
    sub = []
    for d in os.listdir(SRC):
        p = os.path.join(SRC, d)
        tot = 0
        if os.path.isdir(p):
            for dp, dn, fn in os.walk(p):
                for f in fn:
                    try:
                        tot += os.path.getsize(os.path.join(dp, f))
                    except Exception:
                        pass
        else:
            try:
                tot = os.path.getsize(p)
            except Exception:
                pass
        sub.append((tot, d))
    for tot, d in sorted(sub, reverse=True)[:12]:
        print("   %-24s %9.2f MB" % (d, tot / 1024 / 1024))
