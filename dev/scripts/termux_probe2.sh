#!/data/data/com.termux/files/usr/bin/bash
export PATH=/data/data/com.termux/files/usr/bin:$PATH
echo "================ PROBE2 $(date) ================"
echo "--- proot-distro install 的可用参数（怎么指定镜像仓库）---"
proot-distro install --help 2>&1 | head -45
echo
echo "--- proot-distro 顶层配置相关 ---"
proot-distro help 2>&1 | tail -25
echo
echo "--- Debian 源可达性（容器内要用）---"
t() { printf "%-42s " "$1"; curl -s -o /dev/null -w "HTTP=%{http_code}\n" -I -L --connect-timeout 8 --max-time 20 "$2" 2>/dev/null || echo "fail"; }
t "deb.debian.org"            "https://deb.debian.org/debian/dists/bookworm/Release"
t "清华 debian 源"            "https://mirrors.tuna.tsinghua.edu.cn/debian/dists/bookworm/Release"
t "阿里 debian 源"            "https://mirrors.aliyun.com/debian/dists/bookworm/Release"
t "中科大 debian 源"          "https://mirrors.ustc.edu.cn/debian/dists/bookworm/Release"
echo
echo "--- 用代理真正下载 NapCat 安装器（两个代理各试一次）---"
cd "$HOME"; rm -f napcat.termux.sh
for P in "https://ghproxy.net" "https://ghfast.top" "https://gh-proxy.com"; do
  echo "== 试 $P"
  if curl -fL --connect-timeout 10 --max-time 90 -o napcat.termux.sh \
      "$P/https://raw.githubusercontent.com/NapNeko/NapCat-Installer/main/script/install.termux.sh"; then
    echo "   下载成功，大小=$(wc -c < napcat.termux.sh) 字节"
    head -3 napcat.termux.sh
    echo "$P" > proxy_used.txt
    break
  else
    echo "   失败 rc=$?"
  fi
done
ls -l "$HOME/napcat.termux.sh" 2>&1
echo
echo "--- 顺便把容器内的 install.sh 也缓存一份（安装时要它）---"
if [ -s napcat.termux.sh ]; then
  P=$(cat proxy_used.txt 2>/dev/null)
  curl -fL --connect-timeout 10 --max-time 120 -o install.sh \
    "$P/https://raw.githubusercontent.com/NapNeko/NapCat-Installer/main/script/install.sh" \
    && echo "install.sh 大小=$(wc -c < install.sh)" || echo "install.sh 下载失败"
fi
echo "================ PROBE2 DONE ================"
