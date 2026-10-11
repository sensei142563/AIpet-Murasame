# -*- coding: utf-8 -*-
"""① 记忆页三个按钮从 trailing 槽移到内容区、等宽平分（修竖排）
   ② 首页 QQ 卡的文案改清楚 + 状态行说明电脑/手机两种跑法
然后编译 + 装机（装机需要你在手机上确认）。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
SRC = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame")
MS = os.path.join(SRC, "ui/MemoryScreen.kt")
HS = os.path.join(SRC, "ui/HomeScreen.kt")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
PKG = "com.aipet.murasame"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

# ---------- ① MemoryScreen ----------
t = io.open(MS, encoding="utf-8").read().replace("\r\n", "\n")
old = '''        SectionCard(
            title = "记忆文件",
            trailing = {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    TextButton(onClick = {
                        exportZip = true
                        exportLauncher.launch("chatter_记忆备份_$viewPetId.zip")
                    }) { Text("整包备份") }
                    TextButton(enabled = !ioBusy, onClick = {
                        exportBundleLauncher.launch("aipet_记忆互通_$viewPetId.json")
                    }) { Text("导出互通包") }
                    TextButton(enabled = !ioBusy, onClick = {
                        importBundleLauncher.launch(arrayOf("application/json", "text/plain", "*/*"))
                    }) { Text("导入互通包") }
                }
            }
        ) {
            if (files.isEmpty()) {'''
new = '''        SectionCard(title = "记忆文件") {
            // 这三个按钮原来塞在 SectionCard 的 trailing 槽里：那块地方窄，中文 5 个字放不下
            // 就被逐字折行，显示成竖排（用户反馈）。改成放在内容区、用 weight 等宽平分。
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(4.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                TextButton(
                    onClick = {
                        exportZip = true
                        exportLauncher.launch("chatter_记忆备份_$viewPetId.zip")
                    },
                    modifier = Modifier.weight(1f)
                ) { Text("整包备份", fontSize = 13.sp, maxLines = 1) }
                TextButton(
                    enabled = !ioBusy,
                    onClick = { exportBundleLauncher.launch("aipet_记忆互通_$viewPetId.json") },
                    modifier = Modifier.weight(1f)
                ) { Text("导出互通包", fontSize = 13.sp, maxLines = 1) }
                TextButton(
                    enabled = !ioBusy,
                    onClick = {
                        importBundleLauncher.launch(arrayOf("application/json", "text/plain", "*/*"))
                    },
                    modifier = Modifier.weight(1f)
                ) { Text("导入互通包", fontSize = 13.sp, maxLines = 1) }
            }
            Spacer(Modifier.height(4.dp))
            if (files.isEmpty()) {'''
if old in t:
    t = t.replace(old, new, 1)
    io.open(MS, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ ① 记忆页按钮改为内容区等宽平分")
else:
    print("✗ ① MemoryScreen 锚点未命中")

# ---------- ② HomeScreen 文案 ----------
h = io.open(HS, encoding="utf-8").read().replace("\r\n", "\n")
old_btn = '''                    Text(if (qqOpen) "收起 QQ 通道" else "打开 QQ 通道", fontSize = 15.sp,
                        fontWeight = androidx.compose.ui.text.font.FontWeight.Bold)'''
new_btn = '''                    Text(if (qqOpen) "收起 QQ 面板" else "打开 QQ 面板", fontSize = 15.sp,
                        fontWeight = androidx.compose.ui.text.font.FontWeight.Bold)'''
if old_btn in h:
    h = h.replace(old_btn, new_btn, 1)
    print("✓ ②a QQ 按钮文案改掉（打开 QQ 通道 → 打开 QQ 面板）")
else:
    print("✗ ②a 按钮锚点未命中")

old_line = '''                Text(qqLine, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)'''
new_line = '''                Text(qqLine, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                // 把"这是什么、有哪两种跑法"直接写在卡上（原来只有一句"打开 QQ 通道"，看不懂）
                Text(
                    "这里用的 QQ 通道有两种跑法：① 电脑上跑 api.py + NapCat，手机连电脑；" +
                        "② 手机自己跑 NapCat（Termux 里装），用设置里的「本机直连」——②更省事，装好后手机可脱离电脑。",
                    fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant
                )'''
if old_line in h:
    h = h.replace(old_line, new_line, 1)
    print("✓ ②b 已加两种跑法说明")
else:
    print("✗ ②b 说明锚点未命中")

h = h.replace('"NapCat：" + (if (on) "在线 ✓" else "离线（需在电脑上启动并登录）") +',
              '"NapCat：" + (if (on) "在线 ✓" else "离线（电脑端 NapCat 或手机本机 NapCat 未启动）") +', 1)
io.open(HS, "w", encoding="utf-8", newline="\n").write(h)

print()
print("=== 编译 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
for l in ((r.stdout or "") + (r.stderr or "")).splitlines():
    if l.strip().startswith("BUILD") or l.startswith("e: "):
        print("   " + l.strip()[:190])
if r.returncode != 0:
    sys.exit(1)

print()
print("=== 装机（看看这次是否真的装上）===")
before = ""
for l in (subprocess.run([ADB, "-s", DEV, "shell", "dumpsys", "package", PKG],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stdout or "").splitlines():
    if "lastUpdateTime" in l:
        before = l.strip()
print("   装前:", before)
apk = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
r2 = subprocess.run([ADB, "-s", DEV, "install", "-r", "--no-streaming", apk],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
out = (r2.stdout or "") + (r2.stderr or "")
print("   安装输出全文：")
for l in out.strip().splitlines()[-8:]:
    print("      " + l[:150])
time.sleep(2)
after = ""
for l in (subprocess.run([ADB, "-s", DEV, "shell", "dumpsys", "package", PKG],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stdout or "").splitlines():
    if "lastUpdateTime" in l:
        after = l.strip()
print("   装后:", after)
print("   判定：%s" % ("✓ 装上了" if after != before and after else "✗ 没装上（可能等手机确认）"))
