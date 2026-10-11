# -*- coding: utf-8 -*-
"""拿真实 dump 验证 accept_all 里的 tap_text 逻辑：它到底能不能找到「设置」「聊天」等，坐标是多少。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
SD = os.path.join(MAIN, "dev", "shots")

# 复制 accept_all.tap_text 的正则（不改动它，只分析）
NODE = re.compile(r'<node[^>]*text="([^"]*)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"')


def analyze(path, needles):
    x = io.open(path, encoding="utf-8", errors="replace").read()
    print("=== %s（%d 字节，%d 个 node）===" % (os.path.basename(path), len(x), x.count("<node")))
    for n in needles:
        hits = []
        for m in NODE.finditer(x):
            if n in m.group(1):
                cx = (int(m.group(2)) + int(m.group(4))) // 2
                cy = (int(m.group(3)) + int(m.group(5))) // 2
                hits.append((m.group(1)[:26], cx, cy))
        print("   %-10s tap_text 匹配 %d 个：%s" % (n, len(hits), hits[:3]))
    # 再统计：所有含这些字的节点（不限 text 属性顺序）
    loose = re.findall(r'text="([^"]*)"', x)
    print("   全部 text 中与关键词相关的：%s"
          % [t for t in loose if any(n in t for n in needles)][:8])
    print()


for f, needles in (("a1.xml", ["设置", "聊天", "首页", "记忆"]),
                   ("c3.xml", ["设置", "聊天", "VRM", "3D"])):
    p = os.path.join(SD, f)
    if os.path.isfile(p):
        analyze(p, needles)

print("=== 结论方向 ===")
x = io.open(os.path.join(SD, "a1.xml"), encoding="utf-8", errors="replace").read()
m = re.search(r'text="设置"[^>]{0,200}', x)
print("   含『设置』的 node 片段：%s" % (m.group(0)[:200] if m else "(无)"))
# 看是否存在 text 在 bounds 之后的写法
m2 = re.search(r'<node[^>]*bounds="\[[^\]]+\]\[[^\]]+\]"[^>]*text="设置"', x)
print("   bounds 在 text 之前的写法存在吗：%s" % ("是（我的正则匹配不到！）" if m2 else "否"))
