# -*- coding: utf-8 -*-
"""提交 UI 复查修复：遮罩 + 暗色一致 + 规范文档。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
CHAT = r"E:\university\order\python\pet\chatter"
MAP = os.path.join(MAIN, "dev", "merge-map")

MSG = """fix(ui): 复查两个界面问题——新页必须全屏遮罩；设置页写死亮色改为主题暗色

用户复查指出两点，均以代码取证确认后修复：

① 全屏遮罩：聊天页里 showAr/showVrm/showSettings 三个新页**没有**遮罩层（showDrawer/showPlus 有）。
   其中 **VrmScreen 根节点没有底色** ⇒ 直接透出底下的聊天页、甚至能看到聊天消息（用户实际看到的现象）。
   处理：
     · showVrm 调用点套一层不透明铺满 Box(fillMaxSize().background(colorScheme.background))；
     · VrmScreen、QqScreen（独立整页时）自身根节点也加不透明底（防御：以后被别处复用也不透）；
       补 background import；SettingsPage 补 MaterialTheme import 并去重。
     · ArScreen 自身已有 background(Color.Black)，不动。

② 配色不一致：App 固定深色（Theme.kt darkColorScheme：background=#0E1218、surface=#151C26、
   surfaceVariant=#1B2432、onSurface=#E7EDF3、onSurfaceVariant=#9FACBC），但 SettingsPage.kt 写死了浅色：
   bg=0xFFF5F6F8、card=0xFFFFFFFF、title=0xFF9AA0A6、text=0xFF1F2329、sub=0xFF8A9099，
   另有图标 tint 0xFFC4C8CC 与分段底色 0xFFEDEFF2。
   ⇒ 正是"整体暗色，从 ☰（三条线）进去的设置页却是亮色"。
   处理：全部改为 MaterialTheme.colorScheme.*。
   保留例外：LoginSheet 的二维码白底（要扫得动）、Common.kt 生成二维码位图的黑白。

编译：BUILD SUCCESSFUL。
规范：见桌面仓 dev/docs/UI规范-遮罩与暗色.md（含现状核查表与可复用排查命令）。
"""
p = os.path.join(MAP, "_msg_ui2.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r1 = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("手机仓:", (r1.stdout or r1.stderr or "").splitlines()[0][:130])
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
r2 = subprocess.run(["git", "-C", MAIN, "commit", "-m",
                     "docs(ui): UI 规范——新页面必须全屏遮罩、配色一律走主题（附现状核查表与排查命令）"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
print("桌面仓:", (r2.stdout or r2.stderr or "").splitlines()[0][:130])
print()
print("=== 校验 ===")
for name, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True).stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"],
                        capture_output=True, text=True).stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (name, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
print()
print("=== 复查修复是否真的落地（grep 关键行）===")
for f, pat in (("SettingsPage.kt", "val bg = MaterialTheme.colorScheme.background"),
               ("VrmScreen.kt", ".background(MaterialTheme.colorScheme.background)"),
               ("QqScreen.kt", ".background(MaterialTheme.colorScheme.background)"),
               ("ChatScreen.kt", "Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background))")):
    t = io.open(os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui", f),
                encoding="utf-8", errors="replace").read()
    print("   %-16s %s" % (f, "✓" if pat in t else "✗"))
print("   SettingsPage 还有写死亮色吗：",
      "无 ✓" if "Color(0xFFF5F6F8)" not in io.open(
          os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/SettingsPage.kt"),
          encoding="utf-8", errors="replace").read() else "仍有 ✗")
