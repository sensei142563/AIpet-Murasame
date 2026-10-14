# -*- coding: utf-8 -*-
"""① 找到可用的 PDF 文本提取库
   ② 列出三个 PDF 的大小/页数
   ③ 各抽前几页文本，先看清是什么
"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DIR = r"D:\微信存储与浏览器下载\xwechat_files\wxid_zcrbiu5hjv8k22_42cd\msg\file\2026-10"
FILES = [
    "MMEdge- Accelerating On-device Multimodal Inference via Pipelined Sensing and Encoding.pdf",
    "ophvlm-r1-waica2026.pdf",
    "2608.27233v1.pdf",
]

print("=== ① 可用的提取库 ===")
LIBS = {}
for name in ("fitz", "pypdf", "PyPDF2", "pdfplumber", "pdfminer"):
    try:
        __import__(name)
        LIBS[name] = True
        print("   ✓ %s" % name)
    except Exception as e:
        print("   ✗ %s (%s)" % (name, type(e).__name__))

print()
print("=== ② 文件 ===")
for f in FILES:
    p = os.path.join(DIR, f)
    if not os.path.isfile(p):
        print("   ✗ 不存在：%s" % f)
        continue
    print("   ✓ %-72s %6.1f MB" % (f[:72], os.path.getsize(p) / 1048576))

print()
print("=== ③ 抽取前 2 页（看清标题/作者/摘要）===")
def extract(p, pages=2):
    txt = ""
    if "fitz" in LIBS:
        import fitz
        d = fitz.open(p)
        for i in range(min(pages, d.page_count)):
            txt += d[i].get_text()
        n = d.page_count
        d.close()
        return txt, n
    if "pypdf" in LIBS:
        from pypdf import PdfReader
        r = PdfReader(p)
        for i in range(min(pages, len(r.pages))):
            txt += r.pages[i].extract_text() or ""
        return txt, len(r.pages)
    if "PyPDF2" in LIBS:
        import PyPDF2
        r = PyPDF2.PdfReader(p)
        for i in range(min(pages, len(r.pages))):
            txt += r.pages[i].extract_text() or ""
        return txt, len(r.pages)
    return "", 0

for f in FILES:
    p = os.path.join(DIR, f)
    if not os.path.isfile(p):
        continue
    print()
    print("   ══════ %s ══════" % f)
    try:
        t, n = extract(p, 2)
        print("   （共 %d 页；下面为前 2 页文本，最多 2000 字）" % n)
        for l in t[:2000].split("\n"):
            if l.strip():
                print("      " + l.strip()[:110])
    except Exception as e:
        print("   ✗ 抽取失败：%s: %s" % (type(e).__name__, e))
