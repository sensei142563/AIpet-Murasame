# -*- coding: utf-8 -*-
"""① QqScreen 支持嵌入模式（避免嵌套滚动崩溃） ② 首页加同级 QQ chatter 卡 ③ 删掉抽屉里的 QQ 通道 ④ 编译提交"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
CHAT = r"E:\university\order\python\pet\chatter"
QQS = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/QqScreen.kt")
HOME = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/HomeScreen.kt")
CHATSCREEN = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/ChatScreen.kt")
MAP = os.path.join(MAIN, "dev", "merge-map")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")
ok = True


def note(m, c):
    global ok
    print(("✓ " if c else "✗ ") + m)
    if not c:
        ok = False


# ---------- ① QqScreen：公开 QqClient + 支持嵌入 ----------
s = io.open(QQS, encoding="utf-8").read().replace("\r\n", "\n")
s = s.replace("private object QqClient {", "internal object QqClient {", 1)
s = s.replace("fun QqScreen(onBack: () -> Unit) {",
              "fun QqScreen(onBack: () -> Unit = {}, embedded: Boolean = false) {", 1)
old_root = """    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {"""
new_root = """    // 嵌入首页时必须去掉 fillMaxSize + 内层滚动（否则与首页滚动形成无限高度约束 → 崩）
    val rootMod = if (embedded) Modifier.fillMaxWidth().padding(horizontal = 4.dp, vertical = 6.dp)
    else Modifier.fillMaxSize().verticalScroll(rememberScrollState())
        .padding(horizontal = 16.dp, vertical = 12.dp)
    Column(rootMod, verticalArrangement = Arrangement.spacedBy(12.dp)) {"""
note("QqScreen 支持嵌入", old_root in s)
if old_root in s:
    s = s.replace(old_root, new_root, 1)
# 嵌入时不显示返回按钮
s = s.replace('            TextButton(onClick = onBack) { Text("← 返回") }',
              '            if (!embedded) TextButton(onClick = onBack) { Text("← 返回") }', 1)
io.open(QQS, "w", encoding="utf-8", newline="\n").write(s)

# ---------- ② 首页加 QQ chatter 卡 ----------
h = io.open(HOME, encoding="utf-8").read().replace("\r\n", "\n")
if "QQ chatter" in h:
    note("首页已有 QQ chatter 卡", True)
else:
    if "rememberCoroutineScope" not in h:
        h = h.replace("import androidx.compose.runtime.remember\n",
                      "import androidx.compose.runtime.remember\nimport androidx.compose.runtime.rememberCoroutineScope\n", 1)
    anchor = """                Text(
                    if (status.loggedIn) "已登录 ${if (status.botId.isNotBlank()) "· ${status.botId}" else ""}"
                    else "首次使用需要用微信扫码绑定",
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
"""
    note("定位微信 chatter 卡末尾", anchor in h)
    card = anchor + """
        // ===== QQ chatter（与上面的微信 chatter **同级**）=====
        // 说明：QQ 侧跑在电脑上（NapCat 是 PC 端 QQNT 插件，手机装不了），
        // 这里给的是"同级入口 + 实时状态"：展开即可看会话、看队列、把要说的话投进发送队列。
        Spacer(Modifier.height(14.dp))
        Card(shape = RoundedCornerShape(20.dp)) {
            Column(Modifier.padding(16.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("QQ chatter", fontSize = 18.sp,
                        fontWeight = androidx.compose.ui.text.font.FontWeight.Bold)
                    Spacer(Modifier.weight(1f))
                    TextButton(onClick = { qqOpen = !qqOpen }) {
                        Text(if (qqOpen) "收起" else "展开")
                    }
                }
                Text(qqLine, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Spacer(Modifier.height(10.dp))
                Button(
                    onClick = {
                        if (!qqOpen) { qqOpen = true; qqRefresh++ }
                        else qqOpen = false
                    },
                    enabled = qqOpen || !busy,
                    shape = RoundedCornerShape(18.dp),
                    modifier = Modifier.fillMaxWidth().height(48.dp)
                ) {
                    Text(if (qqOpen) "收起 QQ 通道" else "打开 QQ 通道", fontSize = 15.sp,
                        fontWeight = androidx.compose.ui.text.font.FontWeight.Bold)
                }
                if (qqOpen) {
                    Spacer(Modifier.height(6.dp))
                    QqScreen(onBack = { qqOpen = false }, embedded = true)
                }
            }
        }
"""
    h = h.replace(anchor, card, 1)
    # 状态变量与拉取
    var_anchor = "fun HomeScreen() {"
    note("定位 HomeScreen 函数头", var_anchor in h)
    h = h.replace(var_anchor, var_anchor + """
    var qqOpen by remember { mutableStateOf(false) }
    var qqLine by remember { mutableStateOf("（电脑端地址未配置：设置 → Jev 电脑地址）") }
    var qqRefresh by remember { mutableIntStateOf(0) }
    LaunchedEffect(qqRefresh) {
        qqLine = withContext(Dispatchers.IO) {
            runCatching {
                val st = com.aipet.murasame.ui.QqClient.get("/qq/status") ?: return@runCatching
                    "连不上电脑端 api.py（" + QqClient.base().ifEmpty { "地址为空" } + "）"
                val ob = QqClient.get("/qq/outbox")
                val on = st.optBoolean("napcat_ws_listening", false)
                "NapCat：" + (if (on) "在线 ✓" else "离线（需在电脑上启动并登录）") +
                    "   会话 " + st.optInt("sessions") +
                    "   待发送 " + (ob?.optInt("pending_bytes") ?: 0) + " 字节"
            }.getOrElse { "读取失败：" + it.javaClass.simpleName }
        }
    }
""", 1)
    io.open(HOME, "w", encoding="utf-8", newline="\n").write(h)
    note("首页已加 QQ chatter 卡", "QQ chatter" in h)

# ---------- ③ 抽屉里去掉 QQ 通道 ----------
c = io.open(CHATSCREEN, encoding="utf-8").read().replace("\r\n", "\n")
if "💬 QQ 通道" in c:
    c = c.replace("""                    Text("💬 QQ 通道", fontSize = 14.5.sp, color = Color.White.copy(alpha = 0.9f),
                        modifier = Modifier.fillMaxWidth().clickable { showDrawer = false; showQq = true }
                            .padding(horizontal = 18.dp, vertical = 12.dp))
""", "", 1)
    c = c.replace("""        if (showQq) {
            // 第 3 步：手机端 QQ 通道页（遥控电脑上的 NapCat）
            QqScreen(onBack = { showQq = false })
        }
""", "", 1)
    c = c.replace("    var showQq by remember { mutableStateOf(false) }\n", "", 1)
    io.open(CHATSCREEN, "w", encoding="utf-8", newline="\n").write(c)
    note("已从抽屉移除 QQ 通道（入口改到首页）", "💬 QQ 通道" not in c)
else:
    note("抽屉里本来就没有 QQ 通道", True)

if not ok:
    print("✗ 有步骤失败，回滚")
    for f in (QQS, HOME, CHATSCREEN):
        subprocess.run(["git", "-C", CHAT, "checkout", "--", os.path.relpath(f, CHAT).replace("\\", "/")],
                       capture_output=True)
    sys.exit(1)

print()
print("=== 编译 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o.splitlines() if x.startswith("e: ")][:12]:
    print("   " + y[:230])
if r.returncode != 0:
    print("✗ 编译失败（未提交）")
    sys.exit(1)

MSG = """feat(ui): 首页新增同级「QQ chatter」卡；移除抽屉里的「QQ 通道」；修 3D 页无法运行的根因

一、3D 页根因（用户反馈"3D 的 AR 没成功"——属实，此前只在电脑上验证过）：
    用 file:// 打开 assets/vrm/index.html 实测，Chromium 直接拦掉 ES module：
      "Access to script at 'file:///…/vendor/three.js' from origin 'null' has been blocked by CORS policy"
      net::ERR_FAILED → 页面里 <script type="module"> 根本不执行 → 手机上必然白屏。
    修法：改用 **WebViewAssetLoader**（新增 androidx.webkit:webkit:1.12.1），页面走
    https://appassets.androidplatform.net/assets/vrm/index.html（正经 origin，module 正常），
    模型走**同源**自定义路径 /vrmmodel/model.vrm → 应用外部目录里的 .vrm（不入库）。
    同时关掉 allowFileAccess/allowFileAccessFromFileURLs（不再需要 file://）。
    诚实标注：**真机仍未验证**（手机不在线），不再声称"3D 成功"。

二、QQ 入口按用户要求搬到首页，与微信 chatter 同级：
    · HomeScreen 新增「QQ chatter」卡（就在微信 chatter 卡下方、同层级）：
      实时状态行（NapCat 在线/离线 · 会话数 · 待发送字节，来自电脑 /qq/status 与 /qq/outbox）
      + 展开/收起按钮；展开后**内嵌** QqScreen（复用现成页面，不重复造）。
    · QqScreen 增加 embedded 模式：嵌入时去掉 fillMaxSize 与内层 verticalScroll，
      避免与首页滚动形成无限高度约束而崩；嵌入时不显示返回按钮。
    · 抽屉里的「💬 QQ 通道」入口与对应渲染分支已删除（入口只在首页）。
"""
p = os.path.join(MAP, "_msg_qqhome.txt")
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
