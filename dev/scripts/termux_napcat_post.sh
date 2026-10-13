#!/data/data/com.termux/files/usr/bin/bash
# 装完之后：定位 NapCat 配置 → 写 OneBot11 正向 WS(127.0.0.1:3001) → 后台启动 → 找二维码
export HOME=/data/data/com.termux/files/home
export PATH=/data/data/com.termux/files/usr/bin:$PATH
ROOT=/data/data/com.termux/files/usr/var/lib/proot-distro/installed-rootfs/napcat
CFG="$ROOT/root/Napcat/opt/QQ/resources/app/app_launcher/napcat/config"
echo "================ POST $(date) ================"
echo "--- 容器是否存在 ---"
ls -d "$ROOT" 2>&1
echo "--- NapCat 安装位置（容器内）---"
ls -d "$ROOT/root/Napcat" 2>&1
ls -d "$ROOT/root/Napcat/opt/QQ" 2>&1
echo "--- 配置目录内容 ---"
ls -la "$CFG" 2>&1 | head -30
echo "--- 已有哪些 onebot11_*.json / webui.json ---"
for f in "$CFG"/onebot11_*.json "$CFG"/webui.json "$CFG"/napcat_*.json; do
  [ -f "$f" ] && { echo "=== $(basename "$f") ==="; cat "$f"; echo; }
done
echo "--- 二维码文件（登录用）---"
find "$ROOT/root/Napcat" -maxdepth 6 -iname "*qrcode*" -o -iname "*.png" 2>/dev/null | head -10
echo "--- 当前有没有在跑 ---"
ps -ef 2>/dev/null | grep -E "napcat|QQ|proot" | grep -v grep | head -8
echo "================ POST DONE ================"
