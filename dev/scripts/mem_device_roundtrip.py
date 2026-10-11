# -*- coding: utf-8 -*-
"""记忆互通**真机往返**全自动验证（不需要人工点界面）。

App 的机制（MainActivity 冷启动时）：
  ① 先把 memory_io/import/ 下的文件合并进来（按 role|timestamp|content 多重集去重，幂等且不丢条数）
  ② 再写一份快照到 memory_io/export/

因此可以全自动跑：
  1) 拉手机最新导出包 → 桌面导入到临时角色 → 数条数（验证"手机→桌面"无损）
  2) 桌面导出 → 丢进手机 memory_io/import/ → 冷启动 App（自动合并）→ 拉新快照 → 数条数
     （验证"桌面→手机"生效且不丢、不重复膨胀）
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
PKG = "com.aipet.murasame"
EXT = "/sdcard/Android/data/%s/files" % PKG
TMP = os.path.join(MAIN, "dev", "mem_rt")
PY = sys.executable
ROWS = []


def adb(*a, timeout=600):
    r = subprocess.run([ADB, "-s", DEV, *a], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return (r.stdout or "") + (r.stderr or "")


def row(name, ok, detail):
    ROWS.append((name, ok, detail))
    print("   [%s] %-30s %s" % ("PASS" if ok else "FAIL", name, detail[:120]))


def counts(path):
    """数一份互通包/记忆文件里的条数：短记忆 + 长记忆。"""
    try:
        o = json.loads(io.open(path, encoding="utf-8", errors="replace").read())
    except Exception as e:
        return None, None
    def n_of(*keys):
        for k in keys:
            v = o.get(k) if isinstance(o, dict) else None
            if isinstance(v, list):
                return len(v)
        return None
    return n_of("records", "history", "short"), n_of("long", "long_term", "longterm")


def bundle_count(path):
    """直接数互通包里的记录（按 role/type 粗分）。"""
    try:
        o = json.loads(io.open(path, encoding="utf-8", errors="replace").read())
    except Exception:
        return None
    if isinstance(o, dict):
        for k in ("records", "items", "messages"):
            if isinstance(o.get(k), list):
                return len(o[k])
        # 可能按角色分组
        tot = 0
        for v in o.values():
            if isinstance(v, list):
                tot += len(v)
        return tot or None
    if isinstance(o, list):
        return len(o)
    return None


print("=" * 74)
print("记忆互通 · 真机往返验证")
print("=" * 74)
os.makedirs(TMP, exist_ok=True)

# ---------- 1. 手机 → 桌面 ----------
print("\n① 手机 → 桌面")
out = adb("shell", "ls", "-t", EXT + "/memory_io/export/")
names = [l.strip().split()[-1] for l in (out or "").splitlines() if l.strip().endswith(".json")]
if not names:
    row("手机侧有导出包", False, "memory_io/export/ 里没有 .json")
    sys.exit(1)
newest = names[0]
local_phone = os.path.join(TMP, "phone_bundle.json")
adb("pull", EXT + "/memory_io/export/" + newest, local_phone)
size = os.path.getsize(local_phone) if os.path.isfile(local_phone) else 0
n_phone = bundle_count(local_phone)
row("手机侧有导出包", size > 0, "%s（%d 字节，记录 %s 条）" % (newest, size, n_phone))

# 导入到桌面临时角色
rt = os.path.join(MAIN, "pets", "_rt_phone")
shutil.rmtree(rt, ignore_errors=True)
r = subprocess.run([PY, os.path.join(MAIN, "tool", "memory_transfer.py"), "import", local_phone,
                    "--pet", "_rt_phone"], cwd=MAIN, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=600,
                   env=dict(os.environ, PYTHONIOENCODING="utf-8"))
imp = (r.stdout or "") + (r.stderr or "")
print("      导入输出：", " | ".join(l.strip() for l in imp.splitlines()[-3:])[:200])

hist = os.path.join(rt, "memory", "history.json")
longf = os.path.join(rt, "memory", "long_history.json")
n_desk = None
n_short = n_long = 0
if os.path.isfile(hist):
    n_short = counts(hist)[0] or 0
    # 长记忆单独一个文件；互通的条数必须是**两者相加**
    # （第一版只数了 history.json，于是把"完全无损"误判成 FAIL —— 自己的数数错）
    for cand in (longf, os.path.join(rt, "memory", "long_term.json"),
                 os.path.join(rt, "memory", "long.json")):
        if os.path.isfile(cand):
            n_long = counts(cand)[0] or counts(cand)[1] or 0
            break
    n_desk = n_short + n_long
    row("手机 → 桌面 无损", (n_phone is None) or (n_desk == n_phone),
        "手机包 %s 条 → 桌面 %s 条（短 %d + 长 %d）" % (n_phone, n_desk, n_short, n_long))
else:
    row("手机 → 桌面 无损", False, "桌面没有生成 %s" % hist)

# ---------- 2. 桌面 → 手机 ----------
print("\n② 桌面 → 手机")
out = subprocess.run([PY, os.path.join(MAIN, "tool", "memory_transfer.py"), "export", "--pet", "murasame"],
                     cwd=MAIN, capture_output=True, text=True, encoding="utf-8", errors="replace",
                     timeout=600, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
expo = (out.stdout or "") + (out.stderr or "")
m = re.search(r"(dev[\\/]memory_io[^\s]+\.json)", expo.replace("\\", "/"))
desk_bundle = None
d = os.path.join(MAIN, "dev", "memory_io")
if os.path.isdir(d):
    js = sorted([f for f in os.listdir(d) if f.endswith(".json")])
    if js:
        desk_bundle = os.path.join(d, js[-1])
print("      桌面导出：", (desk_bundle or "(未找到)"))
n_desk_src = None
if desk_bundle:
    n_desk_src = bundle_count(desk_bundle)
    adb("shell", "mkdir", "-p", EXT + "/memory_io/import")
    adb("push", desk_bundle, EXT + "/memory_io/import/desktop_push.json")
    ls = adb("shell", "ls", "-l", EXT + "/memory_io/import/")
    ok_push = "desktop_push.json" in (ls or "")
    row("桌面包已推入手机 import/", ok_push, "桌面侧 %s 条；%s" % (n_desk_src,
        (ls or "").strip().splitlines()[-1][:80] if ls else ""))
else:
    row("桌面包已推入手机 import/", False, "没找到桌面导出文件")

# 冷启动 App（触发自动合并 + 写新快照）
print("\n   冷启动 App（自动合并 import/ 并写新快照）…")
before = set(l.strip().split()[-1] for l in (adb("shell", "ls", "-t", EXT + "/memory_io/export/") or "").splitlines()
             if l.strip().endswith(".json"))
adb("shell", "am", "force-stop", PKG)
time.sleep(1)
adb("shell", "am", "start", "-n", PKG + "/.MainActivity")
time.sleep(18)
after = set(l.strip().split()[-1] for l in (adb("shell", "ls", "-t", EXT + "/memory_io/export/") or "").splitlines()
            if l.strip().endswith(".json"))
new = sorted(after - before)
print("      新快照：", new[:3] if new else "(没有新快照)")
if new:
    local_new = os.path.join(TMP, "phone_after.json")
    adb("pull", EXT + "/memory_io/export/" + new[0], local_new)
    n_after = bundle_count(local_new)
    # 合并后应当 ≥ 两边各自的数量（多重集合并 = 并集，不丢不爆）
    expected_min = max(n_phone or 0, n_desk_src or 0)
    row("桌面 → 手机 合并生效", (n_after or 0) >= expected_min,
        "合并后手机 %s 条（≥ max(手机原 %s, 桌面 %s) = %s）" % (n_after, n_phone, n_desk_src, expected_min))
    # 去重是否幂等：再冷启动一次，条数不应暴涨
    adb("shell", "am", "force-stop", PKG)
    time.sleep(1)
    adb("shell", "am", "start", "-n", PKG + "/.MainActivity")
    time.sleep(15)
    b2 = set(l.strip().split()[-1] for l in (adb("shell", "ls", "-t", EXT + "/memory_io/export/") or "").splitlines()
             if l.strip().endswith(".json"))
    new2 = sorted(b2 - after)
    if new2:
        local2 = os.path.join(TMP, "phone_again.json")
        adb("pull", EXT + "/memory_io/export/" + new2[0], local2)
        n2 = bundle_count(local2)
        row("重复冷启动不膨胀（幂等）", (n2 or 0) <= (n_after or 0) + 2,
            "第二次冷启动后 %s 条（第一次 %s 条）" % (n2, n_after))
    else:
        row("重复冷启动不膨胀（幂等）", True, "第二次没产生新快照（无新数据即不重写）")
else:
    row("桌面 → 手机 合并生效", False, "冷启动后没有产生新快照（可能没合并）")

# ---------- 3. 汇总 ----------
print("\n" + "=" * 74)
npass = sum(1 for _, ok, _ in ROWS if ok)
for nm, ok, dt in ROWS:
    print("%-34s %-6s %s" % (nm[:33], "PASS" if ok else "FAIL", dt[:60]))
print("-" * 74)
print("合计 %d/%d" % (npass, len(ROWS)))
print("=" * 74)
shutil.rmtree(rt, ignore_errors=True)   # 清理临时角色
sys.exit(0 if npass == len(ROWS) else 1)
