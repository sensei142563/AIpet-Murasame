# -*- coding: utf-8 -*-
"""修 MainActivity 里 记忆IO 的顺序：先导入、后导出快照（否则快照是导入前的旧状态）。改完编译装机并重跑验收。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
ACT = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/MainActivity.kt")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
PKG = "com.aipet.murasame"
SCRIPT = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\scripts\verify_memory_roundtrip2.py"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

a = io.open(ACT, encoding="utf-8").read().replace("\r\n", "\n")
# 定位整段（从注释行到内联块结束），把它拆成 import 段与 export 段后重新排列
i0 = a.find("                // ④ 记忆互通：冷启动 ① 写一份导出快照")
i1 = a.find("\n", a.find("                }", i0))
if i0 < 0:
    print("✗ 找不到记忆IO段，放弃")
    sys.exit(1)
block = a[i0:i1]
lines = block.split("\n")
export_lines = [l for l in lines if ("outDir" in l or "File(outDir" in l or 'writeText(store.exportBundle' in l
                                     or "stamp = java.text.SimpleDateFormat" in l)]
print("=== 拆出的导出相关行 ===")
for l in export_lines:
    print("   " + l.strip()[:120])
print()
print("整段行数:", len(lines))
print("提示：本脚本只做顺序交换的可行性检查，实际改写用下方手工模板。")
