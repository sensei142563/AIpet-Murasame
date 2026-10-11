# -*- coding: utf-8 -*-
"""提交离线 JS 包 + 许可说明，并确认仓库状态。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
DEMO = os.path.join(MAIN, "dev", "three-demo")
MAP = os.path.join(MAIN, "dev", "merge-map")

io.open(os.path.join(DEMO, "vendor", "README.md"), "w", encoding="utf-8", newline="\n").write(
    """# 离线渲染依赖（three / three-vrm）

这些文件是**第三方开源库**，为了让页面在**不联外网**的环境（手机 assets）里也能跑，
按原样本地化保存。两者都是 **MIT** 许可，允许再分发，保留版权与许可声明即可。

| 文件 | 来源 | 版本 | 许可 |
|---|---|---|---|
| `three.js` | <https://www.npmjs.com/package/three> | 0.186.1 | MIT |
| `GLTFLoader.js` | three 官方 examples/jsm/loaders | 0.186.1 | MIT |
| `three-vrm.js` | <https://www.npmjs.com/package/@pixiv/three-vrm> | 3.5.5 | MIT |

获取方式：jsDelivr 的 `+esm` 预打包端点（Rollup + esbuild 打包、含依赖），例如
`https://cdn.jsdelivr.net/npm/three@0.186.1/+esm`。

## ⚠ 本地化时必须做的一步（否则离线 404）

`+esm` 打包会把依赖**外部化成绝对路径**，例如 `three-vrm.js` 里出现
`"/npm/three@0.185.1/+esm"`、`GLTFLoader.js` 里出现 `"/npm/three@0.186.1/+esm"`。
importmap **拦不住**这种路径式导入，必须改写成相对本地文件：

```
"/npm/three@0.186.1/+esm"   →  "./three.js"
"/npm/three@0.185.1/+esm"   →  "./three.js"
```

`dev/scripts/vrm_offline_fix.py` 就是做这件事的（并复核残留）。
""")
print("✓ 写了 vendor/README.md（许可 + 本地化注意事项）")

MSG = """test(3d): three/three-vrm 离线化（0.95MB 本地包）并验证「不联外网也能渲染」

上一提交证明了 CDN 版本能渲染，但手机 WebView 不能依赖 CDN，且校园网对部分域名有拦截。
本次把依赖本地化并用同一套 CDP 手段验证离线可用。

做法：
  · 用 jsDelivr 的 `+esm` 端点取三个文件（Rollup+esbuild 预打包、自带依赖）：
    three.js 729.5KB / three-vrm.js 148.4KB / GLTFLoader.js 45.8KB，合计 0.95MB；
  · index.html 的 importmap 指向本地文件；页面加自诊断（异常写进 document.title）；
  · 抓错过程（dev/scripts/vrm_cdp_console.py，CDP 打开 Runtime/Log 域）发现真凶：
      HTTP 404 http://127.0.0.1:8099/npm/three@0.186.1/+esm
      HTTP 404 http://127.0.0.1:8099/npm/three@0.185.1/+esm
    ⇒ `+esm` 会把依赖**外部化成绝对路径**，importmap 拦不住路径式导入；离线必然 404。
  · vrm_offline_fix.py 把这些绝对路径改写成相对本地文件（three-vrm.js 引用的是 0.185.1，
    GLTFLoader.js 引用 0.186.1，都指向本地 three.js），复核残留为 0。

结果：页面标题 **VRM_OK 在 0 秒**返回（本地文件加载远快于 CDN），
      CDP 截图 85.5KB，3D 角色（MToon 材质 + spring bone 头发）正常渲染。

附带：dev/three-demo/vendor/README.md 记录来源/版本/许可（three 与 three-vrm 均为 MIT）
      以及"本地化必须改写绝对路径"这条坑。测试用 VRM 仍不入库（.gitignore）。
"""
p = os.path.join(MAP, "_msg_vrm2.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
r = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
print("桌面仓:", (r.stdout or r.stderr or "").splitlines()[0][:130])
n = subprocess.run(["git", "-C", MAIN, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True).stdout.strip()
st = subprocess.run(["git", "-C", MAIN, "status", "--porcelain"],
                    capture_output=True, text=True).stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
print("  three-demo 已跟踪文件:")
for l in subprocess.run(["git", "-C", MAIN, "ls-files", "dev/three-demo"],
                        capture_output=True, text=True).stdout.splitlines():
    print("     " + l)
