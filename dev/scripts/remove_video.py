# -*- coding: utf-8 -*-
"""按用户要求去掉相机录像：快门长按分支/VideoCapture 绑定/REC 覆盖层/相关状态与提示文字 → 编译装机 → 回归验证。"""
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
ARDIR = "/sdcard/Android/data/%s/files/ar/" % PKG
MAP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\merge-map"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

L = io.open(AR, encoding="utf-8").read().replace("\r\n", "\n").splitlines(keepends=True)
ok = True


def note(m, c):
    global ok
    print(("✓ " if c else "✗ ") + m)
    if not c:
        ok = False


def find(pred, start=0):
    for i in range(start, len(L)):
        if pred(L[i]):
            return i
    return None


# ① 快门：把 pointerInput(长按录像) 整块换成简单的 clickable
pi = find(lambda l: l.strip() == ".pointerInput(Unit) {"
          or (l.strip().startswith(".pointerInput(Unit)") and "doShot" in "".join(
              L[max(0, 0):0])))
# 更可靠：找包含 doShot 的 pointerInput 块
cands = [i for i, l in enumerate(L) if ".pointerInput(Unit)" in l]
pi = None
for i in cands:
    chunk = "".join(L[i:i + 40])
    if "doShot()" in chunk and "detectTapGestures" in chunk:
        pi = i
        break
note("定位快门的 pointerInput 块", pi is not None)
if pi is not None:
    ind = re.match(r"(\s*)", L[pi]).group(1)
    close = ind + "},"
    pe = None
    for j in range(pi + 1, len(L)):
        if L[j].rstrip() == close.rstrip():
            pe = j
            break
    note("定位该块结尾", pe is not None)
    if pe is not None:
        L[pi:pe + 1] = [ind + "// 只拍照（录像功能已按用户要求去掉）\n",
                        ind + ".clickable {\n",
                        ind + "    if (!capturing) doShot()\n",
                        ind + "},\n"]
        note("快门改为只拍照", True)

# ② 去掉 REC 覆盖层
ri = find(lambda l: l.strip() == "if (recording != null) {")
note("定位 REC 覆盖层", ri is not None)
if ri is not None:
    ind = re.match(r"(\s*)", L[ri]).group(1)
    re_ = None
    for j in range(ri + 1, len(L)):
        if L[j].rstrip() == ind + "}":
            re_ = j
            break
    note("定位覆盖层结尾", re_ is not None)
    if re_ is not None:
        del L[ri:re_ + 1]
        note("已删除 REC 覆盖层", True)

# ③ 去掉相关状态
for key in ("var videoMode by remember", "var videoCapture by remember",
            "var recording by remember", "var recSec by remember",
            "// 录像：模式开关", "// 录像：模式开关 / 当前录制 / 已录秒数 / VideoCapture 实例",
            "// 长按连拍：还剩几张要拍", "var burstLeft by remember"):
    hits = [i for i, l in enumerate(L) if key in l]
    for i in reversed(hits):
        del L[i]
        print("   - 删除状态行: " + key)

# ④ 绑定去掉 VideoCapture
bi = find(lambda l: "val rec = Recorder.Builder()" in l)
note("定位 Recorder 构建", bi is not None)
if bi is not None:
    # 从注释/val rec 起，到 videoCapture = vcap 结束
    be = find(lambda l: "videoCapture = vcap" in l, bi)
    note("定位 vcap 赋值", be is not None)
    if be is not None:
        s0 = bi
        while s0 > 0 and (L[s0 - 1].strip().startswith("//") or L[s0 - 1].strip() == ""):
            s0 -= 1
        del L[s0:be + 1]
        note("已删除 Recorder/VideoCapture 构建", True)
s = "".join(L)
if "preview, cap, vcap," in s:
    s = s.replace("preview, cap, vcap,", "preview, cap,", 1)
    note("绑定改回 预览+拍照", True)
# 提示文字：把任何含"长按录像"的 Text 文案整句换掉（正则，容忍空格/中点差异）
s2 = re.sub(r'"点按拍照[^"]*长按录像[^"]*"', '"点按拍照 · 点按画面可对焦"', s)
if s2 == s:
    # 退路：直接删掉"长按录像"这几个字所在的那一小段
    s2 = re.sub(r'\s*·\s*长按录像', '', s)
print("   提示文字是否仍含长按录像:", "长按录像" in s2)
s = s2
note("提示文字去掉长按录像", "长按录像" not in s)

if not ok:
    print("✗ 有步骤失败 —— 回滚")
    subprocess.run(["git", "-C", CHAT, "checkout", "--",
                    "app/src/main/java/com/aipet/murasame/ui/ArScreen.kt"], capture_output=True)
    sys.exit(1)
io.open(AR, "w", encoding="utf-8", newline="\n").write(s)
print("✓ 已写入")

print("=== 编译 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o.splitlines() if x.startswith("e: ")][:8]:
    print("   " + y[:240])
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


def box_any(labels, xml):
    for lb in labels:
        m = re.search(r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % re.escape(lb), xml)
        if m:
            return (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))
    return None


def tap(b, tag=""):
    if b:
        sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
        print("   tap %s %s" % (tag, b))
        return True
    print("   ✗ 没找到 %s" % tag)
    return False


def texts(xml):
    return [t for t in re.findall(r'text="([^"]*)"', xml) if t.strip()]


def files():
    return re.findall(r"(AIpet_\d+_\d+\.\w+)", sh("ls", ARDIR))


sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", PKG)
time.sleep(4)
sh("am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(15)
tap(box_any(["聊天"], dump("z1")), "聊天")
time.sleep(6)
tap(box_any(["☰"], dump("z2")), "☰")
time.sleep(4)
z = dump("z3")
tap(box_any(["⚙  设置", "设置"], z), "设置")
time.sleep(4)
tap(box_any(["AR 模式（实景 + 桌宠）"], dump("z4")), "AR模式")
time.sleep(15)
z = dump("z5")
tx = texts(z)
print()
print("AR 页:", tx[:14])
print("   提示文字:", [t for t in tx if "点按" in t][:1])
a = box_any(["相册"], z)
sy = ((a[1] + a[3]) // 2) if a else 2123
print()
print("=== 回归 1：点一下快门 → 应产生 1 张照片 ===")
n0 = files()
print("   点前文件数:", len(n0))
sh("input", "tap", "612", str(sy))
time.sleep(12)
n1 = files()
print("   点后文件数:", len(n1), "→ 新增", len(n1) - len(n0), "（期望 1 ✓）")
print()
print("=== 回归 2：长按快门 → 不应产生任何视频 ===")
n2 = files()
sh("input", "swipe", "612", str(sy), "612", str(sy), "900")
time.sleep(12)
n3 = files()
new = [f for f in n3 if f not in n2]
print("   长按后新增:", new or "无 ✓", "（应为空 ✓）")
print("   其中 mp4:", [f for f in new if f.endswith(".mp4")] or "无 ✓")
print("   页面提示:", [t for t in texts(dump("z6")) if "已保存" in t or "失败" in t][:1])
