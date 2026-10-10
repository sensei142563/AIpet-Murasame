# -*- coding: utf-8 -*-
"""稳妥版：只在我们的 App 内活动（每步验证标记）→ 点「朗读」整行打开 → 回聊天发消息 → pull voice.log。"""
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
F5LOG = r"E:\university\order\python\pet\_audit_fish9269\_f5serve.log"
VOICELOG = "/sdcard/Android/data/%s/files/voice.log" % PKG
MARK = ("☰", "＋", "Live2D", "首页", "记忆", "人设", "设置", "聊天")


def sh(*a, t=300):
    return subprocess.run([ADB, "shell", *a], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=t).stdout or ""


def foreground():
    t = sh("dumpsys", "window", "windows")
    pk = re.findall(r"mCurrentFocus=Window\{[^}]*?([\w\.]+)/", t)
    return pk[-1] if pk else "?"


def dump(tag):
    sh("uiautomator", "dump", "/sdcard/%s.xml" % tag)
    subprocess.run([ADB, "pull", "/sdcard/%s.xml" % tag, os.path.join(TMP, "%s.xml" % tag)],
                   capture_output=True, timeout=60)
    try:
        return io.open(os.path.join(TMP, "%s.xml" % tag), encoding="utf-8", errors="replace").read()
    except Exception:
        return ""


def boxes(label, xml):
    return [tuple(int(m.group(i)) for i in (1, 2, 3, 4))
            for m in re.finditer(r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % re.escape(label), xml)]


def box(label, xml):
    b = boxes(label, xml)
    return b[0] if b else None


def tap(b):
    if b:
        sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
        return True
    return False


def texts(xml):
    return [t for t in re.findall(r'text="([^"]*)"', xml) if t.strip()]


def editbox(xml):
    m = re.search(r'class="android.widget.EditText"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml)
    return None if not m else tuple(int(m.group(i)) for i in (1, 2, 3, 4))


def is_ours(xml):
    return any(t in texts(xml) for t in MARK)


def ensure_ours(limit=4):
    for i in range(limit):
        if foreground() == PKG:
            z = dump("f%d" % i)
            if is_ours(z):
                return z
        sh("am", "start", "-n", "%s/.MainActivity" % PKG)
        time.sleep(6)
    return dump("f_end")


print("=== ① 确保在 App 内 ===")
sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", PKG)
time.sleep(3)
sh("am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(10)
z = ensure_ours()
print("   前台:", foreground(), "；是我们 App:", is_ours(z))

print("=== ② 进设置页 ===")
if not tap(box("聊天", z)):
    tap(box("＋", z))
time.sleep(5)
z = ensure_ours()
tap(box("☰", z))
time.sleep(3)
z = dump("s1")
if not tap(box("⚙  设置", z) if box("⚙  设置", z) else box("设置", z)):
    print("   ✗ 没进设置页；文字:", texts(z)[-8:])
    sys.exit(1)
time.sleep(3)
z = dump("s2")
print("   设置页含语音区:", any(t in texts(z) for t in ("朗读", "朗读音色", "语音服务地址")))

print("=== ③ 点「朗读」整行 ===")
row = box("朗读", z)
state_before = None
if row:
    yy = (row[1] + row[3]) // 2
    for mm in re.finditer(r'text="([^"]*)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', z):
        if mm.group(1) in ("开", "关") and abs((int(mm.group(2)) + int(mm.group(4))) // 2 - yy) < 70:
            state_before = mm.group(1)
print("   朗读行:", row, "；状态:", state_before)
if state_before == "关" and row:
    tap(row)
    time.sleep(3)
    z = dump("s3")
    yy = (row[1] + row[3]) // 2
    after = [mm.group(1) for mm in re.finditer(r'text="([^"]*)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', z)
             if mm.group(1) in ("开", "关") and abs((int(mm.group(2)) + int(mm.group(4))) // 2 - yy) < 70]
    print("   点后状态:", after[:2], "（应为 开 ✓）")
elif state_before == "开":
    print("   （已经是开 ✓）")

print("=== ④ 回聊天（点底部导航「聊天」）===")
z = dump("c0")
if not tap(box("聊天", z)):
    sh("input", "keyevent", "KEYCODE_BACK")
    time.sleep(3)
    z = dump("c1")
    tap(box("聊天", z))
time.sleep(5)
z = ensure_ours()
print("   输入框:", editbox(z) is not None, "；前台:", foreground())

if editbox(z):
    sh("rm", "-f", VOICELOG)
    f50 = os.path.getsize(F5LOG) if os.path.isfile(F5LOG) else 0
    b = editbox(z)
    sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
    time.sleep(2)
    sh("input", "text", "hello")
    time.sleep(3)
    z = dump("c2")
    ups = boxes("↑", z)
    print("   框内:", [t for t in texts(z) if "hello" in t][:1], "；↑ =", ups)
    if ups:
        tap(ups[0])
        time.sleep(5)
    print("   等待（最多 120 秒）…")
    for k in range(12):
        time.sleep(10)
        if os.path.isfile(F5LOG) and os.path.getsize(F5LOG) > f50:
            new = io.open(F5LOG, encoding="utf-8", errors="replace").read()[f50:]
            if "/infer" in new:
                print("   %3ds ✓ F5 收到 /infer" % ((k + 1) * 10))
                break
        if k % 4 == 3:
            print("   %3ds 尾部: %s" % ((k + 1) * 10, texts(dump("c3"))[-4:]))
    print()
    print("=== ★ voice.log ===")
    dst = os.path.join(TMP, "phone_voice4.log")
    subprocess.run([ADB, "pull", VOICELOG, dst], capture_output=True, timeout=120)
    content = io.open(dst, encoding="utf-8", errors="replace").read() if os.path.isfile(dst) else ""
    print(content or "   （没有 ✗）")
    print("=== 判定 ===")
    if "成功播放" in content:
        print("   ✅✅ TTS 端到端成功（电脑 F5 丛雨音色）")
    elif content.strip():
        print("   ⚠ speak() 调用但失败 →", [l for l in content.splitlines() if ("异常" in l or "失败" in l or "RIFF" in l or "太小" in l or "HTTP" in l)][:2])
    else:
        print("   ✗ speak() 仍未执行")
else:
    print("   ✗ 到不了聊天输入框；当前文字:", texts(z)[-8:], "前台:", foreground())
