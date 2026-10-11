# -*- coding: utf-8 -*-
"""第 3 步：手机 QQ 页（状态 / 会话 / 消息 / 发送到队列）+ 抽屉入口 → 编译装机。"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
QQ = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/QqScreen.kt")
CHATSCREEN = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/ChatScreen.kt")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")
ok = True


def note(m, c):
    global ok
    print(("✓ " if c else "✗ ") + m)
    if not c:
        ok = False


io.open(QQ, "w", encoding="utf-8", newline="\n").write('''package com.aipet.murasame.ui

import android.content.Context
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.aipet.murasame.bot.chat.JevClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * QQ 通道页 —— 手机端操作**电脑上**的 QQ 通道。
 *
 * 为什么在手机上只能"远程操作"：QQ 侧靠 NapCat（PC 端 QQNT 插件）+ OneBot11 正向 WebSocket，
 * 手机装不了 NapCat；所以手机的职责是：看状态、看会话、看消息、把要说的话投进发送队列，
 * 由桌面端进程（握着 WS 的那个）真正发出（qq/qq_outbox.py）。
 *
 * 地址复用「Jev 电脑地址」（同一个 api.py），不新增设置项。
 */
private object QqClient {
    private val http = OkHttpClient.Builder()
        .connectTimeout(2500, TimeUnit.MILLISECONDS)
        .readTimeout(15000, TimeUnit.MILLISECONDS)
        .writeTimeout(3000, TimeUnit.MILLISECONDS)
        .build()
    private val JSON = "application/json; charset=utf-8".toMediaType()

    fun base(): String = JevClient.baseUrl.trim().trimEnd('/')

    /** GET，失败返回 null（绝不抛异常）。 */
    fun get(path: String): JSONObject? = runCatching {
        val b = base()
        if (b.isEmpty()) return null
        val req = Request.Builder().url(b + path).get().build()
        http.newCall(req).execute().use { resp ->
            if (!resp.isSuccessful) return null
            val t = resp.body?.string().orEmpty()
            if (t.isBlank()) null else JSONObject(t)
        }
    }.getOrNull()

    /** POST JSON，返回 (是否成功, 描述)。 */
    fun post(path: String, body: JSONObject): Pair<Boolean, String> = runCatching {
        val b = base()
        if (b.isEmpty()) return false to "未配置电脑地址"
        val req = Request.Builder().url(b + path)
            .post(body.toString().toRequestBody(JSON)).build()
        http.newCall(req).execute().use { resp ->
            val t = resp.body?.string().orEmpty()
            if (!resp.isSuccessful) return false to ("HTTP " + resp.code + " " + t.take(80))
            true to t
        }
    }.getOrElse { false to (it.javaClass.simpleName + ": " + it.message) }
}

@Composable
fun QqScreen(onBack: () -> Unit) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    var status by remember { mutableStateOf<JSONObject?>(null) }
    var sessions by remember { mutableStateOf<JSONArray?>(null) }
    var outbox by remember { mutableStateOf<JSONObject?>(null) }
    var err by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var detail by remember { mutableStateOf<Pair<String, List<JSONObject>>?>(null) }

    var targetType by remember { mutableStateOf("private") }
    var targetId by remember { mutableStateOf("") }
    var text by remember { mutableStateOf("") }
    var hint by remember { mutableStateOf("") }

    fun refresh() {
        scope.launch {
            busy = true
            val r = withContext(Dispatchers.IO) {
                Triple(QqClient.get("/qq/status"), QqClient.get("/qq/sessions"), QqClient.get("/qq/outbox"))
            }
            status = r.first
            sessions = r.second?.optJSONArray("sessions")
            outbox = r.third
            err = if (r.first == null) "连不上电脑端 api.py（" + (QqClient.base().ifEmpty { "地址为空" }) + "）" else ""
            busy = false
        }
    }
    LaunchedEffect(Unit) { refresh() }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = onBack) { Text("← 返回") }
            Text("QQ 通道", fontSize = 20.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.weight(1f))
            TextButton(enabled = !busy, onClick = { refresh() }) { Text(if (busy) "刷新中…" else "刷新") }
        }
        Text("地址（与「Jev 电脑地址」共用）: " + (QqClient.base().ifEmpty { "（未配置）" }),
            fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (err.isNotBlank()) {
            Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)) {
                Text(err, Modifier.padding(12.dp), fontSize = 13.sp)
            }
        }

        Card(shape = RoundedCornerShape(14.dp)) {
            Column(Modifier.padding(14.dp)) {
                Text("电脑端 QQ 状态", fontWeight = FontWeight.Medium, fontSize = 14.sp)
                Spacer(Modifier.height(6.dp))
                val st = status
                if (st == null) {
                    Text("（未取到，点刷新）", fontSize = 12.sp)
                } else {
                    val online = st.optBoolean("napcat_ws_listening", false)
                    Text(if (online) "NapCat：在线 ✓" else "NapCat：离线（需要在电脑上启动并登录）",
                        fontSize = 13.sp)
                    Text("WS 地址: " + st.optString("napcat_ws"), fontSize = 11.5.sp)
                    Text("主人 QQ: " + st.optString("owner_id") + "   会话数: " + st.optInt("sessions"),
                        fontSize = 11.5.sp)
                    Text("会话目录: " + st.optString("memory_dir"), fontSize = 10.5.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }

        Card(shape = RoundedCornerShape(14.dp)) {
            Column(Modifier.padding(14.dp)) {
                Text("发送队列", fontWeight = FontWeight.Medium, fontSize = 14.sp)
                Spacer(Modifier.height(6.dp))
                val ob = outbox
                if (ob == null) {
                    Text("（未取到）", fontSize = 12.sp)
                } else {
                    Text("待发送字节: " + ob.optInt("pending_bytes") + "   已发送记录: " +
                        (ob.optJSONArray("acked")?.length() ?: 0), fontSize = 12.sp)
                    val acked = ob.optJSONArray("acked")
                    for (i in ((acked?.length() ?: 0) - 1) downTo maxOf(0, (acked?.length() ?: 0) - 4)) {
                        val a = acked?.optJSONObject(i) ?: continue
                        Text((if (a.optBoolean("ok")) "✓ " else "✗ ") + a.optString("at") + "  " +
                            (a.optString("echo").ifEmpty { a.optString("error") }).take(60),
                            fontSize = 11.sp)
                    }
                    Text("消费者：桌面端进程（NapCat 起来后才会真正发出）", fontSize = 10.5.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }

        Card(shape = RoundedCornerShape(14.dp)) {
            Column(Modifier.padding(14.dp)) {
                Text("发一条到 QQ", fontWeight = FontWeight.Medium, fontSize = 14.sp)
                Spacer(Modifier.height(6.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    TextButton(onClick = { targetType = "private" }) {
                        Text(if (targetType == "private") "【私聊】" else "私聊")
                    }
                    TextButton(onClick = { targetType = "group" }) {
                        Text(if (targetType == "group") "【群聊】" else "群聊")
                    }
                }
                OutlinedTextField(value = targetId, onValueChange = { targetId = it.trim() },
                    label = { Text(if (targetType == "private") "对方 QQ 号" else "群号") },
                    singleLine = true, modifier = Modifier.fillMaxWidth())
                Spacer(Modifier.height(6.dp))
                OutlinedTextField(value = text, onValueChange = { text = it },
                    label = { Text("要说的话") }, modifier = Modifier.fillMaxWidth())
                Spacer(Modifier.height(8.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Button(enabled = !busy && targetId.isNotBlank() && text.isNotBlank(), onClick = {
                        scope.launch {
                            busy = true
                            val body = JSONObject().apply {
                                put("target_type", targetType)
                                put("target_id", targetId.toLongOrNull() ?: 0L)
                                put("text", text)
                            }
                            val (okk, desc) = withContext(Dispatchers.IO) { QqClient.post("/qq/queue/send", body) }
                            hint = if (okk) "已投递到队列 ✓（等桌面端发出）" else ("投递失败：" + desc.take(80))
                            if (okk) text = ""
                            busy = false
                            refresh()
                        }
                    }) { Text("发送到队列") }
                    Spacer(Modifier.weight(1f))
                    Text(hint, fontSize = 11.sp)
                }
            }
        }

        Card(shape = RoundedCornerShape(14.dp)) {
            Column(Modifier.padding(14.dp)) {
                Text("会话（点开看消息）", fontWeight = FontWeight.Medium, fontSize = 14.sp)
                Spacer(Modifier.height(6.dp))
                val ss = sessions
                if (ss == null || ss.length() == 0) {
                    Text("（没有会话文件）", fontSize = 12.sp)
                } else {
                    for (i in 0 until ss.length()) {
                        val s = ss.optJSONObject(i) ?: continue
                        Column(Modifier.fillMaxWidth().clickable {
                            val key = s.optString("key")
                            scope.launch {
                                val j = withContext(Dispatchers.IO) { QqClient.get("/qq/messages?session=" + key) }
                                val arr = j?.optJSONArray("messages")
                                val list = mutableListOf<JSONObject>()
                                for (k in 0 until (arr?.length() ?: 0)) arr?.optJSONObject(k)?.let { list.add(it) }
                                detail = key to list
                            }
                        }.padding(vertical = 6.dp)) {
                            Text(s.optString("key"), fontSize = 13.sp, fontWeight = FontWeight.Medium)
                            Text((s.optInt("messages")).toString() + " 条 · " + s.optString("last").take(50),
                                fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
        }
        Text("说明：手机不能装 NapCat（它是 PC 端 QQNT 插件）；本页只是「遥控器」，" +
            "真正收发在电脑上。QQ 历史同时也能在「记忆」页看到（pets/<角色>/memory/qq/）。",
            fontSize = 10.5.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.height(20.dp))
    }

    detail?.let { (key, list) ->
        AlertDialog(
            onDismissRequest = { detail = null },
            confirmButton = { TextButton(onClick = { detail = null }) { Text("关闭") } },
            title = { Text(key, fontSize = 15.sp) },
            text = {
                Column(Modifier.verticalScroll(rememberScrollState())) {
                    if (list.isEmpty()) Text("（没有消息）", fontSize = 12.sp)
                    for (m in list) {
                        Text((if (m.optString("role") == "user") "你: " else "她: ") +
                            m.optString("content").take(200), fontSize = 12.sp)
                        Spacer(Modifier.height(6.dp))
                    }
                }
            }
        )
    }
}
''')
print("✓ 新增 ui/QqScreen.kt")

# 抽屉入口 + 状态 + 渲染分支
s = io.open(CHATSCREEN, encoding="utf-8").read().replace("\r\n", "\n")
if "showQq" in s:
    note("ChatScreen 已有 QQ 入口", True)
else:
    a1 = "    var showSettings by remember { mutableStateOf(false) }"
    note("定位 showSettings 状态", a1 in s)
    if a1 in s:
        s = s.replace(a1, a1 + "\n    var showQq by remember { mutableStateOf(false) }", 1)
    a2 = '''                    Text("⚙  设置", fontSize = 14.5.sp, color = Color.White.copy(alpha = 0.9f),
                        modifier = Modifier.fillMaxWidth().clickable { showDrawer = false; showSettings = true }
                            .padding(horizontal = 18.dp, vertical = 12.dp))'''
    note("定位抽屉设置入口", a2 in s)
    if a2 in s:
        qq_entry = '''                    Text("💬 QQ 通道", fontSize = 14.5.sp, color = Color.White.copy(alpha = 0.9f),
                        modifier = Modifier.fillMaxWidth().clickable { showDrawer = false; showQq = true }
                            .padding(horizontal = 18.dp, vertical = 12.dp))
''' + a2
        s = s.replace(a2, qq_entry, 1)
    a3 = "        if (showSettings) {"
    note("定位设置页渲染分支", a3 in s)
    if a3 in s:
        s = s.replace(a3, '''        if (showQq) {
            // 第 3 步：手机端 QQ 通道页（遥控电脑上的 NapCat）
            QqScreen(onBack = { showQq = false })
        }
''' + a3, 1)
    io.open(CHATSCREEN, "w", encoding="utf-8", newline="\n").write(s)
    note("已加抽屉入口 + 渲染分支", "showQq" in s)

if not ok:
    print("✗ 有步骤失败 —— 回滚 ChatScreen（QqScreen 保留）")
    subprocess.run(["git", "-C", CHAT, "checkout", "--",
                    "app/src/main/java/com/aipet/murasame/ui/ChatScreen.kt"], capture_output=True)
    sys.exit(1)

print()
print("=== 编译 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o.splitlines() if x.startswith("e: ")][:8]:
    print("   " + y[:230])
if r.returncode != 0:
    sys.exit(1)


def itime():
    t = subprocess.run([ADB, "shell", "dumpsys", "package", "com.aipet.murasame"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=300).stdout
    mm = re.search(r"lastUpdateTime=([^\n]+)", t)
    return mm.group(1).strip() if mm else "?"


b = itime()
APK = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
rr = subprocess.run([ADB, "-s", DEV, "install", "-r", "--no-streaming", APK],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
print("   装:", ((rr.stdout or rr.stderr or "").strip().splitlines() or [""])[-1][:60])
print("   已装:", itime())
