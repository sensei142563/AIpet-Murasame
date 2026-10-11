# -*- coding: utf-8 -*-
"""方案 A 预备：写《手机自足（Termux 版 NapCat）》准备文档 + 可粘贴脚本 + 提交。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
CHAT = r"E:\university\order\python\pet\chatter"
MAP = os.path.join(MAIN, "dev", "merge-map")

SH = """#!/data/data/com.termux/files/usr/bin/bash
# 手机自足（方案 A）：在 Termux 里装官方 NapCat + LinuxQQ，把 OneBot11 正向 WS 挂在 127.0.0.1:3001
# 用法：在 Termux（推荐 ZeroTermux）里逐段粘贴；本脚本只是把步骤固化，出错时请对照官方文档。
set -e

echo "=== 0) 基础环境 ==="
pkg update -y && pkg install -y proot-distro screen curl x11-repo || true

echo "=== 1) 官方一键安装脚本（Debian + rootless NapCat + LinuxQQ arm64）==="
# 官方仓库：https://github.com/NapNeko/NapCat-Installer
curl -o napcat.termux.sh https://nclatest.znin.net/NapNeko/NapCat-Installer/main/script/install.termux.sh
bash napcat.termux.sh

echo "=== 2) 启动（无头 LinuxQQ + NapCat；NapCat 会注入 QQ 的 app_launcher）==="
# 之后每次启动都跑这一行；用 screen 让它常驻，避免切后台被杀
screen -dmS napcat bash -c 'proot-distro login napcat -- bash -c "xvfb-run -a /root/Napcat/opt/QQ/qq --no-sandbox"'
echo "已尝试后台启动。查看：screen -r napcat（Ctrl+A D 退出查看）"

echo "=== 3) 接下来在手机浏览器里做 ==="
cat <<'EOT'
  1. 打开 http://localhost:6099  （NapCat WebUI；token 见容器内
     /root/Napcat/opt/QQ/resources/app/app_launcher/napcat/config/webui.json）
  2. 用**小号**扫码登录。若小号就在本机、无法"同屏扫码"：
     把二维码截图 → 打开小号的 QQ → 扫一扫 → 右上角相册 → 选那张截图（QQ 支持从相册取码）
  3. 网络配置里**新建 WebSocket 服务器**：host=127.0.0.1  port=3001  类型=正向WS  OneBot11
     对应配置文件：.../napcat/config/onebot11_<QQ号>.json 的 network.websocketServers
     （桌面端 qq_bridge.py 的报错提示也指向这一段，格式一致）
  4. 保活：设置→应用管理→Termux/ZeroTermux：允许后台活动、关闭电池优化；
     开发者选项里把该应用加入"不锁屏/常驻"；保持一条常驻通知不清掉
EOT

echo "=== 4) 自检 ==="
echo "容器里看 NapCat 是否在跑： proot-distro login napcat -- bash -c 'ps -ef | grep -i napcat | head'"
echo "端口是否在听（容器内）：  proot-distro login napcat -- bash -c 'netstat -lntp | grep 3001'"
echo "App 侧日志（真机）：      /sdcard/Android/data/com.aipet.murasame/files/onebot_local.log"
"""

OK = """# 手机自足（方案 A）：在手机里跑 NapCat，App 直连本机 OneBot11

> 用户 2026-10-11 选定方案 A。目标：**不开电脑**，手机自己收发 QQ（仅小号）。
> 结论依据见调研：NapCat 是"官方 QQ 客户端 + 注入层"，官方安装器**自带 Termux 脚本**
> （Debian + rootless NapCat + LinuxQQ arm64），协议维护交给 NapCat，我们只当 OneBot11 客户端。
> **自研协议不划算**（go-cqhttp 官方声明无力维护、mirai 停更、MiraiAndroid/Seiko 已归档）。

## 一、App 侧已经准备好的（本轮代码）

| 项 | 状态 |
|---|---|
| 本机 OneBot11 客户端 | ✅ 新增 `bot/chat/OneBotLocal.kt`，用 OkHttp WebSocket（**不加新依赖**），默认连 `ws://127.0.0.1:3001` |
| 冷启动自动尝试连接 | ✅ `MainActivity` 启动时 `OneBotLocal.start(app)`（连不上静默失败，不影响其它功能）|
| 数据源 | ✅ `QqBackend`：**本机 OneBot11 优先，电脑 api.py 兜底**；两者产出**同一套 JSON 形状**，界面无需区分 |
| 界面 | ✅ 首页「QQ chatter」卡 / QQ 面板显示「**数据源**」行；本机连上时显示"本机 NapCat(OneBot11 …)" |
| 发送 | ✅ 本机直连时**直接发**（`send_msg`）；走电脑时投递旧队列 |
| 日志 | ✅ `files/onebot_local.log`（含外置目录同名文件，adb 可 pull）——**这是最主要的验收通道** |
| 会话落盘 | ✅ 本机会话缓存到 `files/onebot_local.json`（重启不丢，每会话最多 200 条 / 最多 40 会话）|

## 二、手机侧要做的（照着走）

一键脚本：`dev/scripts/termux_napcat_setup.sh`（把步骤固化成可粘贴的片段）。

1. **装 ZeroTermux**（或 F-Droid 版 Termux；应用商店版本过旧）。
2. 跑官方安装脚本：
   ```bash
   curl -o napcat.termux.sh https://nclatest.znin.net/NapNeko/NapCat-Installer/main/script/install.termux.sh
   bash napcat.termux.sh
   ```
   （来源：<https://github.com/NapNeko/NapCat-Installer> 的 `script/install.termux.sh`）
3. 启动（每次都要）：
   ```bash
   screen -dmS napcat bash -c 'proot-distro login napcat -- bash -c "xvfb-run -a /root/Napcat/opt/QQ/qq --no-sandbox"'
   ```
4. 手机浏览器开 **`http://localhost:6099`**（NapCat WebUI，token 在容器内
   `…/napcat/config/webui.json`）→ 用**小号**登录。
   *若小号就在本机、没法同屏扫码*：**把二维码截图 → 小号 QQ 扫一扫 → 右上角相册 → 选截图**。
5. **网络配置 → 新建 WebSocket 服务器**：`host=127.0.0.1`、`port=3001`、类型=**正向 WS**、协议 OneBot11。
   对应文件 `…/napcat/config/onebot11_<QQ号>.json` 的 `network.websocketServers` —— 与桌面端
   `qq/qq_bridge.py` 里的报错提示指向同一段配置，格式一致。
6. **保活**（这是本方案唯一硬骨头，不是协议问题）：
   - 允许后台活动、关闭电池优化、把 Termux/ZeroTermux 加入"不锁屏/常驻"白名单；
   - 保持一条常驻通知别清掉；必要时用浮窗/前台运行；
   - 第三方教程的经验值：**≥2GB 运行内存、≥3GB 可用存储**（非官方，未实测）。

## 三、验收（手机侧做完后，我这边这样验）

1. `adb shell cat /sdcard/Android/data/com.aipet.murasame/files/onebot_local.log`
   应出现：`正在连接 ws://127.0.0.1:3001` → `已连上本机 NapCat` → `登录信息：<昵称>(<QQ号>)`。
2. App 首页「QQ chatter」卡：状态行应显示 **NapCat：在线 ✓**，数据源显示 **本机 NapCat(OneBot11 …)**。
3. 用小号给这个号发一条 → 卡片会话列表里出现该会话与消息。
4. 在卡片里回一条 → 小号应收到（本机直连是**立即发**，不经队列）。

## 四、风险与合规（有出处的事实）

- **不要**在同一账号上"多端 + 模块化环境"：NapCat 官方安全文档建议避免同一 IP/设备同时登录
  bot 账号与常用账号；社区（LLOneBot 维护者）明确 "bot 账号最好不要在手机登录"、
  "手机上有模块之类的也会被检测到导致全端下线"。
- 因此：**只用小号**，且**这个手机不要日常登录该小号**（本机登录是给 NapCat 用的）。
- 掉线可尝试把 `o3Hook` 设为 0（NapCat 官方安全文档提供的缓解手段）。
- 反直觉但有利的一点：手机同时是 NapCat 与扫码端 ⇒ **天然同 IP**，少一类风控。

## 五、未验证（如实标注）

1. NapCat Termux 脚本在 **Android 14/15/16** 上的兼容性与保活表现：未实测。
2. proot 内 LinuxQQ arm64 的**实际常驻内存/耗电**：只有第三方博客口径（≥2GB RAM），无实测。
3. **同一台手机**上"截图二维码→相册扫码"是否顺畅：未实测（理论可行，QQ 支持相册取码）。
4. 30 小时以上长时间挂机的稳定性（Doze 是否最终杀掉）：未实测。
5. 本机 OneBot11 客户端与 NapCat 的**全部**消息类型（图片/语音/表情）解析：当前只解析
   文本 + [图片]/[表情]/[语音] 占位，**未在真机验证**。
6. 具体 NapCat 版本（调研时最新 v4.18.37 / 2026-10-10）的配置字段是否有变动：未逐项核对。
"""

io.open(os.path.join(MAIN, "dev", "docs", "QQ手机自足-Termux版NapCat-准备.md"), "w",
        encoding="utf-8", newline="\n").write(OK)
io.open(os.path.join(MAIN, "dev", "scripts", "termux_napcat_setup.sh"), "w",
        encoding="utf-8", newline="\n").write(SH)
print("✓ 写了 dev/docs/QQ手机自足-Termux版NapCat-准备.md")
print("✓ 写了 dev/scripts/termux_napcat_setup.sh")

MSG = """feat(qq): 方案 A 代码侧——App 直连本机 OneBot11（NapCat 跑在手机里）

用户选定方案 A（手机 Termux + 官方 NapCat），本次完成 App 侧全部准备：

· 新增 bot/chat/OneBotLocal.kt：本机 OneBot11 客户端（OkHttp WebSocket，**不新增依赖**），
  默认 ws://127.0.0.1:3001；解析 post_type=message/message_sent（私聊/群聊、字符串与数组两种
  message 形态），维护每会话最近 200 条 / 最多 40 个会话，落盘 files/onebot_local.json；
  日志写 files/onebot_local.log（含外置目录同名文件，便于 adb 验收）。
· 新增 QqBackend 门面：**本机 OneBot11 优先，电脑 api.py 兜底**；两者产出与 api.py
  **完全相同的 JSON 形状**（status/sessions/messages/outbox），所以界面几乎不用改。
· QqScreen / HomeScreen 改用 QqBackend；状态卡新增「数据源」一行（本机连上时显示
  "本机 NapCat(OneBot11 ws://127.0.0.1:3001)"）。
· MainActivity 冷启动 OneBotLocal.start(app)：自动尝试直连本机，连不上静默失败。
· 发送：本机直连时**立即发**（send_msg），走电脑时仍是旧的投递队列。

预备（桌面仓）：
· dev/docs/QQ手机自足-Termux版NapCat-准备.md：手机侧照着做的完整步骤（官方 Termux 安装脚本、
  screen 常驻启动、WebUI 6099 扫码、onebot11_<QQ>.json 里加正向 WS 127.0.0.1:3001、保活要点）、
  验收通道（onebot_local.log / 首页卡片）、风险合规（只用小号、别在这台手机日常登录该小号、
  o3Hook=0）、以及 6 条未验证项。
· dev/scripts/termux_napcat_setup.sh：把上述步骤固化成可粘贴片段。
"""
p = os.path.join(MAP, "_msg_onebot1.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r1 = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("手机仓:", (r1.stdout or r1.stderr or "").splitlines()[0][:130])
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
r2 = subprocess.run(["git", "-C", MAIN, "commit", "-m",
                     "docs(qq): 方案 A 预备——手机 Termux 版 NapCat 完整步骤与验收通道（含风险与未验证项）"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
print("桌面仓:", (r2.stdout or r2.stderr or "").splitlines()[0][:130])
for name, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True).stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"],
                        capture_output=True, text=True).stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (name, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
