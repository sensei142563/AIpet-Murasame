#!/data/data/com.termux/files/usr/bin/bash
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
