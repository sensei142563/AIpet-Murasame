# -*- coding: utf-8 -*-
"""提交：返回键修复 + AR 沉浸/干净模式 + 音量下键快门。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
CHAT = r"E:\university\order\python\pet\chatter"
MAP = os.path.join(MAIN, "dev", "merge-map")

MSG = """feat(ar+nav): 返回键不再直接退出；AR 沉浸全屏+干净模式；音量下键当快门

用户反馈三点，逐条实现（编译通过；**真机未验证** —— 手机不在手边）：

① 返回键（原状：全 App 没有 BackHandler ⇒ 任何页面按返回都直接退出）
   · MainActivity 加总入口 BackHandler：先按导航历史回退（点导航栏时压栈，上限 20 层），
     再退到首页；退无可退时**第一次提示「再按一次返回键退出」**，2 秒内再按才 finish()。
   · 子页面（会话抽屉 / ＋面板 / 设置 / AR / VRM）各自的 BackHandler 会**优先**接管
     （Compose BackHandler 后进先出），因此"返回 = 回上一页"对所有子页面成立。
   · 踩坑：LocalContext.current 是 @Composable 的，不能在 BackHandler 的普通 lambda 里取，
     必须在组合期先取出 activity 引用。

② AR 全屏、干净、无遮挡
   · 沉浸式：进入 AR 隐藏状态栏/导航栏（WindowInsetsControllerCompat +
     BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE），离开时恢复（DisposableEffect）。
   · 新增「干净」模式：一键隐藏顶栏与底栏全部控件，只留一个极小的「控件」按钮；
     拍照瞬间本来就会隐藏界面元素，所以成片始终干净。

③ 音量下键拍照（屏幕因此可以什么都不画）
   · ArScreen 打开时把自己的快门注册到文件级单例 ArShot；
     （踩坑：注册点必须写在 doShot **声明之后** —— Kotlin 局部函数先声明后使用，
       第一次插在声明之前导致 "Unresolved reference 'doShot'"。）
   · MainActivity.dispatchKeyEvent 在 ArShot.active 且收到 KEYCODE_VOLUME_DOWN（首次按下）时
     触发快门并**消费**事件（AR 里按音量键不改音量）。
     （踩坑：dispatchKeyEvent 必须在类级，第一次误插进 setContent 的 composable 里，
       Kotlin 报 "Modifier 'override' is not applicable to 'local function'"。）

未完成（下一步）：**把 3D(VRM) 叠到相机上做成真正的 3D AR**，并让同一音量键拍照 ——
方案已定：窗口级 PixelCopy 可以把"相机预览 + WebView(WebGL)"一次性合成为一张图
（Live2D 那条已有自己的合成路径，不受影响）。当前 VRM 页只是全屏 WebView 演示，没有相机，
所以"3D AR 拍照"要等 3D AR 本身先做出来。
"""
p = os.path.join(MAP, "_msg_ar3.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("手机仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:130])
n = subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True).stdout.strip()
st = subprocess.run(["git", "-C", CHAT, "status", "--porcelain"],
                    capture_output=True, text=True).stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
print()
print("=== 关键实现行复核 ===")
checks = [
    (os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/MainActivity.kt"),
     ["override fun dispatchKeyEvent", "ArShot.active", "BackHandler(enabled = true)",
      "再按一次返回键退出", "tabHistory.removeAt", "actRef?.finish()"]),
    (os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/ArScreen.kt"),
     ["object ArShot", "ArShot.shoot = { doShot() }", "cleanChrome = true",
      "BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE", "SmallBtn(\"控件\", false)"]),
]
for f, pats in checks:
    t = io.open(f, encoding="utf-8", errors="replace").read()
    print("   " + os.path.basename(f))
    for p2 in pats:
        print("      %-44s %s" % (p2[:44], "✓" if p2 in t else "✗"))
