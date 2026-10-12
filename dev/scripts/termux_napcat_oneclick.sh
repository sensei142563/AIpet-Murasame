#!/data/data/com.termux/files/usr/bin/bash
# ============================================================================
# NapCat 一次性安装（在 Termux 里跑；已把 2026-10-12 踩过的坑全部固化）
#
# 踩过的坑（本脚本已规避）：
#   1) 经 adb run-as 执行时，$HOME 是 /data/user/0/com.termux（应用数据根），
#      不是 Termux 真正的 home ⇒ **必须显式指定 HOME**，否则文件下到别处、找不到。
#   2) 清华镜像与基础包版本不同步 ⇒ curl 报
#      "CANNOT LINK EXECUTABLE curl: cannot locate symbol SSL_set_quic_tls_..."，
#      修法：dpkg --force-confdef --force-confold --configure -a，再 apt upgrade 对齐。
#   3) 官方下载域名 nclatest.znin.net 在国内容易超时；raw.githubusercontent.com 直连不通
#      ⇒ 用 https://ghproxy.net 代理（实测可用）。
#   4) proot-distro 5 默认从 registry-1.docker.io 拉镜像，国内不通
#      ⇒ 用 docker.m.daocloud.io 国内镜像。
#   5) 长安装会被系统休眠杀掉 ⇒ 先 termux-wake-lock，并用 setsid nohup 放后台。
# ============================================================================
export HOME=/data/data/com.termux/files/home
export PATH=/data/data/com.termux/files/usr/bin:$PATH
export DEBIAN_FRONTEND=noninteractive
cd "$HOME" || exit 1

PROXY="https://ghproxy.net"
IMAGE="docker.m.daocloud.io/library/debian:bookworm-slim"
RAW="https://raw.githubusercontent.com/NapNeko/NapCat-Installer/main/script"

echo "================ ONECLICK $(date) ================"
echo "HOME=$HOME  uid=$(id -u)"

command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock && echo "wake-lock ✓"

echo "--- 修包数据库（用 dpkg 自己的强制选项，不是 apt 的 -o）---"
yes "" 2>/dev/null | dpkg --force-confdef --force-confold --configure -a 2>&1 | tail -3

echo "--- apt update + upgrade（对齐版本，修 curl）---"
apt-get update -y </dev/null 2>&1 | tail -2
apt-get -y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold upgrade </dev/null 2>&1 | tail -8

echo "--- 确保 screen / proot-distro / curl / wget / openssl ---"
apt-get install -y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold \
  screen proot-distro curl wget openssl ca-certificates </dev/null 2>&1 | tail -4

echo "--- 自检 ---"
for c in curl wget proot-distro screen; do
  printf "%-14s " "$c"; command -v $c >/dev/null 2>&1 && ($c --version 2>&1 | head -1) || echo 缺失
done

echo "--- 经代理下载 NapCat 官方安装器（由手机自己拉）---"
rm -f napcat.termux.sh
curl -fL --connect-timeout 15 --max-time 120 -o napcat.termux.sh "$PROXY/$RAW/install.termux.sh" \
  || { echo "下载失败，换 ghfast.top 再试"; \
       curl -fL --connect-timeout 15 --max-time 120 -o napcat.termux.sh \
         "https://ghfast.top/$RAW/install.termux.sh"; }
ls -l napcat.termux.sh 2>&1
head -3 napcat.termux.sh 2>&1

echo "--- 后台开装（日志 $HOME/napcat_install.log）---"
rm -f napcat_install.log
setsid nohup bash "$HOME/napcat.termux.sh" --image "$IMAGE" --github-proxy "$PROXY" \
  > "$HOME/napcat_install.log" 2>&1 < /dev/null &
echo "PID=$!"
sleep 8
echo "--- 8 秒后日志 ---"
head -25 "$HOME/napcat_install.log" 2>&1
echo "================ ONECLICK LAUNCHED ================"
