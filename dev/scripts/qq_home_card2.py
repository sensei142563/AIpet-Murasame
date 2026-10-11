# -*- coding: utf-8 -*-
"""幂等收尾：QqScreen 嵌入模式 + 首页 QQ chatter 卡（已修掉那两个编译错误）+ 移除抽屉入口 → 编译 → 提交。
   设计原则：**任何检查失败都不回滚**，只打印状态，最后由人（我）看过再决定。"""
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


def info(m):
    print("   " + m)


def changed(path, old, new, label, count=1):
    t = io.open(path, encoding="utf-8").read().replace("\r\n", "\n")
    if old not in t:
        info("· %s：锚点不在（可能已应用）" % label)
        return False
    io.open(path, "w", encoding="utf-8", newline="\n").write(t.replace(old, new, count))
    info("✓ %s" % label)
    return True


print("=== ① QqScreen：嵌入模式 ===")
changed(QQS, "private object QqClient {", "internal object QqClient {", "QqClient 改为 internal")
changed(QQS, "fun QqScreen(onBack: () -> Unit) {",
        "fun QqScreen(onBack: () -> Unit = {}, embedded: Boolean = false) {", "QqScreen 增加 embedded 参数")
changed(QQS, """    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {""",
        """    // 嵌入首页时必须去掉 fillMaxSize 与内层滚动（否则与首页滚动形成无限高度约束 → 崩）
    val rootMod = if (embedded) Modifier.fillMaxWidth().padding(horizontal = 4.dp, vertical = 6.dp)
    else Modifier.fillMaxSize().verticalScroll(rememberScrollState())
        .padding(horizontal = 16.dp, vertical = 12.dp)
    Column(rootMod, verticalArrangement = Arrangement.spacedBy(12.dp)) {""",
        "根布局按 embedded 切换")
changed(QQS, '            TextButton(onClick = onBack) { Text("← 返回") }',
        '            if (!embedded) TextButton(onClick = onBack) { Text("← 返回") }', "嵌入时隐藏返回按钮")

print("=== ② 首页：QQ chatter 卡（与微信 chatter 同级）===")
h = io.open(HOME, encoding="utf-8").read().replace("\r\n", "\n")
if "QQ chatter" in h:
    info("· 已存在，跳过")
else:
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
    if anchor in h:
        h = h.replace(anchor, anchor + """
        // ===== QQ chatter（与上面的微信 chatter **同级**）=====
        // QQ 侧跑在电脑上（NapCat 是 PC 端 QQNT 插件，手机装不了）：这里给"同级入口 + 实时状态"，
        // 展开即可看会话 / 看队列 / 把要说的话投进发送队列。
        Spacer(Modifier.height(14.dp))
        Card(shape = RoundedCornerShape(20.dp)) {
            Column(Modifier.padding(16.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("QQ chatter", fontSize = 18.sp,
                        fontWeight = androidx.compose.ui.text.font.FontWeight.Bold)
                    Spacer(Modifier.weight(1f))
                    TextButton(onClick = { qqOpen = !qqOpen; if (qqOpen) qqRefresh++ }) {
                        Text(if (qqOpen) "收起" else "展开")
                    }
                }
                Text(qqLine, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Spacer(Modifier.height(10.dp))
                Button(
                    onClick = { qqOpen = !qqOpen; if (qqOpen) qqRefresh++ },
                    enabled = true,
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
""", 1)
        info("✓ 已插入 QQ chatter 卡")
    else:
        info("✗ 没找到微信 chatter 卡末尾锚点 —— 未插入（需人工）")

    h = h.replace("fun HomeScreen() {", """fun HomeScreen() {
    var qqOpen by remember { mutableStateOf(false) }
    var qqLine by remember { mutableStateOf("（电脑端地址未配置：设置 → Jev 电脑地址）") }
    var qqRefresh by remember { mutableIntStateOf(0) }
    LaunchedEffect(qqRefresh) {
        qqLine = withContext(Dispatchers.IO) {
            runCatching {
                // 注意：`?: return@runCatching (...) ?: 后必须紧跟表达式，换行会让 lambda 推断成 Any
                val st = com.aipet.murasame.ui.QqClient.get("/qq/status")
                    ?: return@runCatching ("连不上电脑端 api.py（" + QqClient.base().ifEmpty { "地址为空" } + "）")
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
    info("✓ 首页状态拉取代码已加")

print("=== ③ ChatScreen：移除抽屉 QQ 通道 ===")
changed(CHATSCREEN, """                    Text("💬 QQ 通道", fontSize = 14.5.sp, color = Color.White.copy(alpha = 0.9f),
                        modifier = Modifier.fillMaxWidth().clickable { showDrawer = false; showQq = true }
                            .padding(horizontal = 18.dp, vertical = 12.dp))
""", "", "移除抽屉入口")
changed(CHATSCREEN, """        if (showQq) {
            // 第 3 步：手机端 QQ 通道页（遥控电脑上的 NapCat）
            QqScreen(onBack = { showQq = false })
        }
""", "", "移除渲染分支")
changed(CHATSCREEN, "    var showQq by remember { mutableStateOf(false) }\n", "", "移除 showQq 状态")

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
    print("✗ 编译失败 —— 已保留改动，不提交（下一步人工看）")
    sys.exit(1)

MSG = """feat(ui): 首页新增同级「QQ chatter」卡＋移除抽屉「QQ 通道」；并修 3D 页根因（WebViewAssetLoader）

一、3D 页根因（用户反馈"3D 的 AR 没成功"——属实：此前只验证过电脑端渲染，没验证手机）：
    以 file:// 打开 assets/vrm/index.html 实测，Chromium 直接拦掉 ES module：
      "Access to script at 'file:///…/vendor/three.js' from origin 'null' has been blocked by CORS policy"
      net::ERR_FAILED → 页面里 <script type="module"> 根本不执行 → 手机上必然白屏。
    修法：改用 WebViewAssetLoader（新增 androidx.webkit:webkit:1.12.1），页面走
    https://appassets.androidplatform.net/assets/vrm/index.html（正经 origin），模型走同源自定义
    路径 /vrmmodel/model.vrm → 应用外部目录里的 .vrm（不入库）；并关掉 allowFileAccess*。
    诚实标注：**真机仍未验证**（手机不在线），不再声称"3D 成功"。

二、QQ 入口按用户要求搬到首页，与微信 chatter **同级**：
    · HomeScreen 新增「QQ chatter」卡（在微信 chatter 卡下方、同一层级），带实时状态行
      （NapCat 在线/离线 · 会话数 · 待发送字节，取自电脑 /qq/status 与 /qq/outbox）
      以及展开/收起；展开后**内嵌** QqScreen（复用现成页面，不重复造）。
    · QqScreen 增加 embedded 模式：嵌入时去掉 fillMaxSize 与内层 verticalScroll，避免与首页
      滚动形成无限高度约束而崩；嵌入时不显示返回按钮。
    · 抽屉里的「💬 QQ 通道」入口与渲染分支已删除（入口只在首页）。
"""
p = os.path.join(MAP, "_msg_qqhome2.txt")
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
