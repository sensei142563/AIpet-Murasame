# -*- coding: utf-8 -*-
"""① 让 extractText 把字符串形态里的 CQ 码映射成像数组形态那样的可读文本
   ② 修我那条自相矛盾的断言 ③ 重跑 + 全量回归 + 提交"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
SRC = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/bot/chat/OneBotParse.kt")
GEN = os.path.join(MAIN, "dev", "scripts", "onebot_adv_1.py")
MAP = os.path.join(MAIN, "dev", "merge-map")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

# ---------- ① 实现 ----------
t = io.open(SRC, encoding="utf-8").read().replace("\r\n", "\n")
if "cqToReadable" in t:
    print("· 已有 CQ 映射")
else:
    t = t.replace('''    /** OneBot11 的 message 可能是 string，也可能是 [{type,data}] 数组。 */
    fun extractText(j: JSONObject): String {
        val msg = j.opt("message")
        if (msg is String) return msg''',
                  '''    /**
     * 把字符串形态 message 里的 CQ 码换成可读文本（与数组形态保持一致的观感）。
     *
     * 为什么需要：老实现/部分实现会把 message 直接给成 "[CQ:image,file=abc.jpg]你好"，
     * 原样显示的话，聊天里会出现一串 CQ 码 ✗。数组形态本来就会映射成 [图片]/[表情]，
     * 两种形态观感不一致，用户会以为坏了。
     */
    fun cqToReadable(text: String): String {
        if (!text.contains("[CQ:")) return text
        val sb = StringBuilder(text.length)
        var i = 0
        while (i < text.length) {
            val start = text.indexOf("[CQ:", i)
            if (start < 0) { sb.append(text, i, text.length); break }
            sb.append(text, i, start)
            val end = text.indexOf(']', start)
            if (end < 0) { sb.append(text, start, text.length); break }
            val body = text.substring(start + 4, end)          // 形如 image,file=x
            val cqType = body.substringBefore(',').trim()
            val paramStart = body.indexOf("file=").let { if (it >= 0) it else body.indexOf("qq=") }
            val param = if (paramStart >= 0) body.substring(paramStart).substringAfter('=') else ""
            when (cqType) {
                "image" -> sb.append("[图片]")
                "face" -> sb.append("[表情]")
                "record", "audio" -> sb.append("[语音]")
                "video" -> sb.append("[视频]")
                "at" -> sb.append("@" + param)
                "reply" -> { /* 引用段不显示 */ }
                else -> sb.append("[") .append(cqType).append("]")   // 未知段：留个可读占位
            }
            i = end + 1
        }
        return sb.toString()
    }

    /** OneBot11 的 message 可能是 string，也可能是 [{type,data}] 数组。 */
    fun extractText(j: JSONObject): String {
        val msg = j.opt("message")
        if (msg is String) return cqToReadable(msg)''', 1)
    io.open(SRC, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ OneBotParse.extractText 已接 CQ 码映射")

# ---------- ② 修我那条自相矛盾的断言（在生成脚本里改） ----------
g = io.open(GEN, encoding="utf-8").read().replace("\r\n", "\n")
old = '''        assertNull(msg("""{"post_type":"message","message_type":"private","user_id":"1"}""")
            .let { it })   // 有 user_id 但没 message ⇒ 仍应解析（content 为空）'''
new = '''        // 有 user_id 但没 message ⇒ 仍会解析成"内容为空"的一条（实现如此，也合理：
        // "空消息"要不要展示应由调用方决定；这里把现状钉住，避免以后无意改变语义）
        val empty = msg("""{"post_type":"message","message_type":"private","user_id":"1"}""")
        assertNotNull(empty)
        assertEquals("", empty!!.content)'''
if old in g:
    g = g.replace(old, new, 1)
    print("✓ 已修我那条自相矛盾的断言（原写 assertNull，注释却说「仍应解析」）")
else:
    print("⚠ 未命中那条断言（可能已改）")

# 把 CQ 用例改成断言"已映射"
g = g.replace('''        assertTrue("当前实现会原样保留 CQ 码（已知 UX 缺口）", t.contains("[CQ:image"))''',
              '''        assertTrue("CQ 码应被映射成 [图片]（此前会原样带出 CQ 码，属 UX 缺口，本轮已修）",
            t.contains("[图片]") && !t.contains("[CQ:"))
        // 其余段的映射
        val j2 = JSONObject("""{"message":"[CQ:face,id=1][CQ:record,file=a.silk]@[CQ:at,qq=123]x"}""")
        assertEquals("[表情][语音]@123x", OneBotParse.extractText(j2))''', 1)
io.open(GEN, "w", encoding="utf-8", newline="\n").write(g)

print()
print("=== 重跑对抗测试 ===")
r = subprocess.run([sys.executable, "-u", GEN], capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=1800, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
out = (r.stdout or "") + (r.stderr or "")
for l in out.split("\n"):
    if re.search(r"tests completed|BUILD|OneBotAdversarialTest:|✗|^e: ", l):
        print("   " + l.strip()[:185])
