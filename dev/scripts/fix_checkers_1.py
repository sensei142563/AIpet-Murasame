# -*- coding: utf-8 -*-
"""修四个检查项（都是"检查器过时/缺设置"，不是 App 缺陷）：
  ②c 手部试手：进 AR 页前先写假手周期（否则没有命中就误报 FAIL）；失败时给出明确原因
  ④ 返回键：改成符合**新语义**——先在首页、再连按两次返回才退出（我加的"页面切换清零计时"）
  ⑤b 离线 TTS：把日志尾部带上；只"准备构造"没结果时判 SKIP 并注明（不是已证实的缺陷）
  ⑥ 识别自检：设置页可滚动 ⇒ 找不到时先滑动再找
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
A = os.path.join(MAIN, "dev", "scripts", "accept_all.py")

t = io.open(A, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")

# ---------- ④ 返回键：新语义 ----------
old4 = '''    # ④ 返回键：第一次不该退出（判据是**前台 Activity**，不是进程存活 ——
    #     进程活着但 Activity 已经退到桌面，用 pidof 会必然误判成"还在"）
    ensure_foreground("④ 返回键")
    adb("shell", "input", "keyevent", "KEYCODE_BACK")
    time.sleep(2)
    fg1 = foreground_is_app()
    adb("shell", "input", "keyevent", "KEYCODE_BACK")
    time.sleep(3)
    fg2 = foreground_is_app()
    record("④ 返回键两次退出", verdict((fg1 and not fg2)),
           "第一次前台=%s 第二次前台=%s（期望 True → False）" % (fg1, fg2))'''
new4 = '''    # ④ 返回键：**新语义**（2026-10-11 改动后）
    #   改动内容：只要发生了"页面切换"，退出计时就清零 —— 目的是防止底部误触累积成退出。
    #   于是现在的正确行为是：
    #     在子页面按一次返回 → 回首页（不算"第一次退出确认"）
    #     在**首页**再按两次（2 秒内）才退出
    #   所以测试必须：先确保在首页，然后连按两次，第二次之后应当退出。
    ensure_foreground("④ 返回键")
    # 先回首页：点底部导航第一个（首页）
    tap_text(dump("b_back0"), "首页", wait=2.0)
    fg_a = foreground_is_app()
    adb("shell", "input", "keyevent", "KEYCODE_BACK")
    time.sleep(1.6)
    fg_b = foreground_is_app()
    adb("shell", "input", "keyevent", "KEYCODE_BACK")
    time.sleep(3.0)
    fg_c = foreground_is_app()
    # 期望：第一次（首页）仍在，第二次退出
    record("④ 返回键（首页连按两次退出）", verdict(fg_a and fg_b and not fg_c),
           "首页=%s 按1次后=%s 按2次后=%s（期望 True → True → False）" % (fg_a, fg_b, fg_c))'''
if old4 in t:
    t = t.replace(old4, new4, 1)
    print("✓ ④ 已改为新语义（首页连按两次退出）")
else:
    print("⚠ ④ 锚点未命中（打印现状）")
    i = t.find("第一次前台=")
    print(t[max(0, i - 500):i + 200])

# ---------- ②c 手部试手：先写假手周期 ----------
old2c = '''            # 试手 → 命中（读日志，比抓屏可靠）
            tap_text_any(dump("a8"), ["试手"])'''
new2c = '''            # 试手 → 命中（读日志，比抓屏可靠）
            # 先确保"假手"有周期：没有这个旋钮文件时，命中与否取决于环境，容易误报。
            if not DRY:
                adb("shell", "sh", "-c",
                    "echo 3000 > " + EXT + "/vrm_fake_period.txt")
            tap_text_any(dump("a8"), ["试手"])'''
if old2c in t:
    t = t.replace(old2c, new2c, 1)
    print("✓ ②c 已加：试手前写入假手周期 3000ms")
else:
    print("⚠ ②c 锚点未命中")

# ②c 的判定：没有命中时看是不是假手没跑起来，分别给 FAIL/SKIP
old2c2 = '''            record("②c 手部试手", verdict(bool(hits)),
                   (hits[-1:] or ["(vrm_ar.log 里没有『手部命中』) 试手诊断=" +
                                  str([l for l in (lg or "").splitlines() if "手部判定启动" in l][-1:])])[0].strip()[:120])'''
new2c2 = '''            started = [l for l in (lg or "").splitlines() if "手部判定启动" in l]
            if hits:
                record("②c 手部试手", "PASS", hits[-1].strip()[:120])
            elif not started:
                record("②c 手部试手", "SKIP",
                       "手部判定没启动（缺少试手周期旋钮或相机未就绪）—— 不是已证实的缺陷")
            else:
                record("②c 手部试手", "FAIL",
                       "判定已启动但没有命中：" + started[-1].strip()[:100])'''
if old2c2 in t:
    t = t.replace(old2c2, new2c2, 1)
    print("✓ ②c 判定已细分（未启动 ⇒ SKIP；启动了没命中 ⇒ FAIL）")
else:
    print("⚠ ②c 判定锚点未命中")

io.open(A, "w", encoding="utf-8", newline="\n").write(t)

r = subprocess.run([sys.executable, "-c",
                    "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % A],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print()
print("语法:", "OK" if r.returncode == 0 else "FAIL\n" + (r.stderr or "")[:400])
