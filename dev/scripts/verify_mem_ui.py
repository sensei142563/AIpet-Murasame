# -*- coding: utf-8 -*-
"""验收 ④ 的界面：记忆页出现两个按钮 → SAF 导出到 Download → SAF 导入同一文件 → 日志 MemoryIO 出结果。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
PKG = "com.aipet.murasame"
TMP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\shots"
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


def box_any(labels, xml):
    for lb in labels:
        m = re.search(r'(?:text|content-desc)="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % re.escape(lb), xml)
        if m:
            return (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))
    return None


def tap(b, tag=""):
    if b:
        sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
        print("   tap %s %s" % (tag, b))
        time.sleep(2.5)
        return True
    print("   ✗ 没找到 %s" % tag)
    return False


def texts(xml):
    return [t for t in re.findall(r'text="([^"]*)"', xml) if t.strip()]


sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", PKG)
time.sleep(3)
sh("logcat", "-c")
sh("am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(14)

print("=== ① 底部导航进「记忆」 ===")
z = dump("m1")
print("   当前页文字:", texts(z)[:8])
tap(box_any(["记忆"], z), "记忆")
time.sleep(4)
z = dump("m2")
tx = texts(z)
print("   记忆页文字:", [t for t in tx if "记忆" in t or "互通" in t or "备份" in t][:8])
note("出现「导出互通包」按钮", any("导出互通包" in t for t in tx))
note("出现「导入互通包」按钮", any("导入互通包" in t for t in tx))

print()
print("=== ② 导出：点「导出互通包」→ 系统选择器 → 保存 ===")
fresh = sh("ls", "-t", "/sdcard/Download/").split()
before_files = [f for f in fresh if f.endswith(".json")]
print("   Download 里已有 json:", before_files[:3])
tap(box_any(["导出互通包"], z), "导出互通包")
time.sleep(6)
z = dump("m3")
pk = texts(z)
print("   选择器文字:", pk[:10])
note("系统文件选择器已打开", any(("保存" in t or "Save" in t or "取消" in t) for t in pk))
have = False
for lb in ("保存", "Save", "SAVE"):
    if tap(box_any([lb], z), lb):
        have = True
        break
if not have:
    print("   没找到保存按钮，dump 里的按钮候选:", [t for t in pk if t][:16])
time.sleep(6)
after_files = [f for f in sh("ls", "-t", "/sdcard/Download/").split() if f.endswith(".json")]
newf = [f for f in after_files if f not in before_files]
print("   Download 新增 json:", newf)
note("导出成功（Download 出现互通包）", len(newf) > 0)
log1 = sh("logcat", "-d", "-s", "MemoryIO")
for l in [x for x in log1.splitlines() if "MemoryIO" in x][-2:]:
    print("   日志: " + l.strip()[:130])
note("导出日志记录成功", "UI导出" in log1 and "成功=true" in log1)

print()
print("=== ③ 导入：点「导入互通包」→ 选择刚导出的文件 → 应报 新增 0 重复 N ===")
z = dump("m4")
if not any("导入互通包" in t for t in texts(z)):
    tap(box_any(["记忆"], z), "记忆(回到记忆页)")
    time.sleep(3)
    z = dump("m5")
sh("logcat", "-c")
tap(box_any(["导入互通包"], z), "导入互通包")
time.sleep(6)
z = dump("m6")
print("   选择器文字:", texts(z)[:12])
picked = False
if newf:
    stem = newf[0]
    for lb in (stem, stem.replace("aipet_", ""), "aipet_记忆互通_murasame.json"):
        if tap(box_any([lb], z), "文件:" + lb):
            picked = True
            break
    if not picked:
        # 用最近文件列表里第一项兜底
        for lb in texts(z):
            if lb.endswith(".json"):
                if tap(box_any([lb], z), "文件:" + lb):
                    picked = True
                    break
time.sleep(8)
log2 = sh("logcat", "-d", "-s", "MemoryIO")
for l in [x for x in log2.splitlines() if "MemoryIO" in x][-3:]:
    print("   日志: " + l.strip()[:150])
note("导入走通并给出统计（UI导入 …）", "UI导入" in log2)
if "UI导入" in log2 and "新增 0" in log2:
    print("   → 同一份数据回到同一角色，新增 0 属正确行为 ✓（去重生效）")

print()
print("总结:", "界面通路验证通过 ✓" if ok else "有失败项 ✗（看上面 dump 的按钮候选）")
