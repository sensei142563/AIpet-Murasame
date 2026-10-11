# -*- coding: utf-8 -*-
"""修录像保存：录制完成后把 mp4 转存进系统相册（Movies/AIpet，MediaStore+IS_PENDING）→ 编译装机 → 实拍验证。"""
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

L = io.open(AR, encoding="utf-8").read().replace("\r\n", "\n").splitlines(keepends=True)
ok = True


def note(m, c):
    global ok
    print(("✓ " if c else "✗ ") + m)
    if not c:
        ok = False


# 找 Finalize 成功分支里的 scanFile 调用（录像落相册）
i = next((k for k, l in enumerate(L) if "MediaScannerConnection.scanFile(" in l and "video/mp4" in L[k + 1]), None)
note("定位录像的 scanFile 行", i is not None)
if i is not None:
    # 它的上一层是 runCatching {，向上找；向下找到该 runCatching 的结束 }
    u = i
    while u > 0 and "runCatching {" not in L[u]:
        u -= 1
    d = i
    dd = 0
    k = u
    while k < len(L):
        dd += L[k].count("{") - L[k].count("}")
        if dd <= 0 and k > u:
            break
        k += 1
    ind = re.match(r"(\s*)", L[u]).group(1)
    new = [
        ind + "// 录制完成后转存进系统相册（应用私有目录相册扫不到，必须走 MediaStore 公共目录）\n",
        ind + "runCatching {\n",
        ind + "    val vv = ContentValues().apply {\n",
        ind + "        put(MediaStore.Video.Media.DISPLAY_NAME, vname)\n",
        ind + '        put(MediaStore.Video.Media.MIME_TYPE, "video/mp4")\n',
        ind + "        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {\n",
        ind + '            put(MediaStore.Video.Media.RELATIVE_PATH, "Movies/AIpet")\n',
        ind + "            put(MediaStore.Video.Media.IS_PENDING, 1)\n",
        ind + "        }\n",
        ind + "    }\n",
        ind + "    val vuri = ctx.contentResolver.insert(MediaStore.Video.Media.EXTERNAL_CONTENT_URI, vv)\n",
        ind + "    if (vuri != null) {\n",
        ind + "        ctx.contentResolver.openOutputStream(vuri)?.use { out ->\n",
        ind + "            vfile.inputStream().use { ins -> ins.copyTo(out) }\n",
        ind + "        }\n",
        ind + "        val vdone = ContentValues().apply { put(MediaStore.Video.Media.IS_PENDING, 0) }\n",
        ind + "        ctx.contentResolver.update(vuri, vdone, null, null)\n",
        ind + "    }\n",
        ind + "}\n",
    ]
    L[u:k + 1] = new
    note("已改为 MediaStore 转存到 Movies/AIpet", "Movies/AIpet" in "".join(L))

# 提示文字改成能一眼看出存哪了
s = "".join(L)
if '"已保存：" + vname' in s:
    s = s.replace('notice = "已保存：" + vname', 'notice = "已保存到相册：Movies/AIpet/" + vname', 1)
    note("提示文字改为 Movies/AIpet", "已保存到相册：Movies/AIpet/" in s)

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


def tap(b):
    if b:
        sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
        return True
    return False


def texts(xml):
    return [t for t in re.findall(r'text="([^"]*)"', xml) if t.strip()]


def gallery_videos():
    out = sh("content", "query", "--uri", "content://media/external/video/media",
             "--projection", "_display_name:_data")
    return re.findall(r"_display_name=(AIpet_\d+_\d+\.mp4)", out)


print()
print("=== 进 AR 录一段（长按快门）验证 ===")
sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", PKG)
time.sleep(4)
sh("am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(14)
tap(box_any(["聊天"], dump("v0")))
time.sleep(6)
tap(box_any(["☰"], dump("v1")))
time.sleep(4)
z = dump("v2")
tap(box_any(["⚙  设置", "设置"], z))
time.sleep(4)
tap(box_any(["AR 模式（实景 + 桌宠）"], dump("v3")))
time.sleep(14)
z = dump("v4")
a = box_any(["相册"], z)
sy = ((a[1] + a[3]) // 2) if a else 2123
print("   相册框 %s → 快门中心推定 (612,%d)" % (a, sy))
print("   长按开始 ...")
sh("input", "swipe", "612", str(sy), "612", str(sy), "900")
time.sleep(6)
print("   状态:", [t for t in texts(dump("v5")) if "REC" in t or "录像" in t][:2])
time.sleep(8)
print("   再长按停止 ...")
sh("input", "swipe", "612", str(sy), "612", str(sy), "900")
time.sleep(10)
z = dump("v6")
print("   提示:", [t for t in texts(z) if "已保存" in t or "失败" in t][:2])
print()
print("=== 相册视频表里有没有它 ===")
gv = gallery_videos()
print("   相册中的 AIpet_*.mp4:", gv)
print("   判定:", "✓ 已进相册" if gv else "✗ 相册里仍没有")
p = os.path.join(TMP, "video_gallery_check.png")
with io.open(p, "wb") as f:
    q = subprocess.run([ADB, "exec-out", "screencap", "-p"], stdout=subprocess.PIPE, timeout=180)
    f.write(q.stdout or b"")
print("   截图:", p)

MSG = """fix(ar): 录像改存进系统相册（原来只在应用私有目录，相册看不到）

用户反馈"AR录像 不知道是录制失败还是保存错了"。查真机：
  · ar/ 目录里 6 个 mp4 都在（6~16MB，录制本身是成功的）；
  · 但相册的视频表里只有用户旧的视频，没有 AIpet_*.mp4 —— 因为原来是写在
    Android/data/com.aipet.murasame/files/ar/（应用私有外部目录），
    Android 10+ 下 MediaScanner 扫不进这个目录，相册自然没有。
本次：录制完成后把 mp4 通过 MediaStore 转存到公共目录 Movies/AIpet
（insert → openOutputStream 拷贝 → IS_PENDING=0），与照片走同一条已验证可行的路；
提示文字也改成"已保存到相册：Movies/AIpet/xxx.mp4"。
"""
msg = os.path.join(MAP, "_msg_videogallery.txt")
io.open(msg, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r3 = subprocess.run(["git", "-C", CHAT, "commit", "-F", msg], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("提交:", (r3.stdout or r3.stderr or "").splitlines()[0][:110])
print("未推送:", subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                                capture_output=True, text=True).stdout.strip(), "条")
