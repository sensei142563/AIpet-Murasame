# -*- coding: utf-8 -*-
"""设置页加「网络自检（找电脑）」行：显示本机地址/是否热点 + 一键扫同网段找电脑。编译装机。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
SP = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/SettingsPage.kt")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

s = io.open(SP, encoding="utf-8").read().replace("\r\n", "\n")
if "网络自检" in s:
    print("· 已有网络自检行")
else:
    anchor = 'Row2("测试电脑语音", "点一下用电脑 F5 念一句（丛雨音色）",'
    add = '''// [netdiag] 网络自检 / 找电脑（对应"热点链接"那条需求）
// 手机开热点、电脑连手机时，电脑通常是 192.168.43.x，但具体是多少没人记得住。
// 这里先把本机地址与网络类型说清楚，再一键扫同网段把电脑找出来。
var netLine by remember { mutableStateOf("") }
var netBusy by remember { mutableStateOf(false) }
Row2(
    "网络自检（找电脑）",
    if (netBusy) "正在扫同网段找电脑…"
    else if (netLine.isNotEmpty()) netLine
    else "点一下：看本机地址 / 判断是不是热点 / 扫出电脑地址",
    Icons.Default.Settings, text, sub
) {
    if (!netBusy) {
        netBusy = true
        netLine = ""
        scope.launch {
            val rep = withContext(Dispatchers.IO) { com.aipet.murasame.ui.NetEnv.report() }
            val base = "本机 " + (rep.selfIps.joinToString("/").ifEmpty { "无 IPv4" }) +
                (if (rep.hotspotLikely) "（像是手机热点）" else "") + "；" + rep.hint
            if (rep.candidates.isEmpty()) {
                netLine = base
            } else {
                netLine = base + "｜正在扫…"
                val host = com.aipet.murasame.ui.NetEnv.findHost(
                    com.aipet.murasame.ui.NetDiag.prioritize(rep.candidates, rep.subnet), 28565)
                netLine = base + "｜" + (host?.let { "找到电脑：$it（api.py 28565 有响应）" }
                    ?: "没扫到（确认电脑上 api.py 在跑、且和手机同一网络）")
            }
            netBusy = false
        }
    }
}
'''
    if anchor in s:
        s = s.replace(anchor, add + anchor, 1)
        # 需要 scope / Dispatchers / launch
        for imp in ("import androidx.compose.runtime.rememberCoroutineScope",
                    "import kotlinx.coroutines.Dispatchers",
                    "import kotlinx.coroutines.launch",
                    "import kotlinx.coroutines.withContext"):
            if imp not in s:
                s = s.replace("import androidx.compose.runtime.Composable", imp + "\nimport androidx.compose.runtime.Composable", 1)
        # scope 变量：若不存在则加
        if "val scope = rememberCoroutineScope()" not in s:
            s = s.replace("    val bg = MaterialTheme.colorScheme.background",
                          "    val scope = rememberCoroutineScope()\n    val bg = MaterialTheme.colorScheme.background", 1)
        io.open(SP, "w", encoding="utf-8", newline="\n").write(s)
        print("✓ 已加「网络自检（找电脑）」行 + scope/imports")
    else:
        print("✗ 锚点未命中")

print()
print("=== 编译 + 装机 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
for l in ((r.stdout or "") + (r.stderr or "")).splitlines():
    if l.strip().startswith("BUILD") or l.startswith("e: "):
        print("   " + l.strip()[:190])
if r.returncode != 0:
    sys.exit(1)
apk = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
r2 = subprocess.run([ADB, "-s", DEV, "install", "-r", "--no-streaming", apk],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
o2 = (r2.stdout or "") + (r2.stderr or "")
print("   装机:", [l for l in o2.splitlines() if "Success" in l or "Failure" in l][:1] or "?")
