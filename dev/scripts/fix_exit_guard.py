# -*- coding: utf-8 -*-
"""两道保险：
  ① NavigationBar 底部内边距 48dp → 80dp（把 tab 文字抬出手势区）
  ② BackHandler：任何页面切换都清零退出计时（乱点永远不会累计成退出）
然后编译装机。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
F = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/MainActivity.kt")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

t = io.open(F, encoding="utf-8").read().replace("\r\n", "\n")

# ---------- ② 逻辑保险：页面切换即清零退出计时 ----------
old_bh = '''        BackHandler(enabled = true) {
            when {
                tabHistory.isNotEmpty() -> tab = tabHistory.removeAt(tabHistory.size - 1)
                tab != 0 -> tab = 0
                else -> {
                    val now = System.currentTimeMillis()
                    if (now - lastBackAt < 2000L) {
                        actRef?.finish()
                    } else {
                        lastBackAt = now
                        Toast.makeText(app, "再按一次返回键退出", Toast.LENGTH_SHORT).show()
                    }
                }
            }
        }'''
new_bh = '''        BackHandler(enabled = true) {
            when {
                // 真机实测教训：华为手势导航**不显示导航栏、也不报 navigationBars inset**，
                // 但屏幕底部一条仍会吃掉触摸并把它当成 BACK。于是"点底部 tab"会连续产生
                // 多次 BACK：第一次从聊天页退回首页、后面几次就撞进"再按一次退出" ⇒ 用户
                // 描述为"一到聊天页就闪退"（系统 crash buffer / dropbox 里什么都没有，
                // 因为这是**我们自己调用的 finish()**）。
                // 保险：只要发生了页面切换，就把退出计时清零 —— 乱点最多切页面，永远不会退出。
                tabHistory.isNotEmpty() -> {
                    tab = tabHistory.removeAt(tabHistory.size - 1)
                    lastBackAt = 0L
                }
                tab != 0 -> {
                    tab = 0
                    lastBackAt = 0L
                }
                else -> {
                    val now = System.currentTimeMillis()
                    if (lastBackAt != 0L && now - lastBackAt in 1..2000L) {
                        actRef?.finish()
                    } else {
                        lastBackAt = now
                        Toast.makeText(app, "再按一次返回键退出", Toast.LENGTH_SHORT).show()
                    }
                }
            }
        }'''
if old_bh in t:
    t = t.replace(old_bh, new_bh, 1)
    print("✓ ② BackHandler 已加「页面切换清零计时」")
else:
    print("✗ BackHandler 锚点未命中")
    sys.exit(1)

# ---------- ① 抬高：80dp ----------
old_nav = '''                NavigationBar(containerColor = MaterialTheme.colorScheme.surface) {'''
new_nav = '''                NavigationBar(
                    // 手势导航机型底部约 216px 不报 inset 但吃触摸 ⇒ 显式把 tab 抬起来，
                    // 文字中心约 y2455（屏幕高 2776），越出被吞掉的区域。
                    modifier = Modifier.padding(bottom = 80.dp),
                    containerColor = MaterialTheme.colorScheme.surface
                ) {'''
if old_nav in t:
    t = t.replace(old_nav, new_nav, 1)
    for imp in ("import androidx.compose.foundation.layout.padding", "import androidx.compose.ui.unit.dp"):
        if imp not in t:
            t = t.replace("import androidx.compose.foundation.layout.WindowInsets",
                          "import androidx.compose.foundation.layout.WindowInsets\n" + imp, 1)
    print("✓ ① NavigationBar 底部内边距 80dp")
else:
    print("✗ NavigationBar 锚点未命中")
    sys.exit(1)

io.open(F, "w", encoding="utf-8", newline="\n").write(t)

print()
print("=== 编译 + 装机 ===")
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
print("   装机：" + ((r2.stdout or r2.stderr or "").strip().splitlines() or ["(无)"])[-1][:120])
