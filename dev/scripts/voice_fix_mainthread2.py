# -*- coding: utf-8 -*-
"""把整个合成块（请求+读体+落盘）包进 Dispatchers.IO → 编译装机 → 点测试 → pull 日志。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
VC = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/bot/chat/VoiceClient.kt")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
PKG = "com.aipet.murasame"
TMP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\shots"
MAP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\merge-map"
VL = "/sdcard/Android/data/%s/files/voice.log" % PKG
F5LOG = r"E:\university\order\python\pet\_audit_fish9269\_f5serve.log"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

L = io.open(VC, encoding="utf-8", newline="").read().splitlines(keepends=True)
# ① 已经把 execute 包过一层：先还原成普通 execute（避免嵌套）
s = "".join(L)
if "runBlocking" in s:
    s = re.sub(r"kotlinx\.coroutines\.runBlocking \{\n(\s*)kotlinx\.coroutines\.withContext\(kotlinx\.coroutines\.Dispatchers\.IO\) \{\n\s*http\.newCall\(req\)\.execute\(\)\n\s*\}\n(\s*)\}\.use \{ resp ->",
               r"http.newCall(req).execute().use { resp ->", s)
    io.open(VC, "w", encoding="utf-8", newline="").write(s)
    print("✓ 已还原此前的 execute 包装（改为整体包裹）")

L = io.open(VC, encoding="utf-8", newline="").read().splitlines(keepends=True)
i = next((k for k, l in enumerate(L) if "val ok = runCatching {" in l), None)
assert i is not None, "✗ 找不到 val ok = runCatching {"
eol = "\r\n" if L[i].endswith("\r\n") else "\n"
ind = re.match(r"(\s*)", L[i]).group(1)
L[i] = (ind + "// 整块（建连+读响应体+落盘）都必须在 IO 线程：主线程做任何一步都会抛" + eol +
        ind + "// NetworkOnMainThreadException（只包 execute() 不够，读 body 同样是网络操作）。" + eol +
        ind + "val ok = kotlinx.coroutines.runBlocking {" + eol +
        ind + "    kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {" + eol +
        ind + "        runCatching {" + eol)
j = next(k for k in range(i, len(L)) if ".getOrElse { e -> log(" in L[k])
L[j] = L[j].rstrip("\r\n") + " } }" + eol
io.open(VC, "w", encoding="utf-8", newline="").write("".join(L))
print("=== 改后 ===")
for k in range(i, min(len(L), j + 3)):
    print("   %5d| %s" % (k + 1, L[k].rstrip()[:116]))

print("=== 编译 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o.splitlines() if x.startswith("e: ")][:6]:
    print("   " + y[:140])
if r.returncode != 0:
    subprocess.run(["git", "-C", CHAT, "checkout", "--",
                    "app/src/main/java/com/aipet/murasame/bot/chat/VoiceClient.kt"], capture_output=True)
    print("   ✗ 回滚")
    sys.exit(1)


def itime():
    t = subprocess.run([ADB, "shell", "dumpsys", "package", PKG], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=300).stdout
    m = re.search(r"lastUpdateTime=([^\n]+)", t)
    return m.group(1).strip() if m else "?"


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


def box(label, xml):
    m = re.search(r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % re.escape(label), xml)
    return None if not m else (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))


def tap(b):
    if b:
        sh("input", "tap", str((b[0] + b[2]) // 2), str((b[1] + b[3]) // 2))
        return True
    return False


subprocess.run([ADB, "reverse", "tcp:28565", "tcp:28565"], capture_output=True)
subprocess.run([ADB, "reverse", "tcp:9881", "tcp:9881"], capture_output=True)
sh("input", "keyevent", "KEYCODE_WAKEUP")
sh("am", "force-stop", PKG)
time.sleep(3)
sh("am", "start", "-n", "%s/.MainActivity" % PKG)
time.sleep(10)
tap(box("聊天", dump("y0")))
time.sleep(5)
tap(box("☰", dump("y1")))
time.sleep(3)
z = dump("y2")
tap(box("⚙  设置", z) if box("⚙  设置", z) else box("设置", z))
time.sleep(3)
z = dump("y3")
row = box("测试电脑语音", z)
print("   行:", row)
sh("rm", "-f", VL)
f50 = os.path.getsize(F5LOG) if os.path.isfile(F5LOG) else 0
tap(row)
for k in range(7):
    time.sleep(8)
    if os.path.isfile(F5LOG) and os.path.getsize(F5LOG) > f50:
        if "/infer" in io.open(F5LOG, encoding="utf-8", errors="replace").read()[f50:]:
            print("   ✓ F5 收到 /infer（%ds）" % ((k + 1) * 8))
            break
    print("   %ds …" % ((k + 1) * 8))
print()
print("=== ★ voice.log ===")
dst = os.path.join(TMP, "phone_voice9.log")
subprocess.run([ADB, "pull", VL, dst], capture_output=True, timeout=120)
content = io.open(dst, encoding="utf-8", errors="replace").read() if os.path.isfile(dst) else ""
print(content or "   （没有 ✗）")
print("=== 判定 ===")
print("   ✅✅✅✅ TTS 成功！" if "成功播放" in content else
      ("   ⚠ 仍异常 → " + str([l for l in content.splitlines() if "异常" in l][:1]) if "异常" in content else "   ? 见日志"))

MSG = """fix(voice): 把整个合成块放进 IO 线程（只包 execute() 不够，读 body 同样是网络操作）

上一版只把 http.newCall(req).execute() 放进 Dispatchers.IO，真机仍报
NetworkOnMainThreadException —— 因为 resp.body?.bytes() 读取响应体仍在主线程执行。

本次把整个 runCatching 合成块（建连、读响应体、校验 RIFF、写缓存文件）整体包进
kotlinx.coroutines.runBlocking { withContext(Dispatchers.IO) { ... } }，
返回值与调用方接口不变。后续可再优化为真正异步，避免主线程等待合成（约 6 秒）。
"""
msg = os.path.join(MAP, "_msg_netmainthread2.txt")
io.open(msg, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r3 = subprocess.run(["git", "-C", CHAT, "commit", "-F", msg], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("提交:", (r3.stdout or r3.stderr or "").splitlines()[0][:100])
print("未推送:", subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                                capture_output=True, text=True).stdout.strip(), "条")
