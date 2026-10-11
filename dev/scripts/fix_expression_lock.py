# -*- coding: utf-8 -*-
"""修「表情锁死在威胁/阴沉」：
   ① Live2DView：模型就绪前会静默丢弃 setExpression，改为最多等 4 秒轮询补发；
   ② ArScreen：把 expressionId 真正传给 Live2DView（原来收了参数却没用）。
"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
AR = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/ArScreen.kt")
L2D = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/Live2DView.kt")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
PKG = "com.aipet.murasame"
MAP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\merge-map"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")
ok = True


def note(m, c):
    global ok
    print(("✓ " if c else "✗ ") + m)
    if not c:
        ok = False


# ① Live2DView：轮询补发表情
L = io.open(L2D, encoding="utf-8").read().replace("\r\n", "\n").splitlines(keepends=True)
i0 = next((i for i, l in enumerate(L) if "LaunchedEffect(expressionId, l2dReady)" in l), None)
note("定位表情 LaunchedEffect", i0 is not None)
if i0 is not None:
    ind = re.match(r"(\s*)", L[i0]).group(1)
    i1 = None
    d = 0
    for j in range(i0, len(L)):
        d += L[j].count("{") - L[j].count("}")
        if d <= 0 and j > i0:
            i1 = j
            break
    note("定位该块结尾", i1 is not None)
    if i1 is not None:
        L[i0:i1 + 1] = [
            ind + "// 模型就绪前 setExpressionSafe 会静默丢弃，所以这里最多等 4 秒补发，\n",
            ind + "// 否则表情会锁死在上一次成功设置的那个上（用户实测：卡在「威胁」/「阴沉」）。\n",
            ind + "LaunchedEffect(expressionId, l2dReady) {\n",
            ind + "    val id = expressionId ?: return@LaunchedEffect\n",
            ind + "    repeat(40) {\n",
            ind + "        if (JniBridgeJava.modelReady) {\n",
            ind + "            try {\n",
            ind + "                JniBridgeJava.setExpressionSafe(id)\n",
            ind + '                l2dLog("setExpression $id")\n',
            ind + "            } catch (e: Throwable) {\n",
            ind + '                l2dLog("setExpression 失败: ${e.javaClass.name} ${e.message}")\n',
            ind + "            }\n",
            ind + "            return@LaunchedEffect\n",
            ind + "        }\n",
            ind + "        kotlinx.coroutines.delay(100)\n",
            ind + "    }\n",
            ind + '    l2dLog("setExpression 放弃（模型 4 秒内未就绪）: $id")\n',
            ind + "}\n",
        ]
        note("Live2DView 改为轮询补发表情", True)
io.open(L2D, "w", encoding="utf-8", newline="\n").write("".join(L))

# ② ArScreen：把 expressionId 传给 Live2DView
A = io.open(AR, encoding="utf-8").read().replace("\r\n", "\n").splitlines(keepends=True)
hit = next((i for i, l in enumerate(A) if l.strip() == "modelDir = modelDir,"), None)
note("定位 AR 里的 Live2DView 调用", hit is not None)
if hit is not None:
    ind = re.match(r"(\s*)", A[hit]).group(1)
    A[hit + 1:hit + 1] = [ind + "expressionId = expressionId,\n"]
    note("AR 把 expressionId 传下去", True)
    io.open(AR, "w", encoding="utf-8", newline="\n").write("".join(A))

if not ok:
    print("✗ 有步骤失败 —— 回滚两个文件")
    subprocess.run(["git", "-C", CHAT, "checkout", "--",
                    "app/src/main/java/com/aipet/murasame/ui/ArScreen.kt",
                    "app/src/main/java/com/aipet/murasame/ui/Live2DView.kt"], capture_output=True)
    sys.exit(1)

print("=== 编译 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o.splitlines() if x.startswith("e: ")][:8]:
    print("   " + y[:240])
if r.returncode != 0:
    print("   ✗ 编译失败（保留改动，按报错修）")
    sys.exit(1)


def itime():
    t = subprocess.run([ADB, "shell", "dumpsys", "package", PKG], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=300).stdout
    mm = re.search(r"lastUpdateTime=([^\n]+)", t)
    return mm.group(1).strip() if mm else "?"


before = itime()
APK = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
for att in range(1, 4):
    rr = subprocess.run([ADB, "install", "-r", "--no-streaming", APK], capture_output=True, text=True,
                        encoding="utf-8", errors="replace", timeout=3600)
    print("   装 %d:" % att, ((rr.stdout or rr.stderr or "").strip().splitlines() or [""])[-1][:44])
    time.sleep(3)
    now = itime()
    if now != before and now != "?":
        print("   ✓ 已装上:", now)
        break

MSG = """fix(live2d): 修「表情锁死在某个表情（威胁/阴沉）」+ AR 不设表情 + 拖动静止后拍照位置不符

用户实测：AR 与立绘预览里，丛雨的表情有时锁死在「威胁」或「阴沉」上。

根因（两处）：
  1) JniBridgeJava.setExpressionSafe() 里有 `if (!modelReady) return` —— 模型未就绪时**静默丢弃**；
     而 Live2DView 的 LaunchedEffect(expressionId, l2dReady) 只在 l2dReady 变化那一刻试一次，
     错过就再也不会补发 → 模型一直停在上一次成功设置的表情上。
     改为最多 4 秒（40 × 100ms）轮询等待 modelReady 后补发，并记录放弃日志。
  2) ArScreen 虽然声明了 expressionId 参数，却从没传给 Live2DView → AR 里根本不设置表情，
     显示的是聊天页最后留下的那一个。现在真正传下去。

同一提交还包含（上一轮已改完并装机、此处一并提交）：
  · 修「AR 拖动桌宠时一闪一闪退回 2D」：Live2DBusy 占用判断改为进入 AR 时用 remember 只判定一次；
  · 去掉相机录像功能（用户判定鸡肋）；Live2DBusy 新增；聊天页 Live2D 占用时 AR 退化分层立绘，避免
    Live2D 原生层单实例被两个实例同时使用而 SIGSEGV（用户 12:26/12:27 两次闪退）。
"""
msg = os.path.join(MAP, "_msg_expr.txt")
io.open(msg, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r3 = subprocess.run(["git", "-C", CHAT, "commit", "-F", msg], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("提交:", (r3.stdout or r3.stderr or "").splitlines()[0][:110])
print("未推送:", subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                                capture_output=True, text=True).stdout.strip(), "条")
print("工作区:", subprocess.run(["git", "-C", CHAT, "status", "--porcelain"],
                                capture_output=True, text=True).stdout.strip() or "干净 ✓")
