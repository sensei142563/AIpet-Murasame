# -*- coding: utf-8 -*-
"""把去重从"集合"改成"多重集"（计数感知）⇒ 既不重复又能保留合法的重复次数。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
F = os.path.join(MAIN, "tool", "memory_transfer.py")
A = os.path.join(MAIN, "dev", "scripts", "mem_adversarial.py")

t = io.open(F, encoding="utf-8").read().replace("\r\n", "\n")
old = """        seen = {_key(e) for e in cur}
        added = dup = bad = 0
        for e in incoming:
            if not _valid_record(e):
                bad += 1
                continue
            if _key(e) in seen:
                dup += 1
            else:
                seen.add(_key(e))
                cur.append(e)
                added += 1"""
new = """        # **多重集**去重（不是集合）：真实记忆里 59/148 条没有 timestamp，判定键退化成
        # role||content，于是"同一句台词出现 5 次"会被集合去重成 1 条，导入时静默丢掉 4 条。
        # 改成计数感知：当前有 2 条、要导入 5 条相同 ⇒ 补 3 条；再导入 5 条 ⇒ 补 0 条。
        # 这样既保持重导入幂等，又不丢合法的重复次数（计数本身就是信息）。
        remain = Counter(_key(e) for e in cur)
        added = dup = bad = 0
        for e in incoming:
            if not _valid_record(e):
                bad += 1
                continue
            k = _key(e)
            if remain.get(k, 0) > 0:
                remain[k] -= 1          # 已有同款记录，消耗一个计数 ⇒ 算重复
                dup += 1
            else:
                cur.append(e)
                added += 1"""
if old in t:
    t = t.replace(old, new, 1)
    if "from collections import Counter" not in t:
        t = t.replace("import argparse\nimport json", "import argparse\nimport json\nfrom collections import Counter", 1)
        print("✓ 补 import Counter")
    io.open(F, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ 去重改为多重集（计数感知）")
else:
    print("✗ 锚点未命中")
    sys.exit(1)

# 对抗套件新增"重复次数"用例
a = io.open(A, encoding="utf-8").read().replace("\r\n", "\n")
if "重复次数" not in a:
    a = a.replace('''print()
print("=== ③ incoming 里混入非 dict（字符串/数字/null）===")''',
                  '''print()
print("=== ②b 合法的重复次数不能被丢掉（多重集语义）===")
pet_rep = "pet_repeat"
rep = Path(TMP) / "rep.json"
same = {"role": "assistant", "content": "同一句台词", "timestamp": "2026-01-07 00:00:00"}
write(rep, {"pet": pet_rep, "history": [dict(same) for _ in range(5)]})
st, n, err = run_import(rep, pet=pet_rep)
note("首次导入 5 条相同记录 ⇒ 新增 5", st == "ok" and n == 5, "added=%s %s" % (n, err))
got = len(hist(pet_rep) or [])
note("记忆里确实有 5 条（没有被集合去重成 1 条）", got == 5, "实际 %d" % got)
st, n, err = run_import(rep, pet=pet_rep)
note("再导入同一份 ⇒ 新增 0（幂等）", st == "ok" and n == 0, "added=%s %s" % (n, err))
# 部分重叠：再导入 8 条相同 ⇒ 只补 3 条
write(rep, {"pet": pet_rep, "history": [dict(same) for _ in range(8)]})
st, n, err = run_import(rep, pet=pet_rep)
note("导入 8 条、已有 5 条 ⇒ 补 3 条", st == "ok" and n == 3, "added=%s %s" % (n, err))
note("最终 8 条", len(hist(pet_rep) or []) == 8, "实际 %d" % len(hist(pet_rep) or []))

print()
print("=== ③ incoming 里混入非 dict（字符串/数字/null）===")''', 1)
    io.open(A, "w", encoding="utf-8", newline="\n").write(a)
    print("✓ 对抗套件新增『重复次数』4 条断言")

print()
print("=== 跑对抗套件 ===")
r = subprocess.run([sys.executable, "-u", A], capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=900, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
out = (r.stdout or "") + (r.stderr or "")
i = out.find("=== ②b")
j = out.find("=== 汇总")
seg = out[i:j] if i > 0 else ""
print(seg)
print(out[j:] if j > 0 else out[-800:])
print("   退出码:", r.returncode)

print()
print("=== 真实记忆往返（应无损：148 → 148）===")
import shutil
exp = subprocess.run([sys.executable, os.path.join(MAIN, "tool", "memory_transfer.py"),
                      "export", "--pet", "murasame"], cwd=MAIN, capture_output=True, text=True,
                     encoding="utf-8", errors="replace")
print("   " + (exp.stdout or exp.stderr or "").strip()[:150])
outdir = os.path.join(MAIN, "dev", "memory_io")
latest = os.path.join(outdir, sorted(os.listdir(outdir))[-1]) if os.path.isdir(outdir) else None
tmp_pet = "_roundtrip_lossless"
if latest:
    r2 = subprocess.run([sys.executable, os.path.join(MAIN, "tool", "memory_transfer.py"),
                         "import", latest, "--pet", tmp_pet], cwd=MAIN, capture_output=True,
                        text=True, encoding="utf-8", errors="replace")
    print("   " + (r2.stdout or r2.stderr or "").strip().replace("\n", " | ")[:230])
    import json as _json
    rt = os.path.join(MAIN, "pets", tmp_pet, "memory", "history.json")
    if os.path.isfile(rt):
        got = len(_json.loads(io.open(rt, encoding="utf-8").read()).get("history", []))
        print("   往返后条数：%d（原始 148）⇒ %s" % (got, "无损 ✓" if got == 148 else "仍丢 %d 条 ✗" % (148 - got)))
    shutil.rmtree(os.path.join(MAIN, "pets", tmp_pet), ignore_errors=True)
    print("   已清理 pets/%s" % tmp_pet)
