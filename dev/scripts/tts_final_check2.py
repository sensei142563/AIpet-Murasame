# -*- coding: utf-8 -*-
"""打开朗读 → 稳妥回到聊天并确认输入框 → 发一句 → pull voice.log。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
TMP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\shots"
F5LOG = r"E:\university\order\python\pet\_audit_fish9269\_f5serve.log"
VOICELOG = "/sdcard/Android/data/com.aipet.murasame/files/voice.log"


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


def goto_chat(limit=8):
    """退到有底部导航的页面，再点聊天，直到看见输入框。"""
    for attempt in range(4):
        z = dump("g%d" % attempt)
        if editbox(z):
            return z
        if box("聊天", z):
            tap(box("聊天", z))
            time.sleep(5)
            z = dump("g%d_b" % attempt)
            if editbox(z):
                return z
        sh("input", "keyevent", "KEYCODE_BACK")
        time.sleep(2)
    return dump("g_end")


sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", "com.aipet.murasame")
time.sleep(3)
sh("am", "start", "-n", "com.aipet.murasame/.MainActivity")
time.sleep(10)

# ① 打开朗读
for t in range(6):
    z = dump("s%d" % t)
    if box("聊天", z):
        break
    sh("input", "keyevent", "KEYCODE_BACK")
    time.sleep(2)
tap(box("聊天", dump("s_chat")))
time.sleep(5)
tap(box("☰", dump("s_menu")))
time.sleep(3)
z = dump("s_set")
tap(box("⚙  设置", z) if box("⚙  设置", z) else box("设置", z))
time.sleep(3)
z = dump("s_page")
row = box("关", z)
print("① 设置页 关 的位置:", row)
if row:
    tap(row)
    time.sleep(2)
    z = dump("s_after")
    st = [t for t in texts(z) if t in ("开", "关")]
    print("   点后面板上的状态字:", st[:2], "（应出现 开）")
else:
    print("   已是开或没找到")

# ② 回聊天
z = goto_chat()
print("② 输入框:", editbox(z) is not None)
if not editbox(z):
    print("   ✗ 到不了聊天页；当前文字:", texts(z)[-8:])
    sys.exit(1)

sh("rm", "-f", VOICELOG)
f50 = os.path.getsize(F5LOG) if os.path.isfile(F5LOG) else 0
b = editbox(z)
sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
time.sleep(2)
sh("input", "text", "hello")
time.sleep(3)
z = dump("s_typed")
ups = boxes("↑", z)
print("③ 框内:", [t for t in texts(z) if "hello" in t][:1], "；↑ =", ups)
if ups:
    tap(ups[0])
    time.sleep(5)

print("④ 等待回复与朗读（最多 120 秒）…")
hit = False
for k in range(12):
    time.sleep(10)
    if os.path.isfile(F5LOG) and os.path.getsize(F5LOG) > f50:
        new = io.open(F5LOG, encoding="utf-8", errors="replace").read()[f50:]
        if "/infer" in new:
            print("   %3ds ✓ F5 收到 /infer" % ((k + 1) * 10))
            hit = True
            break
    if k % 4 == 3:
        print("   %3ds 尾部: %s" % ((k + 1) * 10, texts(dump("s_w"))[-4:]))

print()
print("=== ★ 手机端 voice.log ===")
dst = os.path.join(TMP, "phone_voice3.log")
subprocess.run([ADB, "pull", VOICELOG, dst], capture_output=True, timeout=120)
content = io.open(dst, encoding="utf-8", errors="replace").read() if os.path.isfile(dst) else ""
print(content or "   （没有 ✗）")

print("=== 判定 ===")
if "成功播放" in content:
    print("   ✅✅ TTS 端到端成功（电脑 F5 的丛雨音色）")
elif "异常" in content or "失败" in content or "不是 RIFF" in content or "响应太小" in content:
    print("   ⚠ speak() 调用了但失败：", [l for l in content.splitlines() if ("异常" in l or "失败" in l or "RIFF" in l or "太小" in l)][:2])
elif content.strip():
    print("   ⚠ 有日志但无成功标记：", content.splitlines()[-1][:120])
else:
    print("   ✗ speak() 仍未执行（F5 是否收到 /infer:", hit, "）")
