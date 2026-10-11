# -*- coding: utf-8 -*-
"""④ 界面验收（修正版）：等页面渲染 → 断言两个按钮 → SAF 导出保存到 Download → SAF 导入该文件 → 看 MemoryIO 日志。"""
import io
import json
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
PKG = "com.aipet.murasame"
TMP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\shots"
PROBE = "界面导入探针-" + time.strftime("%H%M%S")
ok = True


def note(m, c):
    global ok
    print(("✓ " if c else "✗ ") + m)
    if not c:
        ok = False


def sh(*a, t=300):
    return subprocess.run([ADB, "shell", *a], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=t).stdout or ""


def dump(tag):
    sh("uiautomator", "dump", "/sdcard/%s.xml" % tag)
    subprocess.run([ADB, "pull", "/sdcard/%s.xml" % tag, os.path.join(TMP, "%s.xml" % tag)],
                   capture_output=True, timeout=60)
    try:
        return io.open(os.path.join(TMP, "%s.xml" % tag), encoding="utf-8", errors="replace").read()
    except Exception:
        return ""


def box(label, xml):
    """只要 text 精确等于 label 的那个节点（避免抓到外层容器）"""
    m = re.search(r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % re.escape(label), xml)
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))


def tap(b, tag=""):
    if not b:
        print("   ✗ 没找到 %s" % tag)
        return False
    sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
    print("   tap %s @(%d,%d)" % (tag, (b[0] + b[2]) // 2, (b[1] + b[3]) // 2))
    time.sleep(2.5)
    return True


def texts(xml):
    return [t for t in re.findall(r'text="([^"]*)"', xml) if t.strip()]


sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", PKG)
time.sleep(3)
sh("am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(16)
z = dump("v1")
tap(box("记忆", z), "底部导航 记忆")
time.sleep(6)                       # ← 关键：等记忆页渲染完再 dump
z = dump("v2")
tx = texts(z)
print("   记忆页:", [t for t in tx if "记忆" in t or "互通" in t or "备份" in t][:6])
note("页面已渲染（出现「记忆文件」）", any("记忆文件" in t for t in tx))
note("出现「导出互通包」", any(t == "导出互通包" for t in tx))
note("出现「导入互通包」", any(t == "导入互通包" for t in tx))

print()
print("=== ① 导出：点「导出互通包」→ 选择器 → 保存 ===")
before = [f for f in sh("ls", "/sdcard/Download/").split() if f.endswith(".json")]
tap(box("导出互通包", z), "导出互通包")
time.sleep(7)
z = dump("v3")
pt = texts(z)
print("   选择器:", pt[:8])
note("系统保存选择器已打开", any(("保存" in t or "Save" in t) for t in pt))
saved = False
for lb in ("保存", "Save"):
    if tap(box(lb, z), lb):
        saved = True
        break
time.sleep(7)
after = [f for f in sh("ls", "/sdcard/Download/").split() if f.endswith(".json")]
newf = [f for f in after if f not in before]
print("   Download:", after[:4], "新增:", newf)
note("导出落盘成功", len(newf) > 0)
lg = sh("logcat", "-d", "-s", "MemoryIO")
for l in [x for x in lg.splitlines() if "MemoryIO" in x][-2:]:
    print("   日志: " + l.strip()[:130])
note("导出日志成功=true", "UI导出" in lg and "成功=true" in lg)

print()
print("=== ② 导入：先把探针文件放进 Download，再用「导入互通包」选它 ===")
probe = {"schema": "aipet.memory/1", "pet": "murasame", "source": "ui-verify",
         "exported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
         "history": [{"role": "user", "content": PROBE, "timestamp": "2026-10-11 16:50:01"}],
         "long_history": []}
lp = os.path.join(TMP, "ui_probe.json")
io.open(lp, "w", encoding="utf-8", newline="\n").write(json.dumps(probe, ensure_ascii=False, indent=2))
subprocess.run([ADB, "push", lp, "/sdcard/Download/ui_probe.json"], capture_output=True, timeout=300)
sh("am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
   "-d", "file:///sdcard/Download/ui_probe.json")
print("   已放入 /sdcard/Download/ui_probe.json")
z = dump("v4")
if not any(t == "导入互通包" for t in texts(z)):
    tap(box("记忆", z), "回记忆页")
    time.sleep(5)
    z = dump("v5")
sh("logcat", "-c")
tap(box("导入互通包", z), "导入互通包")
time.sleep(7)
z = dump("v6")
print("   选择器首屏:", texts(z)[:10])
# 切到「下载」再选文件
picked = False
for lb in ("显示根目录", "下载", "Downloads", "ui_probe.json"):
    b = box(lb, z)
    if b:
        tap(b, lb)
        time.sleep(3)
        z = dump("v7")
        print("   切/选后:", texts(z)[:10])
        if lb == "ui_probe.json":
            picked = True
            break
if not picked:
    for lb in texts(z):
        if "ui_probe" in lb:
            picked = tap(box(lb, z), lb)
            break
time.sleep(9)
lg2 = sh("logcat", "-d", "-s", "MemoryIO")
for l in [x for x in lg2.splitlines() if "MemoryIO" in x][-3:]:
    print("   日志: " + l.strip()[:150])
note("导入走通并给出统计", "UI导入" in lg2)
if "UI导入" in lg2:
    note("探针确实被导入（新增 ≥1 或重复 ≥1）",
         bool(re.search(r"UI导入 新增 [1-9]", lg2)) or bool(re.search(r"重复 [1-9]", lg2)))

print()
print("总结:", "界面通路验证通过 ✓" if ok else "有失败项 ✗")
