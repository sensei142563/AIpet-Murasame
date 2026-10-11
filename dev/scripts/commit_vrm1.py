# -*- coding: utf-8 -*-
"""提交 VRM 渲染通路验证（页面 + 脚本 + gitignore），确认测试模型未入库。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(MAIN, "dev", "merge-map")

MSG = """test(3d): 用 three + @pixiv/three-vrm 真机渲染 VRM，验证安卓 WebView 路线的关键假设

承接 dev/docs/2D转3D路线-2026-10.md 的路线 1：先证明"浏览器里能正确加载与渲染 VRM"，
再谈搬进手机 WebView。

做法与产物：
  · dev/three-demo/index.html：最小页面（three 0.186.1 + @pixiv/three-vrm 3.5.5，importmap 走 unpkg），
    加载 VRM、设置表情（优先 happy/joy）、加地面与网格，加载成功把 document.title 置为 VRM_OK；
  · dev/scripts/vrm_probe_1.py     下载示例 VRM（jsDelivr）+ 起本地 http + Edge 无头截图（软渲染太慢，弃用）
  · dev/scripts/net_probe_3d.py    网络探针：unpkg/jsDelivr/hf-mirror/github 可达，
                                   raw.githubusercontent **被网关挡**（502/timeout），故改走 jsDelivr
  · dev/scripts/vrm_probe_cdp.py   最终验证手段：headless Edge + --remote-debugging-port
                                   + --remote-allow-origins=* → 轮询 document.title → Page.captureScreenshot
                                   （这样取到的是 WebGL 画布本身，不依赖物理显示器——desktop_screenshot 曾因屏幕休眠全黑）
  · dev/scripts/vrm_probe_fix.py / vrm_probe_front.py  朝向与缓存破坏（Edge 会复用 profile 缓存，
                                   改完页面必须加 ?v=时间戳）

实测结果（证据 dev/shots/vrm_cdp_render.png）：
  · 页面标题 **VRM_OK**（模型加载成功）；
  · 截图 103KB，可见 3D 角色：MToon 卡通材质、头发 spring bone 自然下垂、地面网格；
  · 数据来源是公开的 three-vrm 官方示例模型（VRM1_Constraint_Twist_Sample.vrm，骨架测试用），
    **不入库**（.gitignore 排除 dev/three-demo/*.vrm 与 Edge 临时目录），符合"仓库里不出现别人项目的文件"。

遗留（不影响结论）：示例模型朝向判断在正/背面之间有歧义（长发改动遮挡），
  真正上线要用 VRoid Studio 自制的 VRM，届时朝向与外观自然正确。
"""
p = os.path.join(MAP, "_msg_vrm1.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
r = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
print("桌面仓:", (r.stdout or r.stderr or "").splitlines()[0][:130])
print()
print("=== 确认测试模型没被提交 ===")
ls = subprocess.run(["git", "-C", MAIN, "ls-files", "dev/three-demo"],
                    capture_output=True, text=True).stdout.strip()
print("   git 跟踪的 three-demo 文件:", ls or "(无)")
st = subprocess.run(["git", "-C", MAIN, "status", "--porcelain", "--ignored", "dev/three-demo"],
                    capture_output=True, text=True).stdout.strip()
for l in st.splitlines()[:8]:
    print("   " + l)
n = subprocess.run(["git", "-C", MAIN, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True).stdout.strip()
print("   未推送 %s 条" % n)
