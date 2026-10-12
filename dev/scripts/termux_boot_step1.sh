#!/data/data/com.termux/files/usr/bin/bash
# 在手机 Termux 里跑：换国内镜像 → 装 curl/proot-distro → **由手机自己下载** NapCat 官方安装脚本
# 一切输出写进 /sdcard/Download/napcat_boot.log，便于 adb 侧读取（Termux 界面读不到）
LOG=/sdcard/Download/napcat_boot.log
mkdir -p /sdcard/Download 2>/dev/null
exec >"$LOG" 2>&1
echo "================ BOOT START $(date) ================"
echo "PREFIX=$PREFIX"
echo "HOME=$HOME"
echo "uname: $(uname -a)"

# ① 换清华镜像（国内直连 termux 官方源常超时）
MIRROR=https://mirrors.tuna.tsinghua.edu.cn/termux/apt/termux-main
if [ -d "$PREFIX/etc/apt/sources.list.d" ]; then
  echo "deb $MIRROR stable main" > "$PREFIX/etc/apt/sources.list.d/termux-main.list"
  echo "[mirror] 写入 sources.list.d/termux-main.list"
fi
if [ -f "$PREFIX/etc/apt/sources.list" ]; then
  echo "deb $MIRROR stable main" > "$PREFIX/etc/apt/sources.list"
  echo "[mirror] 覆盖 sources.list"
fi

export DEBIAN_FRONTEND=noninteractive
echo "---- apt-get update ----"
apt-get update -y
echo "update 退出码=$?"
echo "---- 装 curl / proot-distro ----"
apt-get install -y curl proot-distro
echo "install 退出码=$?"
echo "---- 版本自检 ----"
curl --version 2>&1 | head -2
proot-distro --version 2>&1 | head -2
echo "---- 手机自己下载 NapCat 官方 Termux 安装脚本 ----"
cd "$HOME"
rm -f napcat.termux.sh
curl -fL --retry 3 --connect-timeout 20 -o napcat.termux.sh \
  https://nclatest.znin.net/NapNeko/NapCat-Installer/main/script/install.termux.sh
echo "curl 退出码=$?"
ls -l "$HOME/napcat.termux.sh" 2>&1
echo "---- 脚本头部（确认下到的是真东西）----"
head -30 "$HOME/napcat.termux.sh" 2>&1
echo "================ DONE-STEP1 ================"
