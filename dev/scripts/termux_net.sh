#!/data/data/com.termux/files/usr/bin/bash
# 从手机侧测一圈下载源可达性 —— 决定 NapCat 与 Debian 容器走哪条路
export PATH=/data/data/com.termux/files/usr/bin:$PATH
echo "================ NET TEST $(date) ================"
t() {
  local name="$1" url="$2" tmo="${3:-8}"
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" -I -L --connect-timeout "$tmo" --max-time $((tmo*3)) "$url" 2>/dev/null)
  local rc=$?
  printf "%-46s HTTP=%-5s rc=%s\n" "$name" "${code:-none}" "$rc"
}
echo "--- NapCat 安装器来源 ---"
t "nclatest.znin.net(官方)"        "https://nclatest.znin.net/NapNeko/NapCat-Installer/main/script/install.termux.sh"
t "raw.githubusercontent"           "https://raw.githubusercontent.com/NapNeko/NapCat-Installer/main/script/install.sh"
t "jsDelivr(cdn.jsdelivr.net)"      "https://cdn.jsdelivr.net/gh/NapNeko/NapCat-Installer@main/script/install.sh"
t "ghproxy.net 代理"                "https://ghproxy.net/https://raw.githubusercontent.com/NapNeko/NapCat-Installer/main/script/install.sh"
t "ghfast.top 代理"                 "https://ghfast.top/https://raw.githubusercontent.com/NapNeko/NapCat-Installer/main/script/install.sh"
t "gh-proxy.com 代理"               "https://gh-proxy.com/https://raw.githubusercontent.com/NapNeko/NapCat-Installer/main/script/install.sh"
t "raw.gitmirror.com"               "https://raw.gitmirror.com/NapNeko/NapCat-Installer/main/script/install.sh"
echo "--- Docker / OCI 镜像仓库（proot-distro 5 拉 debian 用）---"
t "registry-1.docker.io(默认)"      "https://registry-1.docker.io/v2/"
t "docker.m.daocloud.io(道客)"      "https://docker.m.daocloud.io/v2/"
t "dockerproxy.net"                 "https://dockerproxy.net/v2/"
t "docker.1ms.run"                  "https://docker.1ms.run/v2/"
t "hub.rat.dev"                     "https://hub.rat.dev/v2/"
t "registry.cn-hangzhou.aliyuncs"   "https://registry.cn-hangzhou.aliyuncs.com/v2/"
echo "--- 其它（对照：这些应该通）---"
t "清华 termux 源"                  "https://mirrors.tuna.tsinghua.edu.cn/termux/apt/termux-main/"
t "baidu"                           "https://www.baidu.com"
echo "--- proot-distro 版本与可用帮助 ---"
proot-distro --help 2>&1 | head -20
echo "================ NET DONE ================"
