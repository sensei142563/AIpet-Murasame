# -*- coding: utf-8 -*-
"""修 tap_text：点"最近的 clickable 祖先节点"的中心，而不是文字节点的中心。

根因（实测）：底部导航条的文字中心 y=2695 落在系统导航条上 ⇒ 点击被系统吃掉 ⇒ App 被切到后台。
真正的点击目标（clickable 祖先）中心在 y=2641，比文字中心高 54px。
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
A = os.path.join(MAIN, "dev", "scripts", "accept_all.py")
SD = os.path.join(MAIN, "dev", "shots")

t = io.open(A, encoding="utf-8").read().replace("\r\n", "\n")

old = '''def tap_text(xml, needle, wait=2.5):
    """在 dump 里找**包含** needle 的可点击节点，点它的中心（比精确 text= 更耐得住 emoji/换行）。"""
    for m in re.finditer(r'<node[^>]*text="([^"]*)"[^>]*bounds="\\[(\\d+),(\\d+)\\]\\[(\\d+),(\\d+)\\]"', xml):
        if needle in m.group(1):
            cx = (int(m.group(2)) + int(m.group(4))) // 2
            cy = (int(m.group(3)) + int(m.group(5))) // 2
            adb("shell", "input", "tap", str(cx), str(cy))
            time.sleep(wait)
            return True
    return False'''
new = '''def _node_bounds(xml):
    """返回 [(start, end, text, x1, y1, x2, y2, clickable)]，按出现顺序。"""
    out = []
    pat = re.compile(
        r'<node(?P<attrs>[^>]*?)bounds="\\[(?P<x1>\\d+),(?P<y1>\\d+)\\]\\[(?P<x2>\\d+),(?P<y2>\\d+)\\]"(?P<attrs2>[^>]*?)/?>')
    for m in pat.finditer(xml):
        attrs = (m.group("attrs") or "") + (m.group("attrs2") or "")
        text = (re.search(r'text="([^"]*)"', attrs) or [None, ""])[1] if re.search(r'text="([^"]*)"', attrs) else ""
        clickable = 'clickable="true"' in attrs
        out.append((m.start(), m.end(), text, int(m.group("x1")), int(m.group("y1")),
                    int(m.group("x2")), int(m.group("y2")), clickable))
    return out


def tap_text(xml, needle, wait=2.5, lift=0):
    """找包含 needle 的文本节点，然后点**最近的 clickable 祖先**的中心。

    为什么不能直接点文字中心（实测教训）：底部导航条的文字中心 y 落在**系统导航条**上，
    点击会被系统吃掉、App 直接被切到后台 —— 验收里一连串 SKIP/FAIL 全是这一个原因。
    真正的可点击目标中心比文字中心高 ~54px。
    """
    nodes = _node_bounds(xml)
    for i, nd in enumerate(nodes):
        if needle not in nd[2]:
            continue
        tx = (nd[3] + nd[5]) // 2
        ty = (nd[4] + nd[6]) // 2
        # 往前找最近的、且包住该点的 clickable 节点（Compose 的文本是 clickable 的子节点）
        target = None
        for j in range(i - 1, -1, -1):
            cand = nodes[j]
            if cand[7] and cand[3] <= tx <= cand[5] and cand[4] <= ty <= cand[6]:
                target = cand
                break
        if target is not None:
            cx = (target[3] + target[5]) // 2
            cy = (target[4] + target[6]) // 2
        else:
            cx, cy = tx, ty - lift
        adb("shell", "input", "tap", str(cx), str(cy))
        time.sleep(wait)
        return (cx, cy)
    return None'''
if old in t:
    t = t.replace(old, new, 1)
    io.open(A, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ tap_text 已改为点 clickable 祖先中心（返回坐标便于取证）")
else:
    print("✗ tap_text 锚点未命中")
    sys.exit(1)

print()
print("=== 用真实 dump 验证新逻辑（不发输入，只算坐标）===")
sys.path.insert(0, os.path.dirname(A))
# 只取函数做纯计算：把 adb/sleep 临时替换掉
src = io.open(A, encoding="utf-8").read()
ns = {"re": re, "os": os, "io": io, "sys": sys, "time": type("T", (), {"sleep": staticmethod(lambda *_: None)})}
# 注入假 adb
calls = []
ns["adb"] = lambda *a, **k: calls.append(a)
# 只执行到 _node_bounds/tap_text 的定义（截取到 "def tap_text_any"）
head = src[:src.find("def tap_text_any")]
exec(compile(head.split("DRY = ")[0] + "DRY=False\n" + "\n".join(
    l for l in head.split("\n") if not l.startswith(("import ", "from "))), "<tap>", "exec"), ns)
for f in ("a1.xml",):
    p = os.path.join(SD, f)
    if not os.path.isfile(p):
        continue
    x = io.open(p, encoding="utf-8", errors="replace").read()
    for n in ("设置", "聊天", "首页"):
        calls.clear()
        r = ns["tap_text"](x, n)
        print("   %-6s → 点 %s（期望：比文字中心 y≈2695 更高，落在可点击项上）" % (n, r))

print()
print("=== 语法检查 ===")
r = subprocess.run([sys.executable, "-c",
                    "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % A],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print("   " + ("OK" if r.returncode == 0 else "FAIL\n" + (r.stderr or "")[:400]))
