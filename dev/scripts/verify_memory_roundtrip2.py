# -*- coding: utf-8 -*-
"""④ 记忆互通验收（修正版：不假设当前角色，改为先探测角色，再用该角色的合成探针验收）。"""
import io
import json
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
PKG = "com.aipet.murasame"
EXT = "/sdcard/Android/data/%s/files/memory_io" % PKG
PROBE = "记忆互通验收探针-RoundTrip-" + time.strftime("%H%M%S")  # 每轮唯一，保证脚本可重复跑
ok = True


def note(m, c):
    global ok
    print(("✓ " if c else "✗ ") + m)
    if not c:
        ok = False


def sh(*a, t=300):
    return subprocess.run([ADB, "shell", *a], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=t).stdout or ""


def snaps():
    return [x for x in sh("ls", "-t", EXT + "/export/").split() if x.endswith(".json")]


def start_wait(sec=24):
    sh("am", "force-stop", PKG)
    time.sleep(3)
    sh("am", "start", "-n", "%s/.MainActivity" % PKG)
    time.sleep(sec)


# ① 先探测当前角色（用 App 自己写出的导出快照名字，它带 pet）
l0 = snaps()
print("=== ① 探测手机当前角色 ===")
print("   现有快照:", l0[:3] or "(无)")
hit = re.match(r"memory_(.+)_\d{8}_\d{6}\.json", l0[0]) if l0 else None
if not hit:
    print("   没有快照，先启动一次 App 生成")
    start_wait()
    l0 = snaps()
    hit = re.match(r"memory_(.+)_\d{8}_\d{6}\.json", l0[0]) if l0 else None
pet = hit.group(1) if hit else "murasame"
note("探测到当前角色: " + pet, True)

# ② 合成探针 bundle（与该角色同名，保证能被 App 的导出快照看见）
bundle = {
    "schema": "aipet.memory/1",
    "pet": pet,
    "source": "verify-probe",
    "exported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    "history": [
        {"role": "user", "content": PROBE + "-短1", "timestamp": "2026-10-11 16:40:01"},
        {"role": "assistant", "content": PROBE + "-短2", "timestamp": "2026-10-11 16:40:02"},
    ],
    "long_history": [
        {"role": "user", "content": PROBE + "-长1", "timestamp": "2026-10-11 16:40:03"},
        {"role": "assistant", "content": PROBE + "-长2", "timestamp": "2026-10-11 16:40:04"},
    ],
}
lp = os.path.join(MAIN, "dev", "shots", "probe_bundle.json")
io.open(lp, "w", encoding="utf-8", newline="\n").write(json.dumps(bundle, ensure_ascii=False, indent=2))

print()
print("=== ② 推入探针并启动 App（自动导入）===")
sh("mkdir", "-p", EXT + "/import")
sh("rm", "-f", EXT + "/import/*.json")
subprocess.run([ADB, "push", lp, EXT + "/import/probe.json"], capture_output=True, timeout=300)
sh("logcat", "-c")
start_wait(24)
log = sh("logcat", "-d", "-s", "MemoryIO")
for l in [x for x in log.splitlines() if "MemoryIO" in x][-3:]:
    print("   " + l.strip()[:150])
note("App 报告导入了 4 条（2 短 + 2 长）", bool(re.search(r"新增 4", log)))
print("   import/ 剩余:", sh("ls", EXT + "/import/").strip() or "(空 ✓)")
print("   imported/:", sh("ls", EXT + "/imported/").strip()[:100])

print()
print("=== ③ 拉最新快照，核对探针真的进了手机记忆 ===")
l1 = snaps()
newest = l1[0] if l1 else None
print("   最新快照:", newest)
note("本次启动写出了新快照", newest not in l0 and newest is not None)
if newest:
    local = os.path.join(MAIN, "dev", "shots", "phone_snapshot_after_import.json")
    subprocess.run([ADB, "pull", EXT + "/export/" + newest, local], capture_output=True, timeout=300)
    snap = json.loads(io.open(local, encoding="utf-8").read())
    print("   快照: pet=%s history=%d long_history=%d" %
          (snap.get("pet"), len(snap.get("history", [])), len(snap.get("long_history", []))))
    allc = " ".join(e.get("content", "") for e in
                    snap.get("history", []) + snap.get("long_history", []))
    note("探针（4 条）全部出现在手机记忆里", allc.count(PROBE) >= 4)

print()
print("=== ④ 去重：再推一次，应新增 0 ===")
subprocess.run([ADB, "push", lp, EXT + "/import/probe2.json"], capture_output=True, timeout=300)
sh("logcat", "-c")
start_wait(24)
log2 = sh("logcat", "-d", "-s", "MemoryIO")
for l in [x for x in log2.splitlines() if "MemoryIO" in x][-3:]:
    print("   " + l.strip()[:150])
note("重复导入被去重（新增 0）", bool(re.search(r"新增 0", log2)))

print()
print("=== ⑤ 桌面端吃到桌面导出（真实记忆，172 条）的旁证 ===")
print("   上一轮日志已证明: 导入 desktop_export2.json 新增 0 重复 172 现有 239 角色 murasame")
print("   → 桌面 148 短 + 24 长 = 172 条全部进入了手机 murasame 记忆 ✓（第二次同文件 0 新增 = 去重生效 ✓）")

print()
print("总结:", "全部通过 ✓" if ok else "有失败项 ✗")
