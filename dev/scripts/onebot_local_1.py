# -*- coding: utf-8 -*-
"""方案 A 代码侧：新增本机 OneBot11 客户端（OkHttp WebSocket，无新依赖），
   并让 QQ 页/首页卡走"本机优先、电脑兜底"的双源（QqBackend）。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
CHAT = r"E:\university\order\python\pet\chatter"
UI = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui")
BOT = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/bot/chat")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

io.open(os.path.join(BOT, "OneBotLocal.kt"), "w", encoding="utf-8", newline="\n").write('''package com.aipet.murasame.bot.chat

import android.content.Context
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.concurrent.TimeUnit

/**
 * **本机** OneBot11 客户端 —— 方案 A：NapCat 跑在手机的 Termux 里，
 * App 直连 `ws://127.0.0.1:3001`，**完全不需要电脑**。
 *
 * 为什么能这么做：NapCat 是"官方 QQ 客户端 + 注入层"，官方安装器提供 Termux 脚本
 * （Debian + rootless NapCat + LinuxQQ arm64），把 OneBot11 的正向 WebSocket 挂在 3001。
 * 我们这边只当一个普通的 OneBot11 客户端即可 —— 协议维护交给 NapCat，不自研协议。
 *
 * 用 OkHttp 的 WebSocket（项目已有 okhttp 依赖，**不新增依赖**）。
 *
 * 输出约定：status/sessions/messages/outbox 全部产出**与电脑端 api.py 相同的 JSON 形状**，
 * 这样界面上层代码（QqScreen / 首页卡片）无需区分数据来自本机还是电脑。
 */
object OneBotLocal {

    /** NapCat 在手机里时就是它。 */
    @Volatile var wsUrl: String = "ws://127.0.0.1:3001"

    @Volatile private var ws: WebSocket? = null
    @Volatile var connected: Boolean = false
        private set
    @Volatile var selfId: String = ""
    @Volatile var nickname: String = ""
    @Volatile var lastError: String = ""
    @Volatile var lastEventAt: Long = 0L
        private set
    @Volatile var appCtx: Context? = null

    private val client = OkHttpClient.Builder()
        .connectTimeout(3, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .writeTimeout(5, TimeUnit.SECONDS)
        .build()

    /** key -> 消息列表（每项 role/content/timestamp）；用小容量环形，避免内存无限增长。 */
    private val sessions = LinkedHashMap<String, MutableList<JSONObject>>()
    private val lastLine = HashMap<String, String>()
    private val lastAt = HashMap<String, Long>()
    private const val MAX_PER_SESSION = 200
    private const val MAX_SESSIONS = 40
    private val lock = Any()
    private var cacheFile: File? = null

    fun log(msg: String) = runCatching {
        android.util.Log.i("OneBotLocal", msg)
        val c = appCtx ?: return@runCatching
        File(c.getExternalFilesDir(null) ?: c.filesDir, "onebot_local.log")
            .appendText(java.text.SimpleDateFormat("MM-dd HH:mm:ss", java.util.Locale.US)
                .format(java.util.Date()) + "  " + msg + "\\n")
    }.let { }

    /** 应用启动时调用：读缓存 + 尝试连接（连不上就安静地失败，不影响其它功能）。 */
    fun start(ctx: Context) {
        appCtx = ctx.applicationContext
        if (cacheFile == null) cacheFile = File(ctx.filesDir, "onebot_local.json")
        loadCache()
        connect()
    }

    fun connect() {
        if (connected || ws != null) return
        runCatching {
            ws = client.newWebSocket(Request.Builder().url(wsUrl).build(), listener)
            log("正在连接 " + wsUrl)
        }.onFailure { lastError = it.javaClass.simpleName + ": " + it.message; log("连接发起失败：$lastError") }
    }

    fun disconnect() {
        runCatching { ws?.close(1000, "bye") }
        ws = null
        connected = false
    }

    private val listener = object : WebSocketListener() {
        override fun onOpen(webSocket: WebSocket, response: Response) {
            connected = true
            lastError = ""
            log("已连上本机 NapCat：" + wsUrl)
            sendAction("get_login_info", JSONObject())
        }

        override fun onMessage(webSocket: WebSocket, text: String) {
            runCatching { handle(text) }.onFailure { log("解析事件失败：" + it.message) }
        }

        override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
            connected = false
            ws = null
            lastError = (t.message ?: t.javaClass.simpleName)
            log("连接断开：" + lastError + "（若 NapCat 未启动，属正常）")
        }

        override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
            connected = false
            ws = null
            log("连接已关闭 code=" + code)
        }
    }

    private fun sendAction(action: String, params: JSONObject) {
        val payload = JSONObject().apply {
            put("action", action)
            put("params", params)
            put("echo", action + "_" + System.currentTimeMillis())
        }
        runCatching { ws?.send(payload.toString()) }
            .onFailure { log("发送 " + action + " 失败：" + it.message) }
    }

    private fun handle(text: String) {
        val j = JSONObject(text)
        // API 回包（带 echo / status）
        if (j.has("echo") && j.has("status")) {
            if (j.optString("echo").startsWith("get_login_info")) {
                val d = j.optJSONObject("data")
                selfId = d?.optString("user_id").orEmpty()
                nickname = d?.optString("nickname").orEmpty()
                log("登录信息：$nickname($selfId)")
            }
            return
        }
        val post = j.optString("post_type")
        if (post == "meta_event") {
            if (j.optString("meta_event_type") == "lifecycle") log("NapCat 生命周期事件：" + j.optString("sub_type"))
            return
        }
        if (post != "message" && post != "message_sent") return

        val type = j.optString("message_type")
        val uid = j.optString("user_id")
        val gid = j.optString("group_id")
        val key = if (type == "group") "group_" + gid else "private_" + uid
        val myId = selfId.ifBlank { j.optString("self_id") }
        val fromMe = post == "message_sent" || (myId.isNotBlank() && uid == myId)
        val content = extractText(j)
        val ts = j.optLong("time", System.currentTimeMillis() / 1000) * 1000
        synchronized(lock) {
            val list = sessions.getOrPut(key) { mutableListOf() }
            list.add(JSONObject().apply {
                put("role", if (fromMe) "assistant" else "user")
                put("content", content)
                put("timestamp", ts)
            })
            while (list.size > MAX_PER_SESSION) list.removeAt(0)
            lastLine[key] = content.take(80)
            lastAt[key] = System.currentTimeMillis()
            while (sessions.size > MAX_SESSIONS) {
                val first = sessions.keys.firstOrNull() ?: break
                sessions.remove(first)
            }
        }
        lastEventAt = System.currentTimeMillis()
        log("收到 [" + key + "] " + content.take(40))
        saveCache()
    }

    /** OneBot11 的 message 可能是 string，也可能是 [{type,data}] 数组。 */
    private fun extractText(j: JSONObject): String {
        val msg = j.opt("message")
        if (msg is String) return msg
        if (msg is JSONArray) {
            val sb = StringBuilder()
            for (i in 0 until msg.length()) {
                val seg = msg.optJSONObject(i) ?: continue
                when (seg.optString("type")) {
                    "text" -> sb.append(seg.optJSONObject("data")?.optString("text").orEmpty())
                    "image" -> sb.append("[图片]")
                    "face" -> sb.append("[表情]")
                    "record" -> sb.append("[语音]")
                    else -> {}
                }
            }
            return sb.toString()
        }
        return j.optString("raw_message")
    }

    // ---------- 对外：与电脑端 api.py 相同的 JSON 形状 ----------

    fun status(): JSONObject = JSONObject().apply {
        put("_source", if (connected) "本机 NapCat(OneBot11 " + wsUrl + ")" else "未连接本机")
        put("qq_enabled", true)
        put("napcat_ws", wsUrl)
        put("napcat_ws_listening", connected)
        put("owner_id", selfId)
        put("nickname", nickname)
        put("memory_dir", "(本机 OneBot11 直连，无 session 文件)")
        put("sessions", synchronized(lock) { sessions.size })
        put("last_event_ms", lastEventAt)
        put("error", lastError)
        put("note", "本机 NapCat（Termux 里跑官方 NapCat）")
    }

    fun sessionsJson(): JSONObject = JSONObject().apply {
        val arr = JSONArray()
        synchronized(lock) {
            val keys = sessions.keys.sortedByDescending { lastAt[it] ?: 0L }
            for (k in keys) {
                arr.put(JSONObject().apply {
                    put("key", k)
                    put("file", "")
                    put("messages", sessions[k]?.size ?: 0)
                    put("last", lastLine[k] ?: "")
                    put("mtime", (lastAt[k] ?: 0L) / 1000)
                })
            }
        }
        put("dir", "(本机)")
        put("count", arr.length())
        put("sessions", arr)
    }

    fun messagesJson(key: String, limit: Int = 50): JSONObject = JSONObject().apply {
        val arr = JSONArray()
        synchronized(lock) {
            val list = sessions[key] ?: mutableListOf()
            val from = (list.size - limit).coerceAtLeast(0)
            for (i in from until list.size) arr.put(list[i])
        }
        put("session", key)
        put("total", synchronized(lock) { sessions[key]?.size ?: 0 })
        put("messages", arr)
    }

    fun outbox(): JSONObject = JSONObject().apply {
        put("pending_bytes", 0)
        put("bytes_total", 0)
        put("bytes_done", 0)
        put("queued", JSONArray())
        put("acked", JSONArray())
        put("worker_hint", "本机直连：无需队列（发送直接走 OneBot11）")
    }

    /** 直接发一条（本机直连，不经队列）。 */
    fun send(targetType: String, targetId: Long, text: String): Pair<Boolean, String> {
        if (!connected) return false to "本机 NapCat 未连接（Termux 里启动了吗？）"
        val params = JSONObject().apply {
            put("message_type", targetType)
            put(if (targetType == "private") "user_id" else "group_id", targetId)
            put("message", text)
            put("auto_escape", false)
        }
        return runCatching {
            val payload = JSONObject().apply {
                put("action", "send_msg"); put("params", params)
                put("echo", "send_" + System.currentTimeMillis())
            }
            ws?.send(payload.toString()) ?: return false to "连接已断开"
            log("发送到 " + targetType + ":" + targetId + " → " + text.take(30))
            true to "已发送"
        }.getOrElse { false to (it.javaClass.simpleName + ": " + it.message) }
    }

    // ---------- 缓存 ----------
    private fun saveCache() = runCatching {
        val root = JSONObject()
        synchronized(lock) {
            for ((k, v) in sessions) {
                root.put(k, JSONArray(v))
            }
        }
        cacheFile?.writeText(root.toString())
    }.let { }

    private fun loadCache() = runCatching {
        val f = cacheFile ?: return@runCatching
        if (!f.isFile) return@runCatching
        val root = JSONObject(f.readText())
        synchronized(lock) {
            for (k in root.keys()) {
                val arr = root.optJSONArray(k) ?: continue
                val list = mutableListOf<JSONObject>()
                for (i in 0 until arr.length()) arr.optJSONObject(i)?.let { list.add(it) }
                sessions[k] = list
                lastLine[k] = list.lastOrNull()?.optString("content")?.take(80) ?: ""
                lastAt[k] = list.lastOrNull()?.optLong("timestamp") ?: 0L
            }
        }
        log("已从缓存恢复 " + sessions.size + " 个本机会话")
    }.let { }
}

/**
 * QQ 数据源门面：**本机 OneBot11 优先，电脑 api.py 兜底**。
 * 两者产出同一套 JSON 形状，所以上层（QqScreen / 首页卡片）只需换调用。
 */
object QqBackend {

    fun status(): JSONObject? =
        if (OneBotLocal.connected) OneBotLocal.status() else com.aipet.murasame.ui.QqClient.get("/qq/status")

    fun sessions(): JSONObject? =
        if (OneBotLocal.connected) OneBotLocal.sessionsJson()
        else com.aipet.murasame.ui.QqClient.get("/qq/sessions")

    fun messages(key: String): JSONObject? =
        if (OneBotLocal.connected) OneBotLocal.messagesJson(key)
        else com.aipet.murasame.ui.QqClient.get("/qq/messages?session=" + key)

    fun outbox(): JSONObject? =
        if (OneBotLocal.connected) OneBotLocal.outbox()
        else com.aipet.murasame.ui.QqClient.get("/qq/outbox")

    fun send(targetType: String, targetId: Long, text: String): Pair<Boolean, String> =
        if (OneBotLocal.connected) OneBotLocal.send(targetType, targetId, text)
        else {
            val body = JSONObject().apply {
                put("target_type", targetType); put("target_id", targetId); put("text", text)
            }
            val (okk, desc) = com.aipet.murasame.ui.QqClient.post("/qq/queue/send", body)
            if (okk) true to "已投递到电脑队列（等桌面端发出）" else false to desc
        }

    fun label(): String = when {
        OneBotLocal.connected -> "本机 NapCat 已连接"
        com.aipet.murasame.ui.QqClient.base().isNotEmpty() -> "本机未连接 · 电脑 api.py"
        else -> "未连接（本机 NapCat 未启动，也没配电脑地址）"
    }
}
''')
print("✓ 新增 bot/chat/OneBotLocal.kt（本机 OneBot11 客户端 + QqBackend 双源门面）")

# ---------- QqScreen / HomeScreen 改用 QqBackend ----------
for path, label in ((os.path.join(UI, "QqScreen.kt"), "QqScreen"),
                    (os.path.join(UI, "HomeScreen.kt"), "HomeScreen")):
    t = io.open(path, encoding="utf-8").read().replace("\r\n", "\n")
    before = t
    t = t.replace('QqClient.get("/qq/status")', 'com.aipet.murasame.bot.chat.QqBackend.status()')
    t = t.replace('QqClient.get("/qq/sessions")', 'com.aipet.murasame.bot.chat.QqBackend.sessions()')
    t = t.replace('QqClient.get("/qq/messages?session=" + key)',
                  'com.aipet.murasame.bot.chat.QqBackend.messages(key)')
    t = t.replace('QqClient.get("/qq/outbox")', 'com.aipet.murasame.bot.chat.QqBackend.outbox()')
    t = t.replace("""                            val (okk, desc) = withContext(Dispatchers.IO) { QqClient.post("/qq/queue/send", body) }""",
                  """                            val (okk, desc) = withContext(Dispatchers.IO) {
                                com.aipet.murasame.bot.chat.QqBackend.send(
                                    body.optString("target_type"), body.optLong("target_id"),
                                    body.optString("text"))
                            }""")
    # 状态卡加一行"数据来源"
    t = t.replace('''                    Text("WS 地址: " + st.optString("napcat_ws"), fontSize = 11.5.sp)''',
                  '''                    Text("数据源: " + st.optString("_source", "电脑 api.py"), fontSize = 11.5.sp)
                    Text("WS 地址: " + st.optString("napcat_ws"), fontSize = 11.5.sp)''')
    if t != before:
        io.open(path, "w", encoding="utf-8", newline="\n").write(t)
        print("✓ %s 已改用 QqBackend" % label)
    else:
        print("⚠ %s 没有命中替换锚点" % label)

# ---------- 应用启动时尝试连本机 NapCat ----------
ma = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/MainActivity.kt")
t = io.open(ma, encoding="utf-8").read().replace("\r\n", "\n")
if "OneBotLocal.start" not in t:
    anchor = "        ready = true\n    }"
    if anchor in t:
        t = t.replace(anchor, """        // 方案 A：NapCat 跑在手机 Termux 里 → 启动时试着直连本机 OneBot11（连不上就静默失败）
        com.aipet.murasame.bot.chat.OneBotLocal.start(app)
        ready = true
    }""", 1)
        io.open(ma, "w", encoding="utf-8", newline="\n").write(t)
        print("✓ MainActivity 冷启动时尝试直连本机 OneBot11")
    else:
        print("⚠ MainActivity 未命中锚点")

print()
print("=== 编译 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o.splitlines() if x.startswith("e: ")][:12]:
    print("   " + y[:220])
