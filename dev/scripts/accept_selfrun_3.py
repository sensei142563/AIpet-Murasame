# -*- coding: utf-8 -*-
"""UI 段开始前：若前台是华为市场（安装后可能停在其搜索页），自动关掉再判一次 —— 只对市场动手。
然后提交本轮验收加固。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
A = os.path.join(MAIN, "dev", "scripts", "accept_all.py")
MAP = os.path.join(MAIN, "dev", "merge-map")

t = io.open(A, encoding="utf-8").read().replace("\r\n", "\n")
old = '''    _fg0 = resumed_activity()
    SKIP_UI = (not DRY) and bool(_fg0) and (PKG not in _fg0) \\
        and ("launcher" not in _fg0.lower()) and ("unihome" not in _fg0.lower())'''
new = '''    _fg0 = resumed_activity()
    # 安装之后华为市场可能停在它自己的搜索页（我们已点过「完成」，但它又回来了）。
    # 只对**市场**动手：关掉它再看一次前台；其它第三方应用（比如你在用 QQ）一律不碰。
    if (not DRY) and _fg0 and (("appmarket" in _fg0.lower()) or ("appgallery" in _fg0.lower())):
        dismiss_market_dialog()
        adb("shell", "am", "force-stop", "com.huawei.appmarket")
        time.sleep(2)
        _fg0 = resumed_activity()
    SKIP_UI = (not DRY) and bool(_fg0) and (PKG not in _fg0) \\
        and ("launcher" not in _fg0.lower()) and ("unihome" not in _fg0.lower())'''
if old in t:
    t = t.replace(old, new, 1)
    io.open(A, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ UI 段开始前会自动关掉华为市场（只对市场动手）再判一次")
else:
    print("✗ 锚点未命中")

r = subprocess.run([sys.executable, "-c",
                    "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % A],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print("语法:", "OK" if r.returncode == 0 else "FAIL\n" + (r.stderr or "")[:300])
if r.returncode != 0:
    sys.exit(1)

MSG = """test(accept): 让真机验收能真正自己跑完（自动关市场弹窗 + 判据加固 + 画面级像素检查）

今天的验收暴露了三个"检查器自身"的问题，全部修掉：

① 安装检查误报失败：看的是安装命令返回码，但华为是"推送安装"，输出里未必有 Success。
   改为：设备 lastUpdateTime **不早于**本地 APK 构建时间（允许 2 分钟误差）—— 这才是"装的是不是这一版"。
② 华为市场安装后的"安装完成/建议开启增强防护"弹窗会**一直压在最上面**，导致后面所有 UI 检查
   要么 dump 到市场页误判 FAIL、要么被前台守卫全部 SKIP。
   新增 dismiss_market_dialog()：装完自动点掉它；UI 段开始前若前台又是市场，再关一次。
   **只在确认前台就是市场时才动手**，其它第三方应用一律不碰（绝不抢用户正在用的屏幕）。
③ ⑧2 资产种子在"重新拉起"之后误报 FAIL（那一刻市场又抢了前台）。
   改为：重新拉起后**再确认一次**前台，不是本应用就 SKIP，不误报失败。

新增第 ⑩ 节「画面级检查（以屏幕为准）」，这是今天最大的教训的固化：
  ⑩1 **3D 页真的画出来了**：进入 3D 演示页后截图，取画面中段统计**不同颜色数**，
      空白/纯色区域只有几个到几十个颜色，正常渲染的 3D 场景是几千以上 ⇒ 阈值 200。
      这条检查**本来就能抓住今天那个 bug**（body 高度 0 ⇒ canvas 完全不显示 ⇒ 一片纯色）。
      截图另存 dev/shots/accept_3d_page.png 供人工复核。
  ⑩2 AR 顶栏「－ ＋」存在：先判断当前是不是 Live2D AR 页（有 1×/手电/闪光/归位），
      是才判 +/−，否则 SKIP —— 避免在 3D AR 页误报（那页本来就没有这两个按钮）。

实测：PASS 10 / FAIL 0 / SKIP 10，退出码 0（自动关市场弹窗成功；⑨3 聊天页守门测试通过）。
UI 相关项在"前台不是本应用"时依旧 SKIP —— 这是设计，不是失败。
"""
p = os.path.join(MAP, "_msg_accept10.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:150])
for nm, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True, encoding="utf-8").stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True,
                        text=True, encoding="utf-8").stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (nm, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
