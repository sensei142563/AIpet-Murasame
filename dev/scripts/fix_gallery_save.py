# -*- coding: utf-8 -*-
"""修「存进相册」：分区感知 MediaStore(IS_PENDING) + 旧版公共目录 + MediaScanner 通知 + 补权限 + 如实报错 → 编译装机。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
AR = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/ArScreen.kt")
MAN = os.path.join(CHAT, "app/src/main/AndroidManifest.xml")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
PKG = "com.aipet.murasame"
MAP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\merge-map"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

# ① manifest 补 WRITE_EXTERNAL_STORAGE（只对 API<=28 生效）
m = io.open(MAN, encoding="utf-8", newline="").read()
if "WRITE_EXTERNAL_STORAGE" not in m:
    m = m.replace('<uses-permission android:name="android.permission.CAMERA" />',
                  '<uses-permission android:name="android.permission.CAMERA" />\n'
                  '    <!-- Android 9 及以下把照片写入公共相册需要它；10+ 用 MediaStore 不需要 -->\n'
                  '    <uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE"\n'
                  '        android:maxSdkVersion="28" />', 1)
    io.open(MAN, "w", encoding="utf-8", newline="").write(m)
    print("✓ manifest 已加 WRITE_EXTERNAL_STORAGE(maxSdkVersion=28)")

# ② 替换 shoot / saveShot 为分区感知 + 通知相册 + 如实报错
L = io.open(AR, encoding="utf-8", newline="").read().splitlines(keepends=True)
i = next((k for k, l in enumerate(L) if "private fun shoot(" in l), None)
j = next((k for k, l in enumerate(L) if "@Composable" in l and k > i and "private fun Btn" in L[k + 1]), None)
assert i is not None and j is not None, "✗ 定位 shoot/saveShot 失败"
eol = "\r\n" if L[i].endswith("\r\n") else "\n"
NEW = '''/** 快门：PixelCopy 抓当前窗口画面（相机 + 桌宠）→ 存进系统相册。 */
private fun shoot(ctx: android.content.Context, report: (String) -> Unit) {
    val win = (ctx as? android.app.Activity)?.window
    if (win == null) { report("拍照失败：取不到窗口"); return }
    runCatching {
        val w = win.decorView.width
        val h = win.decorView.height
        if (w <= 0 || h <= 0) { report("拍照失败：窗口尺寸为 0"); return }
        val bmp = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888)
        PixelCopy.request(win, bmp, { r ->
            if (r == PixelCopy.SUCCESS) {
                report(saveShot(ctx, bmp))
            } else {
                report("拍照失败：PixelCopy=" + r)
            }
        }, Handler(Looper.getMainLooper()))
    }.onFailure { report("拍照异常：" + it.javaClass.simpleName + " / " + it.message) }
}

/**
 * 存图进系统相册。返回值是给用户看的真实结果（成功给文件名，失败给原因）。
 *   API >= 29：MediaStore + IS_PENDING 流程（相册立即能看到）
 *   API < 29 ：写公共 Pictures/AIpet，再用 MediaScanner 通知相册（否则相册不会扫到）
 * 另外始终在应用外部目录留一份，便于 adb pull 取证。
 */
private fun saveShot(ctx: android.content.Context, bmp: Bitmap): String {
    val stamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
    val name = "AIpet_" + stamp + ".png"
    val errs = StringBuilder()

    // 外部目录留档（一定成功，用于取证）
    runCatching {
        val dir = File(ctx.getExternalFilesDir(null), "ar").apply { mkdirs() }
        File(dir, name).outputStream().use { bmp.compress(Bitmap.CompressFormat.PNG, 100, it) }
        android.util.Log.i("ArScreen", "saved " + File(dir, name).absolutePath)
    }.onFailure { errs.append("外部分区失败:").append(it.message).append("; ") }

    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
        // ① Android 10+：MediaStore 标准流程
        val ok = runCatching {
            val values = ContentValues().apply {
                put(MediaStore.Images.Media.DISPLAY_NAME, name)
                put(MediaStore.Images.Media.MIME_TYPE, "image/png")
                put(MediaStore.Images.Media.RELATIVE_PATH, "Pictures/AIpet")
                put(MediaStore.Images.Media.IS_PENDING, 1)
            }
            val uri = ctx.contentResolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values)
                ?: return@runCatching false
            ctx.contentResolver.openOutputStream(uri)?.use {
                bmp.compress(Bitmap.CompressFormat.PNG, 100, it)
            }
            values.clear()
            values.put(MediaStore.Images.Media.IS_PENDING, 0)
            ctx.contentResolver.update(uri, values, null, null)
            true
        }.getOrElse { e -> errs.append("MediaStore失败:").append(e.message).append("; "); false }
        if (ok) return "已保存到相册：Pictures/AIpet/" + name
    } else {
        // ② Android 9 及以下：写公共目录 + 通知相册
        val ok = runCatching {
            @Suppress("DEPRECATION")
            val pub = android.os.Environment
                .getExternalStoragePublicDirectory(android.os.Environment.DIRECTORY_PICTURES)
            val dir = File(pub, "AIpet").apply { mkdirs() }
            val f = File(dir, name)
            f.outputStream().use { bmp.compress(Bitmap.CompressFormat.PNG, 100, it) }
            android.media.MediaScannerConnection.scanFile(
                ctx, arrayOf(f.absolutePath), arrayOf("image/png"), null)
            true
        }.getOrElse { e -> errs.append("公共目录失败:").append(e.message).append("; "); false }
        if (ok) return "已保存到相册：Pictures/AIpet/" + name
    }

    // 兜底：至少在应用外部目录里有一份
    runCatching {
        val dir = File(ctx.getExternalFilesDir(null), "ar")
        android.media.MediaScannerConnection.scanFile(
            ctx, arrayOf(File(dir, name).absolutePath), arrayOf("image/png"), null)
    }
    return if (errs.isEmpty()) "已保存（外部目录）" else "相册写入失败：" + errs.toString().take(120)
}

'''
L[i:j] = [NEW]
io.open(AR, "w", encoding="utf-8", newline="").write("".join(L))
print("✓ 已替换 shoot/saveShot（分区感知 + MediaScanner + 如实报错）")

print("=== 编译 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o.splitlines() if x.startswith("e: ")][:8]:
    print("   " + y[:150])
if r.returncode != 0:
    print("   ✗ 编译失败 —— 保留文件供下轮继续")
    sys.exit(1)


def itime():
    t = subprocess.run([ADB, "shell", "dumpsys", "package", PKG], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=300).stdout
    mm = re.search(r"lastUpdateTime=([^\\n]+)", t)
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

MSG = """fix(ar): 拍照真正存进系统相册（分区感知 + MediaScanner 通知 + 如实报错）

用户反馈"拍摄不会被手机相册扫到"。排查：
  · minSdk 26 / targetSdk 36，而 manifest 里**没有** WRITE_EXTERNAL_STORAGE ——
    Android 9 及以下写公共相册必须有它；
  · 旧实现只在 API>=Q 时才设 RELATIVE_PATH，且没有 MediaScanner 通知；
  · 更糟的是 runCatching 把失败也当成"已保存"，界面上看不到真实原因。

本次：
  · manifest 增加 WRITE_EXTERNAL_STORAGE（maxSdkVersion=28）
  · API>=29：MediaStore + IS_PENDING 标准流程（写入后置 PENDING=0，相册立即可见）
  · API<29：写公共 Pictures/AIpet，并用 MediaScannerConnection.scanFile 主动通知相册
  · saveShot 返回真实结果字符串（成功给文件名，失败给具体原因），界面与 Toast 如实显示
  · 始终在 getExternalFilesDir/ar/ 留一份便于 adb pull 取证
"""
msg = os.path.join(MAP, "_msg_gallery.txt")
io.open(msg, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r3 = subprocess.run(["git", "-C", CHAT, "commit", "-F", msg], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("提交:", (r3.stdout or r3.stderr or "").splitlines()[0][:100])
print("未推送:", subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                                capture_output=True, text=True).stdout.strip(), "条")
