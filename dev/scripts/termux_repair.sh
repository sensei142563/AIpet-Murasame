#!/data/data/com.termux/files/usr/bin/bash
# 修 Termux：① 真正修好包数据库 ② 对齐版本修好 curl ③ 装 screen/proot-distro
# 关键：dpkg 用自己的 --force-confold（不能用 apt 的 -o Dpkg::Options）；全程 </dev/null 防卡
export DEBIAN_FRONTEND=noninteractive
export PATH=/data/data/com.termux/files/usr/bin:$PATH
echo "================ REPAIR START $(date) ================"
pkill -f apt-get 2>/dev/null; pkill -f dpkg 2>/dev/null; sleep 1
echo "残余=$(ps -ef 2>/dev/null | grep -E 'apt-get|dpkg' | grep -v grep | wc -l)"

echo "--- ① dpkg --configure -a（dpkg 自己的强制选项）---"
yes "" 2>/dev/null | dpkg --force-confdef --force-confold --configure -a 2>&1 | tail -8
echo "configure 退出码=$?"

echo "--- ② 修复未完成的依赖 ---"
apt-get -y -f install -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold </dev/null 2>&1 | tail -6

echo "--- ③ apt update ---"
apt-get update -y </dev/null 2>&1 | tail -3

echo "--- ④ apt upgrade（对齐版本）---"
apt-get -y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold upgrade </dev/null 2>&1 | tail -18
echo "upgrade 退出码=$?"

echo "--- ⑤ curl 自检 ---"
if curl --version >/dev/null 2>&1; then
  echo "curl OK: $(curl --version | head -1)"
else
  echo "curl 仍坏 ⇒ 重装 curl/libcurl/openssl/ca-certificates"
  apt-get install --reinstall -y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold \
    libcurl openssl ca-certificates curl </dev/null 2>&1 | tail -8
  curl --version 2>&1 | head -2
fi

echo "--- ⑥ 装 screen / proot-distro / wget ---"
apt-get install -y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold \
  screen proot-distro wget </dev/null 2>&1 | tail -6

echo "--- ⑦ 自检 ---"
for c in curl wget proot-distro screen python; do
  printf "%-14s " "$c"
  if command -v $c >/dev/null 2>&1; then $c --version 2>&1 | head -1; else echo "缺失"; fi
done

echo "--- ⑧ 手机自己下载 NapCat 官方 Termux 安装脚本 ---"
cd "$HOME"; rm -f napcat.termux.sh
URL=https://nclatest.znin.net/NapNeko/NapCat-Installer/main/script/install.termux.sh
if curl --version >/dev/null 2>&1; then
  curl -fL --retry 3 --connect-timeout 25 -o napcat.termux.sh "$URL" && echo "curl 下载成功"
else
  echo "用 python 下载"
  python -c "import urllib.request;urllib.request.urlretrieve('$URL','napcat.termux.sh')" && echo "python 下载成功"
fi
ls -l "$HOME/napcat.termux.sh" 2>&1
head -3 "$HOME/napcat.termux.sh" 2>&1
echo "================ REPAIR DONE ================"
