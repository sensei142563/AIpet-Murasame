# -*- coding: utf-8 -*-
"""干净版：按行删除相机录像功能（无正则、无链式补丁）→ 编译装机 → 两项回归验证。"""
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


# ① 快门：整块 pointerInput(含 doShot/detectTapGestures) → clickable
pi = None
for i, l in enumerate(L):
    if ".pointerInput(Unit)" in l and "doShot()" in "".join(L[i:i + 45]):
        pi = i
        break
note("定位快门手势块", pi is not None)
if pi is not None:
    ind = re.match(r"(\s*)", L[pi]).group(1)
    pe = None
    for j in range(pi + 1, len(L)):
        if L[j].rstrip() == (ind + "},").rstrip():
            pe = j
            break
    note("定位手势块结尾", pe is not None)
    if pe is not None:
        L[pi:pe + 1] = [ind + "// 只拍照（录像功能已按用户要求去掉）\n",
                        ind + ".clickable {\n",
                        ind + "    if (!capturing) doShot()\n",
                        ind + "},\n"]
        note("快门改为只拍照", True)

# ② 删 REC 覆盖层
ri = next((i for i, l in enumerate(L) if l.strip() == "if (recording != null) {"), None)
note("定位 REC 覆盖层", ri is not None)
if ri is not None:
    ind = re.match(r"(\s*)", L[ri]).group(1)
    re_ = next((j for j in range(ri + 1, len(L)) if L[j].rstrip() == ind + "}"), None)
    note("定位覆盖层结尾", re_ is not None)
    if re_ is not None:
        del L[ri:re_ + 1]
        note("删除 REC 覆盖层", True)

# ③ 删状态与注释（按行整行删）
kill_exact = [
    "    // 录像：模式开关 / 当前录制 / 已录秒数 / VideoCapture 实例",
    "    var videoMode by remember { mutableStateOf(false) }",
    "    var videoCapture by remember { mutableStateOf<VideoCapture<Recorder>?>(null) }",
    "    var recording by remember { mutableStateOf<Recording?>(null) }",
    "    var recSec by remember { mutableStateOf(0) }",
    "    // 长按连拍：还剩几张要拍",
    "    var burstLeft by remember { mutableStateOf(0) }",
]
for key in kill_exact:
    hits = [i for i, l in enumerate(L) if l.rstrip() == key.rstrip()]
    for i in reversed(hits):
        del L[i]
    print("   - 删除行: %s（%d 处）" % (key.strip()[:46], len(hits)))

_b = next((i for i, l in enumerate(L) if "if (burstLeft > 0) {" in l), None)
note("定位 burstLeft 续拍块", _b is not None)
if _b is not None:
    _d = 0
    _e = None
    for _k in range(_b, len(L)):
        _d += L[_k].count("{") - L[_k].count("}")
        if _d <= 0 and _k >= _b:
            _e = _k
            break
    if _e is not None:
        _s0 = _b
        while _s0 > 0 and L[_s0 - 1].strip().startswith("//"):
            _s0 -= 1
        del L[_s0:_e + 1]
        note("删除 burstLeft 续拍块", True)

# ④ 删 Recorder/VideoCapture 构建段
bi = next((i for i, l in enumerate(L) if "val rec = Recorder.Builder()" in l), None)
note("定位 Recorder 构建", bi is not None)
if bi is not None:
    s0 = bi
    while s0 > 0 and (L[s0 - 1].strip().startswith("//") or L[s0 - 1].strip() == ""):
        s0 -= 1
    be = next((j for j in range(bi, len(L)) if "videoCapture = vcap" in L[j]), None)
    note("定位 vcap 赋值", be is not None)
    if be is not None:
        del L[s0:be + 1]
        note("删除 Recorder/VideoCapture 构建段", True)

s = "".join(L)
if "LaunchedEffect(provider, useFront, videoMode)" in s:
    s = s.replace("LaunchedEffect(provider, useFront, videoMode)", "LaunchedEffect(provider, useFront)", 1)
    note("LaunchedEffect 去掉 videoMode", True)

# ⑤ 绑定改回两路
_ls = s.splitlines(keepends=True)
_ln = next((i for i, l in enumerate(_ls) if l.strip() == "cap, vcap,"), None)
if _ln is not None:
    _ind = re.match(r"(\s*)", _ls[_ln]).group(1)
    _ls[_ln] = _ind + "cap,\n"
    s = "".join(_ls)
    note("绑定改回 预览+拍照（按行）", True)
elif "vcap" not in s:
    note("绑定改回 预览+拍照（已无 vcap）", True)
else:
    note("绑定改回 预览+拍照", False)
# ⑥ 整行替换提示文字（line-based，绝不靠正则）
lines = s.splitlines(keepends=True)
hit = [i for i, l in enumerate(lines) if "长按录像" in l and "Text(" in l]
note("定位提示文字行", len(hit) == 1)
if len(hit) == 1:
    ind = re.match(r"(\s*)", lines[hit[0]]).group(1)
    lines[hit[0]] = ind + 'Text("点按拍照 · 点按画面可对焦", color = Color(0xCCFFFFFF), fontSize = 11.sp)\n'
    s = "".join(lines)
    note("提示文字已替换", chr(34) + "点按拍照 · 长按录像" not in s)
# ⑦ 顺手改掉快门行注释
s = s.replace("// 快门行：左＝相册缩略图 · 中＝快门（点按拍照 / 长按录像）· 右＝翻转",
              "// 快门行：左＝相册缩略图 · 中＝快门（点按拍照）· 右＝翻转", 1)

s = s.replace("// 快门行：左＝相册缩略图 · 中＝快门（点按拍照 / 长按录像）· 右＝翻转",
              "// 快门行：左＝相册缩略图 · 中＝快门（点按拍照）· 右＝翻转", 1)

# 校验：除 import 行外不应再有录像相关标识符
bad = []
for i, l in enumerate(s.splitlines(), 1):
    if l.strip().startswith("import "):
        continue
    for kw in ("VideoCapture", "VideoRecordEvent", "recording", "recSec", "videoMode", "burstLeft", "长按录像"):
        if kw in l:
            bad.append((i, kw, l.strip()[:90]))
note("源码已无录像残留（非 import）", not bad)
for b in bad[:8]:
    print("      %d| %s | %s" % b)

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
        print("   tap %s" % tag)
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
tap(box_any(["聊天"], dump("y1")), "聊天")
time.sleep(6)
tap(box_any(["☰"], dump("y2")), "☰")
time.sleep(4)
z = dump("y3")
tap(box_any(["⚙  设置", "设置"], z), "设置")
time.sleep(4)
tap(box_any(["AR 模式（实景 + 桌宠）"], dump("y4")), "AR模式")
time.sleep(15)
z = dump("y5")
tx = texts(z)
print()
print("AR 页:", tx[:14])
print("   提示文字:", [t for t in tx if "点按" in t][:1])
a = box_any(["相册"], z)
sy = ((a[1] + a[3]) // 2) if a else 2123
print()
print("=== 回归 1：点一下快门 → 应新增 1 张照片 ===")
n0 = files()
sh("input", "tap", "612", str(sy))
time.sleep(12)
n1 = files()
print("   新增:", len(n1) - len(n0), "（期望 1 ✓）  最新:", n1[-1] if n1 else "-")
print()
print("=== 回归 2：长按快门 → 不应新增任何文件 ===")
n2 = files()
sh("input", "swipe", "612", str(sy), "612", str(sy), "900")
time.sleep(12)
n3 = files()
new = [f for f in n3 if f not in n2]
print("   长按后新增:", new or "无 ✓")
print("   页面提示:", [t for t in texts(dump("y6")) if "已保存" in t or "失败" in t][:1])

MSG = """feat(ar)!: 按用户要求去掉相机录像功能（"鸡肋"）

用户判断录像鸡肋（相机录像只录相机画面、不含叠加的 Live2D 桌宠），要求去掉。本次删除：
  · 快门手势里的 onLongPress 录像分支 → 快门恢复为单纯 clickable（点按拍照）；
  · VideoCapture / Recorder 的构建与第三路绑定（绑定回到 预览 + ImageCapture 两路）；
  · 相关状态 videoMode / videoCapture / recording / recSec / burstLeft 及其注释；
  · 录制中的红点 + "REC n s" 覆盖层；
  · 底部提示文字改为"点按拍照 · 点按画面可对焦"。
保留：点按拍照（成片含丛雨、存进系统相册）、对焦、变焦档位、手电、闪光、水平仪、网格、缩略图回看。
"""
msg = os.path.join(MAP, "_msg_novideo.txt")
io.open(msg, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r3 = subprocess.run(["git", "-C", CHAT, "commit", "-F", msg], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("提交:", (r3.stdout or r3.stderr or "").splitlines()[0][:110])
print("未推送:", subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                                capture_output=True, text=True).stdout.strip(), "条")
