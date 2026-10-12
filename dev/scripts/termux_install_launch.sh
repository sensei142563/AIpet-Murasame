#!/data/data/com.termux/files/usr/bin/bash
# 正式安装 NapCat（我自己在 Termux 里跑）
#  · 用国内镜像拉 Debian 容器（docker.io 直连不通）
#  · 用 ghproxy.net 代理下载 GitHub 上的 NapCat 安装器
#  · 先拿 wake-lock，避免长安装被系统休眠杀掉
export PATH=/data/data/com.termux/files/usr/bin:$PATH
export DEBIAN_FRONTEND=noninteractive
cd "$HOME" || exit 1

echo "================ INSTALL LAUNCH $(date) ================"
termux-wake-lock 2>/dev/null && echo "wake-lock 已获取" || echo "wake-lock 不可用（继续）"
echo "安装器存在: $(ls -l "$HOME/napcat.termux.sh" 2>&1)"
echo "代理文件: $(cat "$HOME/proxy_used.txt" 2>/dev/null)"

PROXY="$(cat "$HOME/proxy_used.txt" 2>/dev/null)"
[ -z "$PROXY" ] && PROXY="https://ghproxy.net"
IMAGE="docker.m.daocloud.io/library/debian:bookworm-slim"
echo "PROXY=$PROXY"
echo "IMAGE=$IMAGE"

rm -f "$HOME/napcat_install.log"
setsid nohup bash "$HOME/napcat.termux.sh" --image "$IMAGE" --github-proxy "$PROXY" \
  > "$HOME/napcat_install.log" 2>&1 < /dev/null &
echo "已后台启动，PID=$!"
sleep 5
echo "--- 5 秒后日志头 ---"
head -20 "$HOME/napcat_install.log" 2>&1
echo "================ LAUNCH DONE ================"
