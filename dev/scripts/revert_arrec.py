# -*- coding: utf-8 -*-
"""按用户要求撤掉 AR 录屏（revert 6288bbb + 22dd880）→ 编译装机 → 验证按钮消失、相机录像仍在。"""
import io
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
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")


def git(*a, t=600):
    return subprocess.run(["git", "-C", CHAT, *a], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=t)


# ① revert（逆序：先前台服务提交，再 AR 录屏提交）
r1 = git("revert", "--no-commit", "22dd880")
print("revert 22dd880:", ((r1.stdout or "") + (r1.stderr or "")).strip().splitlines()[:2])
r2 = git("revert", "--no-commit", "6288bbb")
print("revert 6288bbb:", ((r2.stdout or "") + (r2.stderr or "")).strip().splitlines()[:2])
st = git("status", "--porcelain").stdout.strip()
print("工作区改动:", st.splitlines()[:8] if st else "(无)")
conf = [l for l in st.splitlines() if l.startswith("UU") or l.startswith("AA")]
if conf:
    print("✗ 有冲突:", conf)
    sys.exit(1)

MSG = """revert(ar): 按用户要求撤掉 AR 录屏（保留相机录像）

用户明确表示"别做AR录屏"。撤销两个提交：
  · 6288bbb feat(ar): AR 录屏（MediaProjection）…
  · 22dd880 feat(ar): AR 录屏补齐前台服务…
同时删除 ArRecordService.kt 与 manifest 中的
FOREGROUND_SERVICE_MEDIA_PROJECTION 权限、服务声明。

保留不动（这些是用户先前要的相机能力）：
  · 7505307 fix(ar): 相机录像（CameraX VideoCapture + FileOutputOptions）
  · 拍照成片合成、存相册、缩略图、对焦、变焦、档位、EV、闪光、手电、网格、水平仪、定时、连拍
"""
msg = os.path.join(MAP, "_msg_arrevert.txt")
io.open(msg, "w", encoding="utf-8", newline="\n").write(MSG)
rc = git("commit", "-F", msg)
print("提交:", ((rc.stdout or rc.stderr or "").strip().splitlines() or [""])[0][:110])

# ② 校验源码状态
AR = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/ArScreen.kt")
MAN = os.path.join(CHAT, "app/src/main/AndroidManifest.xml")
src = io.open(AR, encoding="utf-8").read()
man = io.open(MAN, encoding="utf-8").read()
svc = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ArRecordService.kt")
print()
print("=== 源码校验 ===")
print("   AR录屏按钮残留:", "AR录屏" in src, "（应为 False）")
print("   MediaProjection 残留:", "MediaProjection" in src, "（应为 False）")
print("   ArRecordService 文件:", os.path.exists(svc), "（应为 False）")
print("   前台服务权限残留:", "FOREGROUND_SERVICE_MEDIA_PROJECTION" in man, "（应为 False）")
print("   相机录像保留:", "VideoCapture" in src, "✓（应为 True）")
print("   模式切换保留:", 'SmallBtn(if (videoMode) "录像" else "拍照"' in src, "（应为 True）")

# ③ 编译 + 装机
print()
print("=== 编译 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o.splitlines() if x.startswith("e: ")][:6]:
    print("   " + y[:220])
if r.returncode != 0:
    print("   ✗ 编译失败")
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
        return True
    return False


def texts(xml):
    return [t for t in re.findall(r'text="([^"]*)"', xml) if t.strip()]


sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", PKG)
time.sleep(4)
sh("am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(14)
tap(box_any(["聊天"], dump("e0")))
time.sleep(6)
tap(box_any(["☰"], dump("e1")))
time.sleep(4)
z = dump("e2")
tap(box_any(["⚙  设置", "设置"], z))
time.sleep(4)
tap(box_any(["AR 模式（实景 + 桌宠）"], dump("e3")))
time.sleep(14)
z = dump("e4")
tx = texts(z)
print()
print("=== 设备实测 ===")
print("   AR 页控件:", tx[:16])
print("   「AR录屏」按钮是否还在:", any("AR录屏" in t for t in tx), "（应为 False ✓）")
print("   「拍照」模式按钮在:", any(t == "拍照" for t in tx), "（应为 True ✓）")
p = os.path.join(TMP, "ar_no_arrec.png")
with io.open(p, "wb") as f:
    q = subprocess.run([ADB, "exec-out", "screencap", "-p"], stdout=subprocess.PIPE, timeout=180)
    f.write(q.stdout or b"")
print("   截图:", p, os.path.getsize(p))
print("未推送:", subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                                capture_output=True, text=True).stdout.strip(), "条")
