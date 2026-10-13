# -*- coding: utf-8 -*-
"""把测试里的「换装复核」改成**走真实入口** pet._switch_cloth()，并加"解析层 + 渲染层"双断言。

原写法的问题（见 dev/docs/换装不生效-排查结论-2026-10-13.md）：
  ① 写的是 data/portrait_choice.json 的**顶层 b**，而 murasame 有 portrait.sets ⇒ 代码读 pets.<id>.<set>，顶层无效；
  ② 把**固定不变的 _pet2.first_portrait** 当 layers 传给 update_portrait ⇒ 图层从没变过。
改用应用自己的换装函数 `_switch_cloth()`（保存 → load_outfit → swap_body → update_portrait），
它才是右键菜单点衣服时走的那条路。
"""
import io
import os
import py_compile
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")
T = os.path.join(ROOT, "tests", "test_bugfix_0930b.py")

lines = io.open(T, encoding="utf-8", errors="replace").read().replace("\r\n", "\n").split("\n")
s = next((i for i, l in enumerate(lines) if "== ① 换装复核" in l), None)
e = next((i for i, l in enumerate(lines) if "check(\"换装复核\", False" in l), None)
if s is None or e is None:
    print("✗ 找不到锚点 s=%s e=%s" % (s, e))
    sys.exit(1)
print("   替换第 %d~%d 行（共 %d 行）" % (s + 1, e + 1, e - s + 1))

NEW = '''print("== ① 换装复核：走**真实入口** _switch_cloth()，四套必须真的不同 ==")
print("   （原写法有两个错：① 写顶层 b，而有 portrait.sets 的角色读 pets.<id>.<set>；")
print("     ② 把固定不变的 first_portrait 当 layers 传给 update_portrait ⇒ 图层从没变过。")
print("     详见 dev/docs/换装不生效-排查结论-2026-10-13.md）")
try:
    from tool import portrait_outfit as PO2  # noqa: E402
    _pc = os.path.join(REPO, "data", "portrait_choice.json")
    _orig_pc = io.open(_pc, encoding="utf-8").read()
    _ratios, _cids = {}, {}
    try:
        for _c in ("制服", "睡衣", "私服", "刀服"):
            _pet2._switch_cloth(_c)              # ← 右键菜单点衣服走的就是这个
            _cids[_c] = PO2.load_outfit().get("cloth_id")
            _ratios[_c] = round(_opaque(_pet2)[0], 2)
    finally:
        # 还原主人原本的装扮选择（_switch_cloth 会真的写盘）
        io.open(_pc, "w", encoding="utf-8").write(_orig_pc)
        if hasattr(PO2, "reset_cache"):
            PO2.reset_cache()
        try:
            from tool.portrait_outfit import load_outfit as _lo
            _pet2.update_portrait(_pet2.portrait_target,
                                  _pet2._first_portrait_for(_pet2._current_set()))
        except Exception:
            pass
    print("      解析层 cloth_id：%s" % _cids)
    print("      渲染层 不透明占比：%s" % _ratios)
    check("★ 解析层：四套 cloth_id 互不相同", len(set(_cids.values())) >= 3, str(_cids))
    check("★ 渲染层：四套画出来至少 3 种不同", len(set(_ratios.values())) >= 3, str(_ratios))
except Exception as e:
    import traceback
    traceback.print_exc()
    check("换装复核", False, "%s: %s" % (type(e).__name__, e))'''

lines = lines[:s] + NEW.split("\n") + lines[e + 1:]
io.open(T, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
print("✓ 已替换")

print()
print("=== 验证 ===")
try:
    py_compile.compile(T, doraise=True)
    print("   ✓ py_compile")
except py_compile.PyCompileError as ex:
    print("   ✗", str(ex)[:300])
    sys.exit(1)
r = subprocess.run([VENV, os.path.join("tests", "test_bugfix_0930b.py")], cwd=ROOT,
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    s2 = l.strip()
    if "[FAIL]" in s2 or "FAILED" in s2 or "通过" in s2 or s2.startswith(("解析层", "渲染层")):
        print("   " + s2[:150])
print("   退出码 =", r.returncode)
