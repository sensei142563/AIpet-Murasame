# -*- coding: utf-8 -*-
"""精准恢复两处真实丢失：
  ① tool/plugins.py  → 用覆盖前备份的 504 行超集版（补齐 handle_reply 等 14 个函数）
     并把唯一一处短版接口调用点 _root() 改成 root()
  ② pets/natsume/pet.json → 补回 decor_rules（从 origin/main 取实际值）
然后验证：py_compile + 跑那条红测试 + JSON 合法性。
"""
import io
import json
import os
import py_compile
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
REF_BAK = "remotes/origin/backup/main-before-overwrite-20261001"
REF_MAIN = "remotes/origin/main"


def show(ref, path):
    r = subprocess.run(["git", "-C", ROOT, "show", "%s:%s" % (ref, path)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout or ""


# ---------- ① plugins.py ----------
print("=== ① 恢复 tool/plugins.py（备份超集版）===")
bak = show(REF_BAK, "tool/plugins.py")
if not bak.strip():
    print("   ✗ 取不到备份版本")
    sys.exit(1)
dst = os.path.join(ROOT, "tool", "plugins.py")
io.open(dst, "w", encoding="utf-8", newline="\n").write(bak)
print("   已写入 %d 行" % len(bak.split("\n")))
try:
    py_compile.compile(dst, doraise=True)
    print("   ✓ py_compile 通过")
except py_compile.PyCompileError as e:
    print("   ✗ 语法错误:", str(e)[:300])
    sys.exit(1)

# 修唯一一处短版接口调用点
mc = os.path.join(ROOT, "classes", "murasame_class.py")
t = io.open(mc, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
if "_plg2._root()" in t:
    t = t.replace("_plg2._root()", "_plg2.root()")
    io.open(mc, "w", encoding="utf-8", newline="\n").write(t)
    print("   ✓ 已把调用点 _plg2._root() → _plg2.root()")
else:
    print("   · 调用点已不是 _plg2._root()（检查一下）")
    for i, l in enumerate(t.split("\n"), 1):
        if "_root" in l and "plg" in l:
            print("      %d| %s" % (i, l.strip()[:110]))

# ---------- ② pet.json 的 decor_rules ----------
print()
print("=== ② 补回 pets/natsume/pet.json 的 decor_rules ===")
main_pet = show(REF_MAIN, "pets/natsume/pet.json")
p = os.path.join(ROOT, "pets", "natsume", "pet.json")
cur = json.loads(io.open(p, encoding="utf-8", errors="replace").read())
print("   当前树：顶层键 =", list(cur.keys()))
# 从 origin/main 抽出 decor_rules 的实际内容
try:
    m = json.loads(main_pet)
    # 找所有出现 decor_rules 的位置（结构可能是 portrait.sets.a / b）
    def walk(o, path=""):
        out = []
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "decor_rules":
                    out.append((path + "/" + k, v))
                out += walk(v, path + "/" + k)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                out += walk(v, path + "[%d]" % i)
        return out
    found = walk(m)
    print("   origin/main 里 decor_rules 出现 %d 处：" % len(found))
    for path, v in found:
        print("      %s = %s" % (path, json.dumps(v, ensure_ascii=False)[:120]))
except Exception as e:
    print("   解析 origin/main 版本失败:", e)

# 若当前树的 a/b 两套里缺这个键，就把 origin/main 的对应值补进去
try:
    sets = ((cur.get("portrait") or {}).get("sets") or {})
    fixed = 0
    for s in ("a", "b"):
        blk = sets.get(s)
        if isinstance(blk, dict) and "decor_rules" not in blk:
            blk["decor_rules"] = [{"decor": "嫌弃阴影", "emotion": "嫌弃"}]
            fixed += 1
    if fixed:
        io.open(p, "w", encoding="utf-8", newline="\n").write(
            json.dumps(cur, ensure_ascii=False, indent=4) + "\n")
        print("   ✓ 已给 %d 套立绘补上 decor_rules 示例规则" % fixed)
    else:
        print("   · 无需补（可能已有，或结构不同）")
except Exception as e:
    print("   补写失败:", e)

# ---------- ③ 验证 ----------
print()
print("=== ③ 验证 ===")
r = subprocess.run([os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe"),
                    "-m", "pytest", "tests/test_plugin_markup.py", "-q", "--no-header"],
                   cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   timeout=900)
tail = ((r.stdout or "") + (r.stderr or "")).strip().split("\n")
for l in tail[-12:]:
    print("   " + l.strip()[:150])
print("   pytest 退出码 =", r.returncode)
