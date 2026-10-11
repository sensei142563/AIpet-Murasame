# -*- coding: utf-8 -*-
"""④ 记忆互通验收（双向、可复跑）：
   桌面导出 → 推进手机 import/ → 启动 App 自动导入 → 拉取手机导出快照核对内容与去重；
   再把手机快照用桌面 CLI 导入到一个临时角色，核对桌面也能吃到手机的记忆。
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
CHAT = r"E:\university\order\python\pet\chatter"
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
PKG = "com.aipet.murasame"
EXT = "/sdcard/Android/data/%s/files/memory_io" % PKG
PY = r"C:\Users\ASUS\AppData\Local\Programs\Python\Python310\python.exe"
ok = True


def note(m, c):
    global ok
    print(("✓ " if c else "✗ ") + m)
    if not c:
        ok = False


def sh(*a, t=300):
    return subprocess.run([ADB, "shell", *a], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=t).stdout or ""


def py(args, t=600):
    r = subprocess.run([PY, "-u"] + args, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=MAIN, timeout=t)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def start_app_wait(sec=22):
    sh("am", "force-stop", PKG)
    time.sleep(3)
    sh("am", "start", "-n", "%s/.MainActivity" % PKG)
    time.sleep(sec)


print("=== ① 桌面端导出（真实记忆）===")
rc, out = py(["tool/memory_transfer.py", "export", "--pet", "murasame"])
print("   " + out.strip().splitlines()[-1][:150])
bundle_file = None
m = re.search(r"-> (.+\.json)", out)
note("桌面导出成功", rc == 0 and m is not None)
if not m:
    sys.exit(1)
bundle_file = m.group(1).strip()
if not os.path.isabs(bundle_file):
    bundle_file = os.path.join(MAIN, bundle_file)
print("   文件:", bundle_file, os.path.getsize(bundle_file), "B")
data = json.loads(io.open(bundle_file, encoding="utf-8").read())
print("   内容: history=%d 条, long_history=%d 条, schema=%s, pet=%s" %
      (len(data.get("history", [])), len(data.get("long_history", [])),
       data.get("schema"), data.get("pet")))
# 取一条桌面独有的短句，作为"是否真的进来了"的探针
probe = None
for e in data.get("history", []):
    if e.get("content") and len(e["content"]) > 8:
        probe = e["content"][:12]
        break
print("   探针句子:", probe)

print()
print("=== ② 推进手机 import/ 并启动 App（自动导入）===")
sh("mkdir", "-p", EXT + "/import")
subprocess.run([ADB, "push", bundle_file, EXT + "/import/desktop_export.json"],
               capture_output=True, timeout=300)
print("   已推入:", sh("ls", "-l", EXT + "/import/").strip()[:120])
sh("logcat", "-c")
start_app_wait(24)
log = sh("logcat", "-d", "-s", "MemoryIO")
print("   应用日志 MemoryIO:")
for l in [x for x in log.splitlines() if "MemoryIO" in x][-4:]:
    print("      " + l.strip()[:150])
note("App 报告已导入（新增 > 0）", "新增" in log and not re.search(r"新增 0 重复 0", log))

print()
print("=== ③ import/ 是否归档 ===")
print("   import/:", sh("ls", EXT + "/import/").strip() or "(空 ✓)")
print("   imported/:", sh("ls", EXT + "/imported/").strip()[:120] or "(空)")
note("导入文件已归档", "desktop_export.json" in sh("ls", EXT + "/imported/"))

print()
print("=== ④ 拉取手机导出快照，核对桌面记忆真的进来了 ===")
snaps = [x for x in sh("ls", "-t", EXT + "/export/").split() if x.endswith(".json")]
print("   手机快照:", snaps[:3])
note("手机写出了导出快照", len(snaps) > 0)
if snaps:
    local = os.path.join(MAIN, "dev", "shots", "phone_memory_snapshot.json")
    subprocess.run([ADB, "pull", EXT + "/export/" + snaps[0], local], capture_output=True, timeout=300)
    snap = json.loads(io.open(local, encoding="utf-8").read())
    print("   手机快照: history=%d, long_history=%d, schema=%s, source=%s" %
          (len(snap.get("history", [])), len(snap.get("long_history", [])),
           snap.get("schema"), snap.get("source")))
    allc = " ".join(e.get("content", "") for e in snap.get("history", []))
    note("桌面导出的探针句子已出现在手机记忆里", bool(probe) and probe in allc)
    note("手机快照 schema 正确", snap.get("schema") == "aipet.memory/1")

print()
print("=== ⑤ 去重验证：再推同一个文件一次，应新增 0 ===")
subprocess.run([ADB, "push", bundle_file, EXT + "/import/desktop_export2.json"],
               capture_output=True, timeout=300)
sh("logcat", "-c")
start_app_wait(24)
log2 = sh("logcat", "-d", "-s", "MemoryIO")
for l in [x for x in log2.splitlines() if "MemoryIO" in x][-3:]:
    print("      " + l.strip()[:150])
note("重复导入被去重（新增 0）", bool(re.search(r"新增 0", log2)))

print()
print("=== ⑥ 反方向：手机快照 → 桌面（导入到临时角色，不碰真记忆）===")
if snaps:
    local = os.path.join(MAIN, "dev", "shots", "phone_memory_snapshot.json")
    rc2, out2 = py(["tool/memory_transfer.py", "import", local, "--pet", "murasame_roundtrip"])
    print("   " + out2.strip().splitlines()[-1][:150])
    tmp = os.path.join(MAIN, "pets", "murasame_roundtrip", "memory", "history.json")
    note("桌面吃到了手机记忆", rc2 == 0 and os.path.isfile(tmp) and os.path.getsize(tmp) > 100)
    if os.path.isfile(tmp):
        d = json.loads(io.open(tmp, encoding="utf-8").read())
        print("   临时角色 history 条数:", len(d.get("history", [])))
    shutil.rmtree(os.path.join(MAIN, "pets", "murasame_roundtrip"), ignore_errors=True)
    print("   已清理临时角色 ✓")

print()
print("总结:", "全部通过 ✓" if ok else "有失败项 ✗")
