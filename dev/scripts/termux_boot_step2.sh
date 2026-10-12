#!/data/data/com.termux/files/usr/bin/bash
# step2：修 curl（镜像版本不同步导致链接失败）→ 手机自己下载 NapCat 官方安装脚本
LOG=/sdcard/Download/napcat_boot2.log
exec >"$LOG" 2>&1
echo "================ STEP2 START $(date) ================"
export DEBIAN_FRONTEND=noninteractive

try_curl() {
  echo "---- curl 自检 ----"
  curl --version 2>&1 | head -2
  return $?
}

echo "### 先做一次全量 upgrade，把依赖版本对齐（镜像不同步是 curl 链接失败的根因）"
apt-get upgrade -y
echo "upgrade 退出码=$?"
try_curl
C1=$?
echo "curl 自检退出码=$C1"

if [ $C1 -ne 0 ]; then
  echo "### 仍然坏 ⇒ 重装 curl 相关库"
  apt-get install --reinstall -y libcurl openssl ca-certificates curl
  echo "reinstall 退出码=$?"
  try_curl
  C1=$?
  echo "curl 自检退出码=$C1"
fi

if [ $C1 -ne 0 ]; then
  echo "### 还坏 ⇒ 换回 Termux 官方源，再对齐一次"
  M=https://packages.termux.dev/apt/termux-main
  [ -d "$PREFIX/etc/apt/sources.list.d" ] && echo "deb $M stable main" > "$PREFIX/etc/apt/sources.list.d/termux-main.list"
  [ -f "$PREFIX/etc/apt/sources.list" ] && echo "deb $M stable main" > "$PREFIX/etc/apt/sources.list"
  apt-get update -y
  apt-get upgrade -y
  apt-get install --reinstall -y curl libcurl openssl
  try_curl
  C1=$?
  echo "curl 自检退出码=$C1"
fi

echo "### 备用下载器 wget / python"
apt-get install -y wget 2>&1 | tail -2
wget --version 2>&1 | head -1

echo "### 开始下载 NapCat 官方 Termux 安装脚本（由手机自己拉取）"
cd "$HOME"
rm -f napcat.termux.sh
URL=https://nclatest.znin.net/NapNeko/NapCat-Installer/main/script/install.termux.sh
if [ $C1 -eq 0 ]; then
  curl -fL --retry 3 --connect-timeout 25 -o napcat.termux.sh "$URL"
  echo "curl 下载退出码=$?"
else
  echo "curl 不可用，改用 python 下载"
  python -c "import urllib.request;urllib.request.urlretrieve('$URL','napcat.termux.sh')" 2>&1
  echo "python 下载退出码=$?"
fi
ls -l "$HOME/napcat.termux.sh" 2>&1
echo "---- 文件类型/头部（确认真下到了）----"
head -c 200 "$HOME/napcat.termux.sh" 2>&1
echo
echo "---- 行数 ----"
wc -l "$HOME/napcat.termux.sh" 2>&1
echo "================ DONE-STEP2 ================"
