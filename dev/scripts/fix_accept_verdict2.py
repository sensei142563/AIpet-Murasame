# -*- coding: utf-8 -*-
"""补掉最后两处会谎报 PASS 的地方。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
P = os.path.join(MAIN, "dev", "scripts", "accept_all.py")

t = io.open(P, encoding="utf-8").read().replace("\r\n", "\n")
# ① 硬编码 PASS
t = t.replace('record("测试 VRM", "PASS", "已就位")', 'record("测试 VRM", verdict(True), "已就位")')
# ② 多行 DRY 判定（⑤b）
t = re.sub(r'"PASS" if \(DRY or any\([^\)]*\)\)\s*\n\s*else "FAIL"',
           'verdict(any("ready" in l or "返回" in l for l in lines))', t)
t = t.replace('''            record("⑤b 离线 TTS 合成", verdict(any("ready" in l or "返回" in l for l in lines))''',
              '''            record("⑤b 离线 TTS 合成", verdict(any("ready" in l or "返回" in l for l in lines)),''')
io.open(P, "w", encoding="utf-8", newline="\n").write(t)
print("✓ 已修两处")
print()
print("=== 复核：全文还有没有 (DRY ... 直接判 PASS 的残留 ===")
src = io.open(P, encoding="utf-8").read()
bad = [l.strip() for l in src.split("\n") if "DRY" in l and '"PASS"' in l and "verdict" not in l]
print("   " + ("无 ✓" if not bad else "\n   ".join(bad[:5])))
print("   语法:", end=" ")
r = subprocess.run([sys.executable, "-c", "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % P],
                   capture_output=True, text=True)
print("✓" if r.returncode == 0 else "✗ " + (r.stderr or "")[:200])
if r.returncode != 0:
    sys.exit(1)

print()
print("=== 再跑 dry-run ===")
r = subprocess.run([sys.executable, "-u", P, "--dry-run"], capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=600)
out = (r.stdout or "") + (r.stderr or "")
i = out.find("=== 汇总 ===")
print("\n".join("   " + l for l in out[i:].splitlines()[:14]) if i > 0 else out[-1200:])
allskip = "FAIL 0" in out and "PASS 0" in out
print()
print("判定:", "✓ dry-run 全部 SKIP、零谎报" if allskip else "· 仍有非 SKIP 项（见上）")

MSG = """fix(accept): 补掉最后两处会谎报 PASS 的地方（dry-run 现在 100% 如实）

- "测试 VRM" 原来是硬编码 "PASS" → 改走 verdict()；
- ⑤b 离线 TTS 那条是多行写法，上一版正则没覆盖到 → 已改。
复核方式：全文搜索"同时含 DRY 与 \\"PASS\\" 且不含 verdict"的行，确认为 0。
现在 --dry-run 的输出是：PASS 0 / FAIL 0 / SKIP 全部，不再把未验证的项显示成通过。
"""
p = os.path.join(MAIN, "dev", "merge-map", "_msg_accept2.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:130])
n = subprocess.run(["git", "-C", MAIN, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True).stdout.strip()
st = subprocess.run(["git", "-C", MAIN, "status", "--porcelain"],
                    capture_output=True, text=True).stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
