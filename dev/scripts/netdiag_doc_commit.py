# -*- coding: utf-8 -*-
"""① 手机端"没扫到"时提示热点方案 ② 写操作说明文档 ③ 编译装机 ④ 提交。"""
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
DOC = os.path.join(MAIN, "dev", "docs", "热点链接-手机连电脑.md")
MAP = os.path.join(MAIN, "dev", "merge-map")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

# ① 提示更具体
s = io.open(SP, encoding="utf-8").read().replace("\r\n", "\n")
old = '''                netLine = base + "｜" + (host?.let { "找到电脑：$it（api.py 28565 有响应）" }
                    ?: "没扫到（确认电脑上 api.py 在跑、且和手机同一网络）")'''
new = '''                netLine = base + "｜" + (host?.let { "找到电脑：$it（api.py 28565 有响应）" }
                    ?: ("没扫到。两台要在同一个网络：最省事的是**手机开热点、电脑连这个热点**"
                        + "（校园/公司网常把客户端互相隔离，同网也可能连不上）；"
                        + "另外确认电脑上 api.py 在跑（端口 28565 监听 0.0.0.0）"))'''
if old in s:
    s = s.replace(old, new, 1)
    io.open(SP, "w", encoding="utf-8", newline="\n").write(s)
    print("✓ ① 手机端提示已补充热点方案")
else:
    print("⚠ ① 锚点未命中")

# ② 文档
io.open(DOC, "w", encoding="utf-8", newline="\n").write("""# 热点链接：手机怎么连上电脑（2026-10-11 实测）

## 为什么要看这一页
App 里有两处要填"电脑地址"：
- 设置 → 语音 → **语音服务地址**（电脑的 F5-TTS，端口 9881）
- 设置 → 语音 → **Jev 电脑地址**（电脑的 api.py，端口 28565）

填不对就连不上。**根本原因几乎总是"两台不在同一个网络"**，或者"虽然在同一个网络、
但这个网络把客户端互相隔离了"。

## 实测过的情况（2026-10-11，用户的机器）
| | 地址 | 说明 |
|---|---|---|
| 手机 | `10.88.97.91` | 连的是校园 Wi-Fi |
| 电脑 | `172.25.195.72/17`（网关 172.25.255.254） | 连的是另一个网络，且像校园/企业网 |
| 结论 | **不在同一网络** | 电脑 ping 手机 ＝ 不通（已实测） |

好消息：电脑上的 `api.py`(28565) 与 F5(9881) **都监听在 0.0.0.0**，不是只听 127.0.0.1
⇒ 只要网络通了，手机立刻就能连上，**不需要改电脑上的任何配置**。

## 推荐做法：手机开热点、电脑连手机
1. 手机：设置 → 移动网络 → **个人热点** → 打开（建议顺手设个密码）
2. 电脑：点右下角网络图标 → 连上这个热点
3. 手机 App：聊天页 → ☰ → ⚙ 设置 → 点 **「网络自检（找电脑）」**
   - 它会显示："本机 192.168.43.1（像是手机热点）"
   - 然后自动扫 `192.168.43.x`，**几秒内把电脑地址找出来**
   - 找到后照着填进上面那两处地址（端口分别用 9881 与 28565）
4. 电脑侧随时可以用这条命令自查：
   ```
   python tool/net_selfcheck.py <手机IP>
   ```
   它会告诉你：电脑有哪些可用地址、是不是连在手机热点上、**关键端口是不是监听在 0.0.0.0**
   （"只听 127.0.0.1"是第二个最常见的坑）

## 为什么不建议走校园 Wi-Fi
校园/企业 Wi-Fi 普遍开启**客户端隔离（AP isolation）**：即使手机和电脑连的是同一个
Wi-Fi、地址只差最后一位，两台之间也**互相 ping 不通**。这种情况不用折腾防火墙和路由器，
直接开热点最快。

## 手机自己就是热点时，地址长什么样
- 安卓默认：手机 `192.168.43.1`，电脑一般是 `192.168.43.x`
- 部分机型：`192.168.42.x` / `192.168.44.x`
- iPhone 热点：`172.20.10.x`

App 的网络自检已经把这几种都认作"热点网段"（纯逻辑部分有 10 个单测覆盖：
`NetDiagTest`，`hotspot 43/42/44/172.20.10 都认得出`、`普通 Wi-Fi 不误判` 等）。
""")
print("✓ ② 已写 dev/docs/热点链接-手机连电脑.md")

# ③ 编译装机
print()
print("=== ③ 编译 + 装机 ===")
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

# ④ 提交
MSG = """feat(net): 「热点链接」第一步 —— 手机端网络自检/找电脑 + 电脑端自检工具

用户原目标里最后一条「热点链接」，实测下来就是"手机怎么找到电脑"这件事。

一、新增纯逻辑 NetDiag（可 JVM 单测，**10/10 通过**）
  · 从本机 IPv4 列表判断：像不像"手机自己开热点"（192.168.43/42/44、172.20.10 四个网段）
  · 生成候选电脑地址（同网段 .1~.254，排除自己），并把网关与常见 DHCP 段排在前面
  · 过滤回环 / 169.254 链路本地；接口优先级 ap > swlan > wlan > eth > rndis
  · 覆盖用例：热点各网段识别、普通 Wi-Fi 不误判、只有移动数据、空列表、
    候选不含自己且覆盖 .2~.254、热点网段优先于其它网段、去重、优先级排序

二、新增 NetEnv（设备侧）：枚举本机 IPv4 + **并发短超时扫描候选地址**找出电脑
  （254 个地址，32 并发、每个 300ms，几秒出结果；连上端口即算，不依赖 HTTP）

三、设置页新增「网络自检（找电脑）」行
  点一下：显示本机地址 + 是否热点 + 给一句可执行提示；然后自动扫同网段找 api.py(28565)。
  找不到时的提示直接给出最省事的解法：**手机开热点、电脑连热点**
  （校园/公司网常开客户端隔离，同网也可能连不上）。

四、新增电脑侧 tool/net_selfcheck.py
  打印电脑可用 IPv4、判断是否连在手机热点上、**关键端口是否监听在 0.0.0.0**
  （"只听 127.0.0.1"是最常见的第二个坑），并可选测试能否连到手机。

五、真机实测（本轮）
  手机自己报：「本机 10.88.97.91；看起来是普通 Wi-Fi/路由器网络：电脑通常是 10.88.97.x」
  扫描结果：「没扫到」——**这是正确结论**：电脑在 172.25.195.72/17，两台不在同一网络，
  电脑 ping 手机实测不通。同时确认 api.py(28565) 与 F5(9881) 都监听 0.0.0.0，
  ⇒ 只要网络通了就能连，不需要改电脑配置。
  另：3001（NapCat）当前没有进程监听，与"电脑上 NapCat 没在跑"一致。

六、文档 dev/docs/热点链接-手机连电脑.md：热点四步操作 + 为什么校园 Wi-Fi 不行 +
  各机型热点网段对照 + 电脑侧自查命令。
"""
p = os.path.join(MAP, "_msg_net.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("手机仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:150])
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
rc2 = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                     encoding="utf-8", errors="replace")
print("桌面仓:", (rc2.stdout or rc2.stderr or "").splitlines()[0][:150])
for nm, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True, encoding="utf-8").stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True,
                        text=True, encoding="utf-8").stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (nm, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
