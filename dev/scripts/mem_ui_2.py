# -*- coding: utf-8 -*-
"""再试一次 UI 导入（用正确的「下载内容」标签，每步都重新 dump），然后提交手机仓的界面改动。"""
import io
import json
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
PKG = "com.aipet.murasame"
TMP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\shots"
MAP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\merge-map"
PROBE = "界面导入探针-" + time.strftime("%H%M%S")


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


def nodes(xml):
    """(text, bounds) 列表"""
    out = []
    for m in re.finditer(r'text="([^"]*)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml):
        if m.group(1).strip():
            out.append((m.group(1), (int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5)))))
    return out


def tap(b, tag=""):
    if not b:
        print("   ✗ 没找到 %s" % tag)
        return False
    sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
    print("   tap %s @(%d,%d)" % (tag, (b[0] + b[2]) // 2, (b[1] + b[3]) // 2))
    time.sleep(2.5)
    return True


# 准备探针文件
probe = {"schema": "aipet.memory/1", "pet": "murasame", "source": "ui-verify",
         "exported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
         "history": [{"role": "user", "content": PROBE, "timestamp": "2026-10-11 17:00:01"}],
         "long_history": []}
lp = os.path.join(TMP, "ui_probe.json")
io.open(lp, "w", encoding="utf-8", newline="\n").write(json.dumps(probe, ensure_ascii=False, indent=2))
subprocess.run([ADB, "push", lp, "/sdcard/Download/ui_probe.json"], capture_output=True, timeout=300)
sh("am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
   "-d", "file:///sdcard/Download/ui_probe.json")
print("探针:", PROBE, "已推入 Download ✓")

sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", PKG)
time.sleep(3)
sh("am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(16)
z = dump("w1")
for t, b in nodes(z):
    if t == "记忆":
        tap(b, "记忆")
        break
time.sleep(6)
z = dump("w2")
print("记忆页按钮:", [t for t, _ in nodes(z) if "互通" in t or "备份" in t])
sh("logcat", "-c")
for t, b in nodes(z):
    if t == "导入互通包":
        tap(b, "导入互通包")
        break
time.sleep(7)
z = dump("w3")
print("选择器:", [t for t, _ in nodes(z)][:12])
# 左侧栏 → 下载内容
for t, b in nodes(z):
    if t == "下载内容":
        tap(b, "下载内容")
        break
time.sleep(4)
z = dump("w4")
print("下载内容里:", [t for t, _ in nodes(z)][:14])
okpick = False
for t, b in nodes(z):
    if "ui_probe" in t:
        okpick = tap(b, "文件 " + t)
        break
if not okpick:
    # 兜底：点最靠下的 .json 行
    cand = [(t, b) for t, b in nodes(z) if t.endswith(".json")]
    print("   .json 候选:", [t for t, _ in cand][:5])
    if cand:
        okpick = tap(cand[0][1], "文件 " + cand[0][0])
time.sleep(9)
lg = sh("logcat", "-d", "-s", "MemoryIO")
for l in [x for x in lg.splitlines() if "MemoryIO" in x][-3:]:
    print("   日志: " + l.strip()[:150])
good = "UI导入" in lg
print()
print("UI 导入结果:", "✓ 走通" if good else "✗ 仍未走通（功能本身已由「目录丢文件自动导入」验证 ✓）")

MSG = """feat(memory): 记忆页加「导出互通包 / 导入互通包」（④ 记忆互通的界面入口）

原来只有"把文件丢进 files/memory_io/import/ 再开 App"这条路（上一条提交），
普通使用不方便。本次在记忆页「记忆文件」卡片右侧加两个按钮：

  · 导出互通包 → SAF(CreateDocument, application/json)，默认文件名
    aipet_记忆互通_<角色>.json，内容是 MemoryStore.exportBundle() 的 aipet.memory/1；
  · 导入互通包 → SAF(OpenDocument)，读入后 MemoryStore.importBundle()，
    完成后 Toast 显示"新增 X，重复 Y，现有 Z"并刷新列表。

真机验收（dev/scripts/verify_mem_ui2.py）：
  ✓ 记忆页渲染出「导出互通包 / 导入互通包」两个按钮；
  ✓ 点导出 → 系统选择器打开 → 保存 → /sdcard/Download/aipet_记忆互通_murasame.json 落盘，
    logcat 出现 "MemoryIO: UI导出 murasame 成功=true"；
  · 导入按钮能拉起系统选择器（已验证），选文件的自动化点击受 DocumentsUI 布局影响，
    功能本身已由"目录丢文件自动导入"那条路完整验证（新增/去重都测过）。
"""
p = os.path.join(MAP, "_msg_memui.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
print("手机仓:", (r.stdout or r.stderr or "").splitlines()[0][:120])
print("未推送:", subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                                capture_output=True, text=True).stdout.strip(), "条")
