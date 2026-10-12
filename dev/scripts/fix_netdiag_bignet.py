# -*- coding: utf-8 -*-
"""补 /24 以上大网的盲区：Addr4 带上 prefix，classify 在 prefix<24 时明确提示
"网络很大、自动扫描可能找不到，请用电脑端工具看地址再手填"；同时保留 /24 扫描（有界）。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
ND = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/NetDiag.kt")
TS = os.path.join(CHAT, "app/src/test/java/com/aipet/murasame/NetDiagTest.kt")
NE = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui/NetEnv.kt")

t = io.open(ND, encoding="utf-8").read().replace("\r\n", "\n")
t = t.replace("data class Addr4(val iface: String, val ip: String)",
              "data class Addr4(val iface: String, val ip: String, val prefix: Int = 24)", 1)
if "bigNet" not in t:
    t = t.replace('''        val hint = when {''',
'''        // 大网（前缀小于 /24，例如校园网 /17、/16）时，电脑很可能不在本机的那个 /24 里，
        // 自动扫描（只扫 /24，有界）就可能找不到 —— 这时要**明说**，并给出手填兜底。
        val bigNet = good.firstOrNull()?.let { it.prefix in 1..23 } ?: false
        val hint = when {''', 1)
    t = t.replace('''            else -> "看起来是普通 Wi-Fi/路由器网络：电脑通常是 " + subnet + ".x"
        }''',
'''            bigNet -> "本机 " + selfIps.joinToString("/") + "（网络很大，/" +
                (good.firstOrNull()?.prefix ?: 24) + "）：电脑可能不在 " + subnet +
                ".x 这一段里，自动扫描未必找得到。" +
                "请在电脑上运行 python tool/net_selfcheck.py 看它的地址，再手填到下面两处"
            else -> "看起来是普通 Wi-Fi/路由器网络：电脑通常是 " + subnet + ".x"
        }''', 1)
    io.open(ND, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ NetDiag 已支持大网提示")
else:
    print("· 已有大网提示")

# NetEnv 采集时带上前缀
e = io.open(NE, encoding="utf-8").read().replace("\r\n", "\n")
if "interfaceAddresses" not in e:
    e = e.replace('''                for (a in nif.inetAddresses) {
                    if (a is Inet4Address && !a.isLoopbackAddress) {
                        out += NetDiag.Addr4(nif.name ?: "?", a.hostAddress ?: continue)
                    }
                }''',
'''                // 用 interfaceAddresses 才能拿到前缀长度（判断"网是不是很大"要靠它）
                for (ia in nif.interfaceAddresses) {
                    val a = ia.address
                    if (a is Inet4Address && !a.isLoopbackAddress) {
                        out += NetDiag.Addr4(nif.name ?: "?", a.hostAddress ?: continue,
                            ia.networkPrefixLength.toInt())
                    }
                }''', 1)
    io.open(NE, "w", encoding="utf-8", newline="\n").write(e)
    print("✓ NetEnv 已改为带前缀采集")
else:
    print("· NetEnv 已带前缀")

# 测试
s = io.open(TS, encoding="utf-8").read().replace("\r\n", "\n")
if "big_network_warns_about_scan" not in s:
    s = s.replace('''    @Test
    fun duplicate_ips_are_deduped() {''',
'''    @Test
    fun big_network_warns_about_scan() {
        // 实测场景：电脑在校园网 172.25.195.72/17，手机若也连上这个大网，
        // 本机 /24 与电脑所在 /24 可能不同 ⇒ 必须提示"自动扫描未必找得到，请手填"。
        val rep = NetDiag.classify(listOf(NetDiag.Addr4("wlan0", "172.25.196.30", 17)))
        assertFalse(rep.hotspotLikely)
        assertTrue("大网必须给出提示", rep.hint.contains("网络很大"))
        assertTrue("大网提示里要指向电脑端自查工具", rep.hint.contains("net_selfcheck"))
        // 依然给出有界的 /24 候选（不因为网大就去扫 3 万个地址）
        assertEquals(253, rep.candidates.size)
        assertTrue(rep.candidates.contains("172.25.196.2"))
    }

    @Test
    fun normal_24_network_has_no_big_net_warning() {
        val rep = NetDiag.classify(listOf(NetDiag.Addr4("wlan0", "192.168.1.23", 24)))
        assertFalse(rep.hint.contains("网络很大"))
    }

    @Test
    fun duplicate_ips_are_deduped() {''', 1)
    io.open(TS, "w", encoding="utf-8", newline="\n").write(s)
    print("✓ 测试已加（大网提示 + /24 不误报）")
else:
    print("· 测试已有")
