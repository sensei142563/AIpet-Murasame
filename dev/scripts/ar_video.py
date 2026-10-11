# -*- coding: utf-8 -*-
"""录像：VideoCapture+Recorder，拍照/录像模式切换，红点计时，存 Movies/AIpet → 编译装机实测。"""
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

s = io.open(AR, encoding="utf-8").read().replace("\r\n", "\n")
ok = True


def note(m, c):
    global ok
    print(("✓ " if c else "✗ ") + m)
    if not c:
        ok = False


# ① 导入
need = ["androidx.camera.video.MediaStoreOutputOptions", "androidx.camera.video.Quality",
        "androidx.camera.video.QualitySelector", "androidx.camera.video.Recorder",
        "androidx.camera.video.Recording", "androidx.camera.video.VideoCapture",
        "androidx.camera.video.VideoRecordEvent"]
anchor = "import androidx.camera.core.resolutionselector.ResolutionSelector\n"
if anchor in s:
    add = "".join("import %s\n" % i for i in need if ("import %s\n" % i) not in s)
    s = s.replace(anchor, anchor + add, 1)
note("补充 video 相关导入", all(("import %s\n" % i) in s for i in need))

# ② 状态
if "videoMode" not in s:
    s = s.replace("    var evMax by remember { mutableStateOf(0) }\n",
                  "    var evMax by remember { mutableStateOf(0) }\n"
                  "    // 录像：模式开关、当前录制对象、已录秒数\n"
                  "    var videoMode by remember { mutableStateOf(false) }\n"
                  "    var recording by remember { mutableStateOf<Recording?>(null) }\n"
                  "    var recSec by remember { mutableStateOf(0) }\n", 1)
note("状态 videoMode/recording/recSec", "var videoMode" in s)

# ③ 绑定时同时准备 VideoCapture，并按模式选择绑定
old_bind = """                    val cap = ImageCapture.Builder()
                        .setCaptureMode(ImageCapture.CAPTURE_MODE_MAXIMIZE_QUALITY)
                        .setResolutionSelector(selector)
                        .build()
                    imageCapture = cap
                    p.unbindAll()
                    camera = p.bindToLifecycle(
                        lifecycleOwner,
                        if (useFront) CameraSelector.DEFAULT_FRONT_CAMERA
                        else CameraSelector.DEFAULT_BACK_CAMERA,
                        preview, cap,
                    )"""
new_bind = """                    val cap = ImageCapture.Builder()
                        .setCaptureMode(ImageCapture.CAPTURE_MODE_MAXIMIZE_QUALITY)
                        .setResolutionSelector(selector)
                        .build()
                    imageCapture = cap
                    val rec = Recorder.Builder()
                        .setQualitySelector(QualitySelector.from(Quality.HD))
                        .build()
                    val vcap = VideoCapture.withOutput(rec)
                    videoCapture = vcap
                    p.unbindAll()
                    camera = p.bindToLifecycle(
                        lifecycleOwner,
                        if (useFront) CameraSelector.DEFAULT_FRONT_CAMERA
                        else CameraSelector.DEFAULT_BACK_CAMERA,
                        preview,
                        if (videoMode) vcap else cap,
                    )"""
if old_bind in s:
    s = s.replace(old_bind, new_bind, 1)
    note("绑定支持录像", True)
else:
    note("绑定支持录像（锚点未命中）", False)

# ④ videoCapture 状态 + LaunchedEffect 依赖 videoMode
if "var videoCapture" not in s:
    s = s.replace("    var imageCapture by remember { mutableStateOf<ImageCapture?>(null) }\n",
                  "    var imageCapture by remember { mutableStateOf<ImageCapture?>(null) }\n"
                  "    var videoCapture by remember { mutableStateOf<VideoCapture<Recorder>?>(null) }\n", 1)
note("videoCapture 状态", "var videoCapture" in s)
s = s.replace("LaunchedEffect(provider, useFront) {", "LaunchedEffect(provider, useFront, videoMode) {", 1)
note("LaunchedEffect 依赖 videoMode", "useFront, videoMode" in s)

# ⑤ 快门 onTap：录像模式走录制/停止
old_tap = """            if (timerSec > 0) {
                                                countdown = timerSec"""
if "videoMode" in s and "if (videoMode) {" not in s:
    # 在 onTap 开头插入录像分支
    lines = s.splitlines(keepends=True)
    oi = next((i for i, l in enumerate(lines) if l.strip() == "onTap = {"), None)
    if oi is not None:
        ind = re.match(r"(\s*)", lines[oi]).group(1) + "    "
        branch = [
            "if (videoMode) {",
            "    val rec = recording",
            "    if (rec != null) {",
            "        runCatching { rec.stop() }",
            "        recording = null",
            "        recSec = 0",
            "    } else {",
            "        val vc = videoCapture",
            "        if (vc != null) {",
            '            val name2 = "AIpet_" + SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date()) + ".mp4"',
            "            val values2 = ContentValues().apply {",
            "                put(MediaStore.Video.Media.DISPLAY_NAME, name2)",
            '                put(MediaStore.Video.Media.MIME_TYPE, "video/mp4")',
            "                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {",
            '                    put(MediaStore.Video.Media.RELATIVE_PATH, "Movies/AIpet")',
            "                }",
            "            }",
            "            val opts = MediaStoreOutputOptions",
            "                .Builder(ctx.contentResolver, values2).build()",
            "            runCatching {",
            "                recording = vc.output",
            "                    .prepareRecording(ctx, opts)",
            "                    .start(ContextCompat.getMainExecutor(ctx)) { e ->",
            "                        when (e) {",
            "                            is VideoRecordEvent.Status -> recSec =",
            "                                (e.recordingStats.recordedDurationNanos / 1_000_000_000L).toInt()",
            "                            is VideoRecordEvent.Finalize -> {",
            "                                recording = null",
            "                                recSec = 0",
            '                                notice = if (e.hasError()) "录像失败：" + e.error',
            '                                    else "已保存到相册：Movies/AIpet"',
            "                            }",
            "                        }",
            "                    }",
            '                notice = "录像中…"',
            '            }.onFailure { notice = "录像失败：" + it.message }',
            "        } else {",
            '            notice = "录像不可用：相机未就绪"',
            "        }",
            "    }",
            "    return@detectTapGestures",
            "}",
        ]
        lines[oi + 1:oi + 1] = [(ind + b + "\n") for b in branch]
        s = "".join(lines)
        note("快门支持录制/停止", "if (videoMode) {" in s)
    else:
        note("快门支持录制（找不到 onTap）", False)

    else:
        note("快门支持录制（找不到 onTap 锚点）", False)

# ⑥ 模式切换按钮（加进水平那行）
if 'SmallBtn("录像"' not in s and 'SmallBtn("拍照"' not in s:
    old_row = '                        SmallBtn("水平", showLevel) { showLevel = !showLevel }\n'
    if old_row in s:
        s = s.replace(old_row, old_row +
                      '                        Spacer(Modifier.width(10.dp))\n'
                      '                        // 拍照 / 录像 模式切换\n'
                      '                        SmallBtn(if (videoMode) "录像" else "拍照", videoMode) { videoMode = !videoMode }\n', 1)
        note("模式切换按钮", "videoMode = !videoMode" in s)
    else:
        note("模式切换按钮（锚点未命中）", False)

# ⑦ 录制中的红点 + 秒数
if "recording != null" not in s:
    fi = s.index("            if (flash) {")
    s = s[:fi] + ("            if (recording != null) {\n"
                  "                Row(Modifier.fillMaxWidth().padding(top = 44.dp),\n"
                  "                    horizontalArrangement = Arrangement.Center,\n"
                  "                    verticalAlignment = Alignment.CenterVertically) {\n"
                  "                    Box(Modifier.size(12.dp).background(Color(0xFFE53935), CircleShape))\n"
                  "                    Spacer(Modifier.width(8.dp))\n"
                  '                    Text("REC " + recSec + "s", color = Color(0xFFFF8A80), fontSize = 14.sp)\n'
                  "                }\n"
                  "            }\n\n") + s[fi:]
    note("录制红点与计时", "REC " in s)

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


def vids():
    return re.findall(r"(AIpet_\d+_\d+\.mp4)", sh("ls", "/sdcard/Movies/AIpet/"))


def dump(tag):
    sh("uiautomator", "dump", "/sdcard/%s.xml" % tag)
    subprocess.run([ADB, "pull", "/sdcard/%s.xml" % tag, os.path.join(TMP, "%s.xml" % tag)],
                   capture_output=True, timeout=60)
    try:
        return io.open(os.path.join(TMP, "%s.xml" % tag), encoding="utf-8", errors="replace").read()
    except Exception:
        return ""


def bt(label, xml):
    m = re.search(r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % re.escape(label), xml)
    return None if not m else (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))


def tap(b):
    if b:
        sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
        return True
    return False


sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", PKG)
time.sleep(3)
sh("am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(10)
tap(bt("聊天", dump("y0")))
time.sleep(5)
tap(bt("☰", dump("y1")))
time.sleep(3)
z = dump("y2")
tap(bt("⚙  设置", z) if bt("⚙  设置", z) else bt("设置", z))
time.sleep(3)
tap(bt("AR 模式（实景 + 桌宠）", dump("y3")))
time.sleep(12)
z = dump("y4")
print("① 模式按钮:", bt("拍照", z), "（点它切到录像）")
tap(bt("拍照", z))
time.sleep(6)
z = dump("y5")
print("   切换后按钮:", bt("录像", z))
print("② 点快门开始录像 (612,2010)")
sh("input", "tap", "612", "2010")
time.sleep(4)
z = dump("y6")
rec = [t for t in re.findall(r'text="([^"]*)"', z) if "REC" in t]
print("   录制状态文字:", rec)
time.sleep(6)
print("③ 再点快门停止")
sh("input", "tap", "612", "2010")
time.sleep(6)
z = dump("y7")
print("   提示:", [t for t in re.findall(r'text="([^"]*)"', z) if "已保存" in t or "失败" in t][:2])
print("④ Movies/AIpet 里的视频:", vids())
p = os.path.join(TMP, "video_state.png")
with io.open(p, "wb") as f:
    q = subprocess.run([ADB, "exec-out", "screencap", "-p"], stdout=subprocess.PIPE, timeout=180)
    f.write(q.stdout or b"")
print("   截图:", p, os.path.getsize(p))

MSG = """feat(ar): 录像（CameraX VideoCapture + Recorder），对标系统相机

  · 绑定相机时同时构建 Recorder(H.264, Quality.HD) 的 VideoCapture；
    LaunchedEffect 依赖加入 videoMode —— 拍照模式绑 ImageCapture、录像模式绑 VideoCapture；
  · 新增「拍照 / 录像」模式切换按钮（在「水平」同一行）；
  · 录像模式下快门变为开始/结束录制：
      开始：MediaStoreOutputOptions 写 Movies/AIpet（AIpet_时间戳.mp4），
            VideoRecordEvent.Status 更新已录秒数、Finalize 收尾并给出提示；
      停止：recording.stop()；
  · 录制中画面顶部显示红点 + "REC n s"。
未知项：合成录像（把 Live2D 桌宠录进视频）需要逐帧抓 GL，本版未做，视频是纯相机画面。
"""
msg = os.path.join(MAP, "_msg_video.txt")
io.open(msg, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r3 = subprocess.run(["git", "-C", CHAT, "commit", "-F", msg], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("提交:", (r3.stdout or r3.stderr or "").splitlines()[0][:100])
print("未推送:", subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                                capture_output=True, text=True).stdout.strip(), "条")
