# -*- coding: utf-8 -*-
"""去掉正则解析提示串，改为「取 ar/ 目录里最新的 png」→ 编译装机 → 拍照+点缩略图验证。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
AR = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/ArScreen.kt")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
PKG = "com.aipet.murasame"
TMP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\shots"
MAP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\merge-map"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

L = io.open(AR, encoding="utf-8", newline="").read().splitlines(keepends=True)
EOL = "\r\n" if L[0].endswith("\r\n") else "\n"
# 定位 381 行附近那段正则块（以 'val mm = Regex(' 为中心，向上到 'runCatching {'，向下到该 if 结束）
i = next((k for k, l in enumerate(L) if "val mm = Regex(" in l), None)
assert i is not None, "✗ 找不到 val mm = Regex( 行"
# 上：找 runCatching {
u = i
while u > 0 and "runCatching {" not in L[u]:
    u -= 1
# 下：找 mm != null 的 if 结束（含闭合的 }）——以 'lastShot = File(dir,' 行往下两行
d = i
while d < len(L) and "lastShot = File(dir," not in L[d]:
    d += 1
assert "lastShot = File(dir," in L[d], "✗ 找不到 lastShot 赋值行"
# 该 if 块通常再往下 2 行结束（mm != null 的 } 与 runCatching 的 }）
end = d
depth = 0
# 从 u 开始配平到 runCatching 结束
dd = 0
k = u
while k < len(L):
    dd += L[k].count("{") - L[k].count("}")
    if dd <= 0 and k > u:
        break
    k += 1
end = k
ind = re.match(r"(\s*)", L[u]).group(1)
new = [
    ind + "// 不用正则去解析提示串（那是最容易出问题的一环），直接取外部目录里最新的 PNG" + EOL,
    ind + "runCatching {" + EOL,
    ind + '    val dir = File(ctx.getExternalFilesDir(null), "ar")' + EOL,
    ind + '    lastShot = dir.listFiles { f -> f.name.startsWith("AIpet_") && f.name.endsWith(".png") }' + EOL,
    ind + "        ?.maxByOrNull { it.lastModified() }?.absolutePath" + EOL,
    ind + "}" + EOL,
]
L[u:end + 1] = new
io.open(AR, "w", encoding="utf-8", newline="").write("".join(L))
present = "maxByOrNull" in io.open(AR, encoding="utf-8").read()
print("✓ 已替换为「取最新 PNG」；校验写入: %s（替换行 %d~%d）" % (present, u + 1, end + 1))
if not present:
    subprocess.run(["git", "-C", CHAT, "checkout", "--",
                    "app/src/main/java/com/aipet/murasame/ui/ArScreen.kt"], capture_output=True)
    sys.exit(1)

print("=== 编译 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o.splitlines() if x.startswith("e: ")][:10]:
    print("   " + y[:150])
if r.returncode != 0:
    print("   ✗ 编译失败 —— 回滚")
    subprocess.run(["git", "-C", CHAT, "checkout", "--",
                    "app/src/main/java/com/aipet/murasame/ui/ArScreen.kt"], capture_output=True)
    sys.exit(1)


def itime():
    t = subprocess.run([ADB, "shell", "dumpsys", "package", PKG], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=300).stdout
    mm = re.search(r"lastUpdateTime=([^\n]+)", t)
    return mm.group(1).strip() if mm else "?"


before = itime()
APK = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
for att in range(1, 4):
    rr = subprocess.run([ADB, "install", "-r", "--no-streaming", APK], capture_output=True, text=True,
                        encoding="utf-8", errors="replace", timeout=3600)
    print("   装 %d:" % att, ((rr.stdout or rr.stderr or "").strip().splitlines() or [""])[-1][:44])
    time.sleep(3)
    now = itime()
    if now != before and now != "?":
        print("   ✓ 已装上:", now)
        break


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


def box_text(label, xml):
    m = re.search(r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % re.escape(label), xml)
    return None if not m else (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))


def tap(b):
    if b:
        sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
        return True
    return False


def shot(name):
    p = os.path.join(TMP, name)
    with io.open(p, "wb") as f:
        q = subprocess.run([ADB, "exec-out", "screencap", "-p"], stdout=subprocess.PIPE, timeout=180)
        f.write(q.stdout or b"")
    print("   截图:", p, os.path.getsize(p))
    return p


sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", PKG)
time.sleep(3)
sh("am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(10)
tap(box_text("聊天", dump("t0")))
time.sleep(5)
tap(box_text("☰", dump("t1")))
time.sleep(3)
z = dump("t2")
tap(box_text("⚙  设置", z) if box_text("⚙  设置", z) else box_text("设置", z))
time.sleep(3)
tap(box_text("AR 模式（实景 + 桌宠）", dump("t3")))
time.sleep(12)
sz = sh("wm", "size")
m = re.search(r"(\d+)x(\d+)", sz)
W, H = (int(m.group(1)), int(m.group(2))) if m else (1224, 2776)
print("① 拍照 (%d,%d)" % (W // 2, H - 465))
sh("input", "tap", str(W // 2), str(H - 465))
for k in range(8):
    time.sleep(4)
    if "AIpet_" in sh("ls", "/sdcard/Pictures/AIpet/"):
        print("   ✓ 相册已有照片")
        break
time.sleep(3)
z = dump("t4")
print("② 缩略图仍显示占位「相册」吗:", box_text("相册", z) is not None, "（False 即成功 ✓）")
shot("thumb_fixed.png")
print("③ 点缩略图 (153,2338)")
sh("input", "tap", "153", "2338")
time.sleep(4)
z = dump("t5")
close = box_text("关闭", z)
print("   是否出现「关闭」:", close)
shot("thumb_dialog_fixed.png")
if close:
    tap(close)
    time.sleep(2)
    print("   点关闭后消失:", box_text("关闭", dump("t6")) is None)
    shot("thumb_closed_fixed.png")

MSG = """fix(ar): 缩略图状态改为「取外部目录里最新的 PNG」，不再解析提示串

现象：拍完照后左下角缩略图仍显示「相册」占位 —— 说明 lastShot 一直是 null，
因此点缩略图也没有反应（不是点击失效，是状态没接上）。

原因分析：原实现从 saveShot 返回的提示串里用 Regex 抠文件名
（`Regex("AIpet_\\\\d+_\\\\d+\\\\.png").find(msg)`），只要提示串格式或匹配有一点偏差就静默失败。
本次改成不依赖文本解析：拍照成功后直接扫描 getExternalFilesDir/ar/，
取 mtime 最新的 AIpet_*.png 作为 lastShot。
"""
msg = os.path.join(MAP, "_msg_thumbfix.txt")
io.open(msg, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r3 = subprocess.run(["git", "-C", CHAT, "commit", "-F", msg], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("提交:", (r3.stdout or r3.stderr or "").splitlines()[0][:100])
print("未推送:", subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                                capture_output=True, text=True).stdout.strip(), "条")
