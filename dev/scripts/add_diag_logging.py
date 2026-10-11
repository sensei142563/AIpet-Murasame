# -*- coding: utf-8 -*-
"""加诊断日志：
  新建 Diag.kt（写 external files/diag.log，adb 可读）
  MainActivity：init + 全局异常处理器 + onCreate/onStart/onStop/onPause/onDestroy(打印调用栈) + tab 切换埋点
  ChatScreen：进入/退出埋点
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
SRC = os.path.join(PET, "chatter", "app/src/main/java/com/aipet/murasame")
MA = os.path.join(SRC, "MainActivity.kt")
CS = os.path.join(SRC, "ui/ChatScreen.kt")
DIAG = os.path.join(SRC, "Diag.kt")

io.open(DIAG, "w", encoding="utf-8", newline="\n").write('''package com.aipet.murasame

import android.content.Context
import android.util.Log
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * 诊断日志：写 external files/diag.log（adb 可直接读，不用 root）。
 *
 * 为什么要有它：App 里到处是 runCatching，异常会被静默吞掉；而且此前**没有全局未捕获异常处理器**，
 * 一旦真的崩了什么都不留。用户在真机上遇到"切到聊天页就闪退"，日志里查不到任何痕迹，所以先把
 * 观测能力补上：异常堆栈、Activity 生命周期（销毁时连调用栈一起写，能看出是谁结束了它）。
 */
object Diag {

    private const val TAG = "AIpetDiag"
    private val fmt = SimpleDateFormat("MM-dd HH:mm:ss.SSS", Locale.US)
    @Volatile private var file: File? = null
    private val lock = Any()

    fun init(ctx: Context) {
        runCatching {
            val dir = ctx.getExternalFilesDir(null) ?: ctx.filesDir
            file = File(dir, "diag.log")
        }
    }

    fun log(tag: String, msg: String) {
        val line = "%s  [%s] %s".format(fmt.format(Date()), tag, msg)
        Log.i(TAG, line)
        val f = file ?: return
        synchronized(lock) {
            runCatching {
                f.parentFile?.mkdirs()
                f.appendText(line + "\\n")
            }
        }
    }

    /** 打印当前位置的调用栈（用来查出"是谁调用了 finish()"）。 */
    fun where(): String =
        Throwable().stackTrace.drop(2).take(14).joinToString("\\n    ") {
            "at %s.%s(%s:%d)".format(it.className, it.methodName, it.fileName, it.lineNumber)
        }

    private var installed = false

    /** 全局未捕获异常处理器：崩之前把完整堆栈写进文件，然后交回默认处理器（保持系统行为）。 */
    fun installCrashHandler() {
        if (installed) return
        installed = true
        val prev = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { t, e ->
            runCatching {
                log("FATAL", "线程 " + t.name + " 未捕获异常：" + e.javaClass.name + ": " + e.message)
                log("FATAL", "堆栈：\\n" + e.stackTraceToString())
                var c = e.cause
                var depth = 0
                while (c != null && depth < 5) {
                    log("FATAL", "cause[$depth] " + c.javaClass.name + ": " + c.message
                        + "\\n" + c.stackTraceToString())
                    c = c.cause
                    depth++
                }
            }
            prev?.uncaughtException(t, e)
        }
    }
}
''')
print("✓ 新建 Diag.kt")

# ---------- MainActivity ----------
t = io.open(MA, encoding="utf-8").read().replace("\r\n", "\n")
if "Diag.init" in t:
    print("· MainActivity 已有埋点")
else:
    t = t.replace('''    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()''',
                  '''    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Diag.init(this)
        Diag.installCrashHandler()
        Diag.log("Activity", "onCreate")
        enableEdgeToEdge()''', 1)
    t = t.replace('''    override fun onStart() {
        super.onStart()
        AppForeground.isForeground = true
    }''',
                  '''    override fun onStart() {
        super.onStart()
        Diag.log("Activity", "onStart")
        AppForeground.isForeground = true
    }''', 1)
    t = t.replace('''    override fun onStop() {
        super.onStop()''',
                  '''    override fun onStop() {
        super.onStop()
        Diag.log("Activity", "onStop")''', 1)
    # onDestroy：把调用栈一起写出来
    m = re.search(r"override fun onDestroy\(\) \{", t)
    if m:
        t = t[:m.end()] + '''
        Diag.log("Activity", "onDestroy —— 调用栈（谁结束了这个 Activity）：\\n    " + Diag.where())''' + t[m.end():]
        print("✓ onDestroy 已加调用栈记录")
    else:
        print("⚠ 没找到 onDestroy，补一个")
        t = t.replace("    override fun onStart() {",
                      '''    override fun onDestroy() {
        Diag.log("Activity", "onDestroy —— 调用栈（谁结束了这个 Activity）：\\n    " + Diag.where())
        super.onDestroy()
    }

    override fun onStart() {''', 1)
    # onPause
    if "override fun onPause()" in t:
        t = re.sub(r"(override fun onPause\(\) \{\n        super\.onPause\(\))",
                   r'\1\n        Diag.log("Activity", "onPause")', t, count=1)
    else:
        t = t.replace("    override fun onStop() {",
                      '''    override fun onPause() {
        Diag.log("Activity", "onPause")
        super.onPause()
    }

    override fun onStop() {''', 1)
    # tab 切换埋点
    t = t.replace('''                            onClick = {
                                if (tab != index) {
                                    if (tabHistory.size < 20) tabHistory.add(tab)
                                    tab = index
                                }
                            },''',
                  '''                            onClick = {
                                Diag.log("Tab", "点击 tab=$label index=$index（当前 tab=$tab）")
                                if (tab != index) {
                                    if (tabHistory.size < 20) tabHistory.add(tab)
                                    tab = index
                                }
                            },''', 1)
    # when(tab) 分支埋点
    t = t.replace("                4 -> ChatScreen()",
                  '                4 -> { Diag.log("Tab", "进入 ChatScreen"); ChatScreen() }', 1)
    io.open(MA, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ MainActivity 埋点完成")

# ---------- ChatScreen ----------
cs = io.open(CS, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
if "Diag.log(\"Chat\"" in cs:
    print("· ChatScreen 已有埋点")
else:
    m = re.search(r"fun ChatScreen\(\) \{\n", cs)
    if m:
        cs = cs[:m.end()] + '    com.aipet.murasame.Diag.log("Chat", "ChatScreen 开始组合")\n' + cs[m.end():]
    # LaunchedEffect(petId) 里加一行
    cs = cs.replace("        LaunchedEffect(petId) {",
                    '        LaunchedEffect(petId) {\n            com.aipet.murasame.Diag.log("Chat", "LaunchedEffect(petId) 进入")', 1)
    io.open(CS, "w", encoding="utf-8", newline="\n").write(cs)
    print("✓ ChatScreen 埋点完成")

print()
print("=== 语法自检（Kotlin 括号平衡粗查）===")
for p in (DIAG, MA, CS):
    s = io.open(p, encoding="utf-8", errors="replace").read()
    print("   %-24s 行数=%-5d 大括号 %d/%d %s" % (os.path.basename(p), s.count("\n") + 1,
          s.count("{"), s.count("}"), "平衡 ✓" if s.count("{") == s.count("}") else "不平衡 ✗"))
