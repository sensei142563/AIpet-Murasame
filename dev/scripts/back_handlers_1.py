# -*- coding: utf-8 -*-
"""纠正我自己的过度声称：给 ChatScreen 的 5 个子页面状态各加 BackHandler（关页面而不是走全局历史），
   首页展开的 QQ 卡也加一个。Compose 的 BackHandler 后组合者优先，
   MainActivity 的全局处理器在 ChatScreen 之前组合 → 子页面会正确抢先。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
CHAT = r"E:\university\order\python\pet\chatter"
UI = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui")
CHATSCREEN = os.path.join(UI, "ChatScreen.kt")
HOME = os.path.join(UI, "HomeScreen.kt")
MAP = os.path.join(MAIN, "dev", "merge-map")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

t = io.open(CHATSCREEN, encoding="utf-8").read().replace("\r\n", "\n")
if "BackHandler(enabled = showDrawer)" in t:
    print("· ChatScreen 已有子页面 BackHandler")
else:
    if "import androidx.activity.compose.BackHandler" not in t:
        t = t.replace("import androidx.compose.foundation.background",
                      "import androidx.activity.compose.BackHandler\nimport androidx.compose.foundation.background", 1)
    # 插入到第一个子页面渲染分支之前（showAr/showVrm/showSettings 三者依次出现）
    anchor = "        if (showAr) {"
    if anchor not in t:
        print("✗ 找不到 showAr 分支锚点")
        sys.exit(1)
    handlers = """        // ── 子页面返回键：每一层自己接管，按返回是"回上一层"而不是退出 App ──
        // （ChatScreen 在 MainActivity 之后组合，所以这些 handler 会先于全局处理器拿到返回键；
        //   同一页面里多层同时为真时，后写的先生效。）
        BackHandler(enabled = showDrawer) { showDrawer = false }
        BackHandler(enabled = showPlus) { showPlus = false }
        BackHandler(enabled = showSettings) { showSettings = false }
        BackHandler(enabled = showVrm) { showVrm = false }
        BackHandler(enabled = showAr) { showAr = false }

"""
    t = t.replace(anchor, handlers + anchor, 1)
    io.open(CHATSCREEN, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ ChatScreen 已加 5 个子页面 BackHandler")

h = io.open(HOME, encoding="utf-8").read().replace("\r\n", "\n")
if "BackHandler(enabled = qqOpen)" in h:
    print("· HomeScreen 已有 QQ 卡 BackHandler")
else:
    if "import androidx.activity.compose.BackHandler" not in h:
        h = h.replace("import androidx.compose.foundation.background",
                      "import androidx.activity.compose.BackHandler\nimport androidx.compose.foundation.background", 1)
    anchor2 = "    val ctx = LocalContext.current\n    val app = ctx.applicationContext as com.aipet.murasame.App"
    if anchor2 in h:
        h = h.replace(anchor2, "    // 展开的 QQ 面板也吃返回键：先收起，再谈其它\n    BackHandler(enabled = qqOpen) { qqOpen = false }\n" + anchor2, 1)
        io.open(HOME, "w", encoding="utf-8", newline="\n").write(h)
        print("✓ HomeScreen 已加 QQ 卡 BackHandler")
    else:
        print("⚠ HomeScreen 未命中锚点（跳过，不影响 ChatScreen）")

print()
print("=== 编译 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o.splitlines() if x.startswith("e: ")][:10]:
    print("   " + y[:220])
if r.returncode != 0:
    print("✗ 编译失败（未提交）")
    sys.exit(1)

MSG = """fix(nav): 补上子页面自己的 BackHandler —— 上一提交的说明过度声称了

上一提交（e53f62c）说"子页面各自的 BackHandler 会优先接管"，但实测全工程**只有 MainActivity**
一个 BackHandler，子页面（会话抽屉/＋面板/设置/AR/VRM）都没有 ⇒ 在这些页面按返回走的是
全局逻辑（历史/回首页），并没有"关掉当前页面"。

本次补齐：
· ChatScreen 为 showDrawer / showPlus / showSettings / showVrm / showAr 各加一个
  BackHandler(enabled = ...) { 关闭 }。ChatScreen 在 MainActivity 之后组合，
  Compose 的返回回调是后加者优先 ⇒ 子页面会正确抢先，返回=回上一层。
· HomeScreen 为展开的 QQ 面板加 BackHandler（先收起面板）。
· 同页多层同时为真时，按"后写的先生效"排序（VRM 在 AR 之前渲染，故 AR 的处理在后）。

教训：提交信息里写"已经具备某某行为"之前，必须**grep 取证**，不能凭设计意图推断。
"""
p = os.path.join(MAP, "_msg_back1.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("手机仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:130])
print()
print("=== 复核：现在有几个 BackHandler ===")
n = 0
for f in (os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/MainActivity.kt"),
          CHATSCREEN, HOME):
    c = sum(1 for l in io.open(f, encoding="utf-8", errors="replace") if "BackHandler(enabled" in l)
    n += c
    print("   %-14s %d 个" % (os.path.basename(f), c))
print("   合计 %d 个" % n)
st = subprocess.run(["git", "-C", CHAT, "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
nn = subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                    capture_output=True, text=True).stdout.strip()
print("   未推送 %s 条，工作区 %s" % (nn, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
