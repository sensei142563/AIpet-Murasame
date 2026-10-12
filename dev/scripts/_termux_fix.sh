#!/data/data/com.termux/files/usr/bin/bash
echo "================ FIX START $(date) ================"
export DEBIAN_FRONTEND=noninteractive
export PATH=/data/data/com.termux/files/usr/bin:$PATH
echo "whoami=$(id -u) HOME=$HOME"
echo "--- 清掉卡死 18 小时的 apt/dpkg ---"
pkill -f "apt-get" 2>/dev/null
pkill -f "dpkg" 2>/dev/null
sleep 2
echo "残余：$(ps -ef 2>/dev/null | grep -E 'apt-get|dpkg' | grep -v grep | wc -l) 个"
echo "--- 修复包数据库 ---"
dpkg --configure -a 2>&1 | tail -5
echo "--- 非交互升级（--force-confold 挡掉所有询问）---"
apt-get -y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold upgrade 2>&1 | tail -30
echo "--- curl 自检 ---"
if curl --version >/dev/null 2>&1; then
  echo "curl OK: $(curl --version | head -1)"
else
  echo "curl 坏 ⇒ 重装相关库"
  apt-get install --reinstall -y -o Dpkg::Options::=--force-confold libcurl openssl ca-certificates curl 2>&1 | tail -8
  curl --version 2>&1 | head -2
fi
echo "--- 装 wget（备用下载器）---"
apt-get install -y -o Dpkg::Options::=--force-confold wget 2>&1 | tail -3
wget --version 2>&1 | head -1
echo "--- python ---"
python --version 2>&1
echo "================ FIX DONE ================"
