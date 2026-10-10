# -*- coding: utf-8 -*-
"""情绪→动作：Live2DView 内部合成命中区触摸（自包含）+ ChatScreen 传 motionHint（仅丛雨）→ 编译装机提交。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
BASE = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame")
LV = os.path.join(BASE, "ui/Live2DView.kt")
CS = os.path.join(BASE, "ui/ChatScreen.kt")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
MAP = r"E:\university\order\python\pet\_audit_fish9269\merge-map"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

# ① Live2DView：加 motionHint 参数 + 尺寸记录 + 合成触摸
s = io.open(LV, encoding="utf-8", newline="").read()
if "motionHint" not in s:
    L = s.splitlines(keepends=True)
    # 签名：加参数（按行号）
    i = next(k for k, l in enumerate(L) if re.match(r"\s*fun Live2DView\(", l))
    j = i
    while not re.search(r"\)\s*\{\s*$", L[j].rstrip()):
        j += 1
    eol = "\r\n" if L[i].endswith("\r\n") else "\n"
    ind = re.match(r"(\s*)", L[i]).group(1)
    L[i:j + 1] = [ind + "fun Live2DView(modifier: Modifier = Modifier, expressionId: String? = null," + eol +
                  ind + "                modelDir: String? = null, overlay: Boolean = false," + eol +
                  ind + "                motionHint: String? = null) {" + eol]
    # 在 l2dReady 状态声明之后插入尺寸状态与合成触摸 effect
    k = next(x for x, l in enumerate(L) if "var l2dReady by remember" in l)
    eol2 = "\r\n" if L[k].endswith("\r\n") else "\n"
    ind2 = re.match(r"(\s*)", L[k]).group(1)
    blk = [
        eol2,
        ind2 + "// [motion] 命中区触摸所需的视图尺寸（与 native 触摸回调同一坐标系：视图像素）" + eol2,
        ind2 + "var viewSize by remember { mutableStateOf(androidx.compose.ui.unit.IntSize.Zero) }" + eol2,
    ]
    L = L[:k + 1] + blk + L[k + 1:]
    # 在 expressionId 的 LaunchedEffect 之后，加 motionHint 的 effect
    k2 = next(x for x, l in enumerate(L) if "LaunchedEffect(expressionId, l2dReady)" in l)
    # 找到该 effect 的结束（配平）
    d = 0
    m = k2
    while m < len(L):
        d += L[m].count("{") - L[m].count("}")
        if d <= 0 and m > k2:
            break
        m += 1
    eol3 = "\r\n" if L[k2].endswith("\r\n") else "\n"
    ind3 = re.match(r"(\s*)", L[k2]).group(1)
    eff = [
        eol3,
        ind3 + "// [motion] 按情绪提示合成一次「命中区触摸」，让 C++ 侧播放对应动作" + eol3,
        ind3 + "//   （native 桥没有独立的播动作接口；命中判定在 C++ 里，靠 touch 触发）" + eol3,
        ind3 + "LaunchedEffect(motionHint, l2dReady, viewSize) {" + eol3,
        ind3 + "    val hint = motionHint ?: return@LaunchedEffect" + eol3,
        ind3 + "    if (!l2dReady || viewSize.width <= 0 || viewSize.height <= 0) return@LaunchedEffect" + eol3,
        ind3 + "    // 命中区相对坐标（按截图观察先给经验值，可再微调）" + eol3,
        ind3 + "    val (fx, fy) = when (hint) {" + eol3,
        ind3 + "        \"hair\"  -> 0.50f to 0.10f" + eol3,
        ind3 + "        \"face\"  -> 0.50f to 0.26f" + eol3,
        ind3 + "        \"chest\" -> 0.50f to 0.45f" + eol3,
        ind3 + "        \"skirt\" -> 0.50f to 0.63f" + eol3,
        ind3 + "        \"leg\"   -> 0.50f to 0.84f" + eol3,
        ind3 + "        else     -> return@LaunchedEffect" + eol3,
        ind3 + "    }" + eol3,
        ind3 + "    val x = viewSize.width * fx" + eol3,
        ind3 + "    val y = viewSize.height * fy" + eol3,
        ind3 + "    runCatching {" + eol3,
        ind3 + "        JniBridgeJava.nativeOnTouchesBegan(x, y)" + eol3,
        ind3 + "        JniBridgeJava.nativeOnTouchesEnded(x, y)" + eol3,
        ind3 + "        l2dLog(\"motion touch: \" + hint + \" @\" + x.toInt() + \",\" + y.toInt())" + eol3,
        ind3 + "    }.onFailure { l2dLog(\"motion touch 失败: \" + it.message) }" + eol3,
        ind3 + "}" + eol3,
    ]
    L = L[:m + 1] + eff + L[m + 1:]
    s = "".join(L)
    # AndroidView 的 modifier 加 onSizeChanged 记录尺寸
    s = s.replace("        modifier = modifier.fillMaxSize(),",
                  "        modifier = modifier.fillMaxSize().onSizeChanged { viewSize = it },", 1)
    if "onSizeChanged" not in s:
        # 若上面那句没命中，换成 AndroidView( 之后的 modifier 行
        s = re.sub(r"(AndroidView\(\s*\n\s*modifier = [^\n]*?)(,)", r"\1.onSizeChanged { viewSize = it }\2", s, count=1)
    if "import androidx.compose.ui.layout.onSizeChanged" not in s:
        s = s.replace("import androidx.compose.ui.viewinterop.AndroidView",
                      "import androidx.compose.ui.layout.onSizeChanged\nimport androidx.compose.ui.viewinterop.AndroidView", 1)
    io.open(LV, "w", encoding="utf-8", newline="").write(s)
    print("✓ Live2DView：加 motionHint + 尺寸记录 + 合成触摸")
else:
    print("（Live2DView 已有 motionHint）")

# ② ChatScreen：情绪 → 命中区（仅丛雨）
c = io.open(CS, encoding="utf-8", newline="").read()
if "motionHintOf" not in c:
    # 加映射函数（放在 emotionOf 之前）
    k = next(x for x, l in enumerate(c.splitlines()) if "private fun emotionOf(reply: String): String {" in l)
    Lc = c.splitlines(keepends=True)
    eol = "\r\n" if Lc[k].endswith("\r\n") else "\n"
    fn = [
        "// [motion] 情绪 → Live2D 命中区（只有丛雨的模型声明了动作；诺瓦没有动作，返回 null 即不触发）" + eol,
        "private fun motionHintOf(emotion: String): String? = when (emotion) {" + eol,
        "    \"生气\", \"吐槽\", \"不满\" -> \"face\"" + eol,
        "    \"害羞\", \"脸红\" -> \"hair\"" + eol,
        "    \"开心\", \"高兴\", \"笑\" -> \"face\"" + eol,
        "    \"难过\", \"伤心\", \"低落\" -> \"chest\"" + eol,
        "    else -> null" + eol,
        "}" + eol,
        eol,
    ]
    Lc = Lc[:k] + fn + Lc[k:]
    c = "".join(Lc)
    # 在聊天页 Live2DView 调用处传参
    m = re.search(r"(Live2DView\(\s*\n(?:[^)]*?\n)*?\s*)\)", c)
    if m and "motionHint" not in m.group(0):
        seg = m.group(0)
        newseg = seg[:-1].rstrip()
        if not newseg.endswith(","):
            newseg += ","
        newseg += "\n                    motionHint = if (petId == \"murasame\") motionHintOf(ChatStore.emotion) else null,\n                )"
        c = c.replace(seg, newseg, 1)
        print("✓ ChatScreen Live2DView 调用处传入 motionHint")
    else:
        print("✗ 没找到聊天页的 Live2DView 调用（下一步手动加）")
    io.open(CS, "w", encoding="utf-8", newline="").write(c)
    print("✓ ChatScreen 加 motionHintOf()")
else:
    print("（ChatScreen 已有 motionHintOf）")

print("=== 编译 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o.splitlines() if x.startswith("e: ")][:8]:
    print("   " + y[:140])
if r.returncode != 0:
    subprocess.run(["git", "-C", CHAT, "checkout", "--",
                    "app/src/main/java/com/aipet/murasame/ui/Live2DView.kt",
                    "app/src/main/java/com/aipet/murasame/ui/ChatScreen.kt"], capture_output=True)
    print("   ✗ 回滚")
    sys.exit(1)
APK = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
print("   装机:", (subprocess.run([ADB, "install", "-r", APK], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=1800).stdout or "").strip()[-16:])

MSG = """feat(live2d): 情绪 → 动作（合成命中区触摸；仅丛雨，因其模型声明了动作）

背景：native 桥没有"直接播动作"的接口，动作是由 C++ 侧的**命中区触摸**驱动的
（摸头/摸脸/胸口/裙子/腿）。因此在不改 C++ 的前提下，用程序合成一次 touch 即可触发动作。

做法：
1) Live2DView 新增 motionHint: String? 参数；用 onSizeChanged 记录视图尺寸
   （与 native 触摸回调同一坐标系），在 LaunchedEffect(motionHint, l2dReady, viewSize) 里
   按提示映射到命中区相对坐标，调用 nativeOnTouchesBegan + nativeOnTouchesEnded。
2) ChatScreen 新增 motionHintOf(emotion) 映射，并在聊天页 Live2DView 调用处传入
   —— 仅当 petId == "murasame" 时启用（noir 的模型没有声明任何动作，保持只换表情）。

命中区相对坐标先给经验值（hair 0.10 / face 0.26 / chest 0.45 / skirt 0.63 / leg 0.84 高度处），
后续可按真机截图微调。

验证：assembleRelease 通过并装机。
"""
msg = os.path.join(MAP, "_msg_motion.txt")
io.open(msg, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r3 = subprocess.run(["git", "-C", CHAT, "commit", "-F", msg], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("   提交: " + (r3.stdout or r3.stderr or "").splitlines()[0][:110])
print("   未推送: " + subprocess.run(["git", "-C", CHAT, "rev-list", "--count", "origin/main..HEAD"],
                                    capture_output=True, text=True).stdout.strip() + " 条")
