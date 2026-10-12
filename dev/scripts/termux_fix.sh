#!/data/data/com.termux/files/usr/bin/bash
# 修 apt/curl（清掉卡死 18 小时的交互询问），全部非交互
echo "================ FIX START $(date) ================"
export DEBIAN_FRONTEND=noninteractive
export PATH=/data/data/com.termux/files/usr/bin:$PATH
echo "uid=$(id -u) HOME=$HOME"
echo "--- 清掉卡死的 apt/dpkg ---"
pkill -f "apt-get" 2>/dev/null
pkill -f "dpkg" 2>/dev/null
sleep 2
echo "残余进程数=$(ps -ef 2>/dev/null | grep -E 'apt-get|dpkg' | grep -v grep | wc -l)"
echo "--- 用 -o Dpkg::Options 强制保留旧配置，避免任何询问 ---"
echo "--- dpkg --configure -a ---"
dpkg --configure -a -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold 2>&1 | tail -6
echo "--- apt-get update ---"
apt-get update -y 2>&1 | tail -4
echo "--- apt-get upgrade（非交互）---"
apt-get -y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold upgrade 2>&1 | tail -25
echo "--- curl 自检 ---"
if curl --version >/dev/null 2>&1; then
  echo "curl OK: $(curl --version | head -1)"
else
  echo "curl 坏 ⇒ 重装"
  apt-get install --reinstall -y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold curl libcurl openssl ca-certificates 2>&1 | tail -8
  curl --version 2>&1 | head -2
fi
echo "--- 装 wget 备用 ---"
apt-get install -y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold wget 2>&1 | tail -3
wget --version 2>&1 | head -1
echo "--- python ---"
python --version 2>&1
echo "================ FIX DONE ================"
