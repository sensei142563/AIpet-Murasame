#!/data/data/com.termux/files/usr/bin/bash
# 前置：清卡死 → 修依赖 → 装 screen/proot-distro/curl → 手机自己下 NapCat 官方安装脚本
export DEBIAN_FRONTEND=noninteractive
export PATH=/data/data/com.termux/files/usr/bin:$PATH
echo "================ PRE START $(date) ================"
echo "uid=$(id -u) HOME=$HOME"
echo "--- 清掉卡死的 apt/dpkg ---"
pkill -f apt-get 2>/dev/null
pkill -f dpkg 2>/dev/null
sleep 1
echo "残余=$(ps -ef 2>/dev/null | grep -E 'apt-get|dpkg' | grep -v grep | wc -l)"
echo "--- 修包数据库（非交互）---"
dpkg --configure -a -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold 2>&1 | tail -4
echo "--- apt update ---"
apt-get update -y 2>&1 | tail -3
echo "--- apt upgrade（对齐版本，curl 的链接错误靠这一步修）---"
apt-get -y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold upgrade 2>&1 | tail -20
echo "--- 装 screen / proot-distro / curl / wget ---"
apt-get install -y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold \
  screen proot-distro curl wget 2>&1 | tail -6
echo "--- 自检 ---"
for c in curl wget proot-distro screen python; do
  printf "%-14s " "$c"
  command -v $c >/dev/null 2>&1 && ($c --version 2>&1 | head -1) || echo "缺失"
done
echo "--- 手机自己下载 NapCat 官方 Termux 安装脚本 ---"
cd "$HOME"
rm -f napcat.termux.sh
curl -fL --retry 3 --connect-timeout 25 -o napcat.termux.sh \
  https://nclatest.znin.net/NapNeko/NapCat-Installer/main/script/install.termux.sh
echo "curl 退出码=$?"
ls -l "$HOME/napcat.termux.sh" 2>&1
echo "--- 头部 5 行 ---"
head -5 "$HOME/napcat.termux.sh" 2>&1
echo "--- 行数 ---"
wc -l "$HOME/napcat.termux.sh" 2>&1
echo "================ PRE DONE ================"
