# -*- coding: utf-8 -*-
"""修 NetDiag：识别"移动数据"接口（rmnet/ccmni 等），给出正确提示，并且不在蜂窝网段做扫描。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
ND = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/NetDiag.kt")

t = io.open(ND, encoding="utf-8").read().replace("\r\n", "\n")

# ① 加蜂窝接口判定
if "isCellular" not in t:
    t = t.replace('''    /** 从接口名判断优先级：热点接口通常叫 ap0/swlan0；正常 Wi-Fi 是 wlan0。 */''',
'''    /**
     * 是不是"移动数据（蜂窝）"接口。
     * 真机实测：手机没连 Wi-Fi 时，ip -4 只列出 lo 与 rmnet0，地址是运营商内网
     * （例如 10.88.97.91/32）——它**不是**局域网地址，手机与电脑不可能互通。
     * 第一版把这种情况误判成"普通 Wi-Fi/路由器网络"，给了用户错误的指引。
     */
    fun isCellular(iface: String): Boolean {
        val n = iface.lowercase()
        return n.startsWith("rmnet") || n.startsWith("ccmni") || n.startsWith("pdp") ||
            n.startsWith("seth") || n.contains("rmnet")
    }

    /** 从接口名判断优先级：热点接口通常叫 ap0/swlan0；正常 Wi-Fi 是 wlan0。 */''', 1)
    print("✓ ① 已加 isCellular")
else:
    print("· 已有 isCellular")

# ② 提示与候选：蜂窝不生成候选，提示改对
old_hint = '''        val candidates = if (subnet.isEmpty()) emptyList() else {
            (1..sweepLimit).map { "$subnet.$it" }.filter { it !in selfIps }
        }
        val hint = when {
            good.isEmpty() -> "没拿到 IPv4（可能只有移动数据）—— 手机与电脑需要同一个网络"
            hot != null -> "看起来是「手机开热点、电脑连手机」：手机自己是网关，电脑通常是 " +
                subnet + ".x（扫一下就能找到）"
            else -> "看起来是普通 Wi-Fi/路由器网络：电脑通常是 " + subnet + ".x"
        }'''
new_hint = '''        // 只有移动数据（蜂窝）时：这个网段是运营商内网，手机与电脑不可能互通，
        // 而且**不应该**拿 254 个地址去扫运营商网络（既无用又冒犯）。
        val cellularOnly = good.isNotEmpty() && good.all { isCellular(it.iface) }
        val candidates = if (subnet.isEmpty() || cellularOnly) emptyList() else {
            (1..sweepLimit).map { "$subnet.$it" }.filter { it !in selfIps }
        }
        val hint = when {
            good.isEmpty() -> "没拿到任何 IPv4 —— 手机与电脑需要连到同一个网络"
            hot != null -> "看起来是「手机开热点、电脑连手机」：手机自己是网关，电脑通常是 " +
                subnet + ".x（点一下就能扫出来）"
            cellularOnly -> "本机 " + selfIps.joinToString("/") +
                " 是**移动数据**（流量），不是局域网 —— 手机和电脑这样永远连不上。" +
                "请二选一：① 手机开个人热点、电脑连这个热点（推荐，最快）；" +
                "② 手机和电脑连同一个 Wi-Fi（校园网常把设备互相隔离，可能仍不通）"
            else -> "看起来是普通 Wi-Fi/路由器网络：电脑通常是 " + subnet + ".x"
        }'''
if old_hint in t:
    t = t.replace(old_hint, new_hint, 1)
    print("✓ ② 已改：蜂窝不给候选 + 提示改为移动数据说明")
else:
    print("⚠ ② 锚点未命中")

io.open(ND, "w", encoding="utf-8", newline="\n").write(t)

# ③ 测试更新
TS = os.path.join(CHAT, "app/src/test/java/com/aipet/murasame/NetDiagTest.kt")
s = io.open(TS, encoding="utf-8").read().replace("\r\n", "\n")
old_t = '''    @Test
    fun only_mobile_data_gives_clear_hint() {
        val rep = NetDiag.classify(listOf(r("10.155.3.7", "rmnet_data0")))
        // 10.x 是运营商内网；它可用（能算同网段），但提示必须说明"需要同一个网络"
        assertFalse(rep.hotspotLikely)
        assertTrue("至少要给出可读提示", rep.hint.isNotEmpty())
    }'''
new_t = '''    @Test
    fun only_mobile_data_is_recognized_and_not_scanned() {
        // 真机实测就是这种情况：手机只有 rmnet0（10.88.97.91/32），没连 Wi-Fi。
        // 第一版把它当成"普通 Wi-Fi/路由器网络"，给了用户错误指引；这个用例锁死正确行为。
        val rep = NetDiag.classify(listOf(r("10.88.97.91", "rmnet0")))
        assertFalse(rep.hotspotLikely)
        assertTrue("必须认出是移动数据", rep.hint.contains("移动数据"))
        assertTrue("必须给出两条出路（热点 / 同一个 Wi-Fi）", rep.hint.contains("热点"))
        assertTrue("不该拿 254 个地址去扫运营商网络", rep.candidates.isEmpty())
    }

    @Test
    fun cellular_iface_names_are_detected() {
        for (n in listOf("rmnet0", "rmnet_data0", "ccmni0", "pdp0")) {
            assertTrue("$n 应被认作移动数据", NetDiag.isCellular(n))
        }
        for (n in listOf("wlan0", "ap0", "swlan0", "eth0")) {
            assertFalse("$n 不应被认作移动数据", NetDiag.isCellular(n))
        }
    }

    @Test
    fun hotspot_wins_over_cellular() {
        // 开热点时蜂窝仍在（rmnet 还在），此时必须按热点处理并给出电脑候选
        val rep = NetDiag.classify(listOf(r("10.88.97.91", "rmnet0"), r("192.168.43.1", "ap0")))
        assertTrue(rep.hotspotLikely)
        assertEquals("192.168.43", rep.subnet)
        assertTrue("热点下必须给出候选", rep.candidates.contains("192.168.43.2"))
    }'''
if old_t in s:
    s = s.replace(old_t, new_t, 1)
    io.open(TS, "w", encoding="utf-8", newline="\n").write(s)
    print("✓ ③ 测试已更新（蜂窝识别 + 不扫描 + 热点优先）")
else:
    print("⚠ ③ 测试锚点未命中")

r = subprocess.run([sys.executable, "-c",
                    "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % ND],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print("NetDiag.kt 结构检查:", "OK" if r.returncode == 0 else "见下")
