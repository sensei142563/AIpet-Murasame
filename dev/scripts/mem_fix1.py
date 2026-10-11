# -*- coding: utf-8 -*-
"""修 memory_transfer 的 4 个对抗问题：非 dict 跳过、排序键健壮、原子写、损坏现状警告。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
F = os.path.join(MAIN, "tool", "memory_transfer.py")

t = io.open(F, encoding="utf-8").read().replace("\r\n", "\n")

# ---------- ① 工具函数：时间排序键 + 记录合法性 ----------
if "_ts_key" not in t:
    t = t.replace('''def _key(e):
    return "%s|%s|%s" % (e.get("role", ""), e.get("timestamp", ""), e.get("content", ""))''',
                  '''def _key(e):
    return "%s|%s|%s" % (e.get("role", ""), e.get("timestamp", ""), e.get("content", ""))


def _ts_key(e):
    """排序键：数字时间在前（按数值），字符串时间在后（按字典序）。

    为什么不能直接用 e.get("timestamp")：导入的文件可能混用 int 与 str，
    Python 3 比较 int 与 str 会抛 TypeError ⇒ 整次导入崩掉（对抗测试实测）。
    """
    ts = e.get("timestamp", "")
    if isinstance(ts, bool):          # bool 是 int 的子类，单独排掉
        return (2, str(ts))
    if isinstance(ts, (int, float)):
        return (0, float(ts))
    return (1, str(ts))


def _valid_record(e):
    """只接受"看起来像一条记忆"的 dict：必须有非空 content。

    None/字符串/数字（损坏的导出文件里很常见）一律跳过，而不是让 e.get() 抛 AttributeError ——
    崩在循环中间会让**后面**的正常记录也导不进去（对抗测试实测）。
    """
    return isinstance(e, dict) and str(e.get("content", "")).strip() != ""''', 1)
    print("✓ 新增 _ts_key / _valid_record")

# ---------- ② 导入循环：过滤非法记录 + 统计 + 原子写 + 备份 ----------
old = '''    for name, incoming in (("history.json", short), ("long_history.json", long_)):
        if not incoming:
            continue
        f = d / name
        cur = _hist(f)
        seen = {_key(e) for e in cur}
        added = dup = 0
        for e in incoming:
            if _key(e) in seen:
                dup += 1
            else:
                seen.add(_key(e))
                cur.append(e)
                added += 1
        if f.exists() and added:
            shutil.copy2(f, str(f) + ".bak-import")
        cur.sort(key=lambda e: e.get("timestamp", ""))
        f.write_text(json.dumps({"history": cur}, ensure_ascii=False, indent=2), encoding="utf-8")
        print("  %s: 新增 %d，重复 %d，现有 %d" % (name, added, dup, len(cur)))
        total_added += added
        total_dup += dup'''
new = '''    for name, incoming in (("history.json", short), ("long_history.json", long_)):
        if not incoming:
            continue
        if not isinstance(incoming, list):
            print("  %s: 不是列表，已跳过（类型 %s）" % (name, type(incoming).__name__))
            continue
        f = d / name
        # 已存在但**读不出来**（截断/损坏）时必须明说，而不是静默当成空文件接着写
        existed = f.exists()
        cur = _hist(f)
        if existed and not cur and f.stat().st_size > 2:
            print("  ⚠ %s 已存在但无法解析（%d 字节）—— 会先备份再写，请检查 .bak-import"
                  % (name, f.stat().st_size))
        cur = [e for e in cur if _valid_record(e)]
        seen = {_key(e) for e in cur}
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
                added += 1
        # 只要文件已存在就先备份（原来只在 added>0 时备份，损坏场景下会漏）
        if existed and (added or bad):
            try:
                shutil.copy2(f, str(f) + ".bak-import")
            except Exception as _e:
                print("  ⚠ 备份失败：%s" % _e)
        cur.sort(key=_ts_key)          # 用健壮排序键，避免 int/str 混用崩掉
        payload = json.dumps({"history": cur}, ensure_ascii=False, indent=2)
        # **原子写**：先写同目录临时文件再 replace ⇒ 写到一半被杀也不会截断原文件
        tmp = f.with_name(f.name + ".tmp")
        tmp.write_text(payload, encoding="utf-8")
        os.replace(str(tmp), str(f))
        print("  %s: 新增 %d，重复 %d，跳过 %d（非法记录），现有 %d"
              % (name, added, dup, bad, len(cur)))
        total_added += added
        total_dup += dup
        total_bad += bad'''
if old in t:
    t = t.replace(old, new, 1)
    print("✓ 导入循环已重写（过滤非法、健壮排序、原子写、损坏警告、备份时机）")
else:
    print("✗ 导入循环锚点未命中")
    sys.exit(1)

# ③ total_bad 初始化 + 汇总打印
t = t.replace("    total_added = total_dup = 0", "    total_added = total_dup = total_bad = 0", 1)
t = t.replace('''    print("导入完成（角色 %s）：新增 %d，重复 %d" % (pet, total_added, total_dup))''',
              '''    print("导入完成（角色 %s）：新增 %d，重复 %d，跳过 %d"
          % (pet, total_added, total_dup, total_bad))''', 1)
# 顶部需要 os
if "\nimport os" not in t:
    t = t.replace("import json\nimport shutil", "import json\nimport os\nimport shutil", 1)
    print("✓ 补 import os")

# ④ _load 增加"损坏"可见性（保持向后兼容，只加一个可选的诊断函数）
if "def _load_strict" not in t:
    t = t.replace("def _hist(p: Path):",
                  '''def _load_strict(p: Path):
    """返回 (数据, 是否解析失败)。用于需要区分"空文件"与"坏文件"的场景。"""
    if not p.is_file():
        return None, False
    try:
        return json.loads(p.read_text(encoding="utf-8")), False
    except Exception:
        return None, True


def _hist(p: Path):''', 1)
    print("✓ 新增 _load_strict（区分空与坏）")

io.open(F, "w", encoding="utf-8", newline="\n").write(t)

print()
print("=== 语法检查 ===")
r = subprocess.run([sys.executable, "-c",
                    "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % F],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print("   " + ("OK" if r.returncode == 0 else "FAIL\n" + (r.stderr or "")[:400]))
if r.returncode != 0:
    sys.exit(1)

print()
print("=== 重跑对抗测试 ===")
r2 = subprocess.run([sys.executable, "-u", os.path.join(MAIN, "dev", "scripts", "mem_adversarial.py")],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=900, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
out = (r2.stdout or "") + (r2.stderr or "")
i = out.find("=== 汇总")
print(out[i:] if i > 0 else out[-2000:])
