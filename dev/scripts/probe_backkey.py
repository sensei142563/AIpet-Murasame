# -*- coding: utf-8 -*-
"""给所有 BackHandler 打点（全局 + ChatScreen 的 6 个），编译装机，
然后做一次受控返回键测试并读 diag.log —— 看第二次 BACK 到底被谁吃了。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
MA = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/MainActivity.kt")
CS = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/ChatScreen.kt")
SD = os.path.join(MAIN, "dev", "shots")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
PKG = "com.aipet.murasame"
EXT = "/sdcard/Android/data/%s/files" % PKG
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

# ---------- ① 全局 BackHandler 打点 ----------
t = io.open(MA, encoding="utf-8").read().replace("\r\n", "\n")
if 'Diag.log("Back", "全局 BackHandler' not in t:
    old = '''        BackHandler(enabled = true) {
            when {'''
    new = '''        BackHandler(enabled = true) {
            Diag.log("Back", "全局 BackHandler 收到 BACK：tab=" + tab
                + " history=" + tabHistory.size + " lastBackAt=" + lastBackAt)
            when {'''
    if old in t:
        t = t.replace(old, new, 1)
        # 各分支也记一下
        t = t.replace("                    tab = tabHistory.removeAt(tabHistory.size - 1)\n                    lastBackAt = 0L",
                      "                    tab = tabHistory.removeAt(tabHistory.size - 1)\n                    lastBackAt = 0L\n                    Diag.log(\"Back\", \"→ 回上一页 tab=\" + tab)",
                      1)
        t = t.replace("                tab != 0 -> {\n                    tab = 0\n                    lastBackAt = 0L\n                }",
                      "                tab != 0 -> {\n                    tab = 0\n                    lastBackAt = 0L\n                    Diag.log(\"Back\", \"→ 回首页（清零退出计时）\")\n                }",
                      1)
        t = t.replace("                        actRef?.finish()",
                      "                        Diag.log(\"Back\", \"→ 满足两次条件，调用 finish()\")\n                        actRef?.finish()",
                      1)
        t = t.replace('Toast.makeText(app, "再按一次返回键退出", Toast.LENGTH_SHORT).show()',
                      'Diag.log("Back", "→ 第一次确认，弹提示（2 秒内再按才退出）")\n'
                      '                        Toast.makeText(app, "再按一次返回键退出", Toast.LENGTH_SHORT).show()',
                      1)
        io.open(MA, "w", encoding="utf-8", newline="\n").write(t)
        print("✓ ① 全局 BackHandler 已打点")
    else:
        print("✗ ① 全局锚点未命中")
else:
    print("· 全局已有打点")

# ---------- ② ChatScreen 的 6 个子 handler 打点 ----------
c = io.open(CS, encoding="utf-8").read().replace("\r\n", "\n")
if 'Diag.log("Back", "ChatScreen' not in c:
    n = 0
    for name in ("showDrawer", "showPlus", "showSettings", "showVrm", "showVrmAr", "showAr"):
        old = "BackHandler(enabled = %s) { %s = false }" % (name, name)
        new = ('BackHandler(enabled = %s) { com.aipet.murasame.Diag.log("Back", "ChatScreen 子处理器 %s 吃掉 BACK"); %s = false }'
               % (name, name, name))
        if old in c:
            c = c.replace(old, new, 1)
            n += 1
    io.open(CS, "w", encoding="utf-8", newline="\n").write(c)
    print("✓ ② ChatScreen 子处理器已打点 %d 个" % n)
else:
    print("· ChatScreen 已有打点")

print()
print("=== ③ 编译 + 装机 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
for l in ((r.stdout or "") + (r.stderr or "")).splitlines():
    if l.strip().startswith("BUILD") or l.startswith("e: "):
        print("   " + l.strip()[:180])
if r.returncode != 0:
    sys.exit(1)
apk = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
r2 = subprocess.run([ADB, "-s", DEV, "install", "-r", "--no-streaming", apk],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
o2 = (r2.stdout or "") + (r2.stderr or "")
print("   装机:", [l for l in o2.splitlines() if "Success" in l or "Failure" in l][:1] or "?")


def adb(*a, timeout=300):
    x = subprocess.run([ADB, "-s", DEV, *a], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return (x.stdout or "") + (x.stderr or "")


def fg():
    for l in adb("shell", "dumpsys", "activity", "activities").splitlines():
        if "mResumedActivity" in l:
            return l.strip()[:70]
    return "(未知)"


print()
print("=== ④ 受控返回键测试（首页 → BACK → BACK）===")
adb("shell", "rm", "-f", EXT + "/diag.log")
adb("shell", "am", "force-stop", PKG)
time.sleep(1)
adb("shell", "am", "start", "-n", PKG + "/.MainActivity")
time.sleep(10)
print("   启动后前台:", fg())
# 点底部「首页」(111,2641)
adb("shell", "input", "tap", "111", "2641")
time.sleep(2.5)
print("   点首页后前台:", fg(), "  (按第一次 BACK)")
adb("shell", "input", "keyevent", "KEYCODE_BACK")
time.sleep(1.5)
print("   第一次后前台:", fg(), "  (按第二次 BACK)")
adb("shell", "input", "keyevent", "KEYCODE_BACK")
time.sleep(3.0)
print("   第二次后前台:", fg())

print()
print("=== diag.log 里的 Back 行 ===")
log = adb("shell", "cat", EXT + "/diag.log")
for l in [l for l in (log or "").splitlines() if "[Back]" in l]:
    print("   " + l.strip()[:170])
if not any("[Back]" in l for l in (log or "").splitlines()):
    print("   （没有 Back 行 —— 说明 BACK 根本没进到全局处理器）")
    print("   全部 diag 行：")
    for l in (log or "").splitlines()[-12:]:
        print("      " + l.strip()[:150])
