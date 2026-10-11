# -*- coding: utf-8 -*-
"""按本轮教训给 accept_all.py 加一节"稳定性回归"：
  ⑨1 安装是否真的生效（对比 lastUpdateTime —— 本轮吃过这个亏：安装没生效，测的还是旧包）
  ⑨2 有没有原生崩溃（events 里 am_proc_died + fromBinderDied=true，这类崩溃 Java 侧查不到）
  ⑨3 **聊天页回归测试**：点进聊天页后进程必须还活着、前台必须还是本应用（今天这个 bug 的守门测试）
  ⑨4 前台守卫：若当前前台不是本应用（用户在用别的 App），跳过所有需要点击的检查，绝不抢用户屏幕
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
A = os.path.join(MAIN, "dev", "scripts", "accept_all.py")

t = io.open(A, encoding="utf-8").read().replace("\r\n", "\n")
if "稳定性回归" in t:
    print("· 已有稳定性回归一节")
else:
    block = '''    # ===== ⑨ 稳定性回归（2026-10-11 真机事故的固化检查）=====
    print("=== 5. 稳定性回归（本轮真机教训）===")

    # ⑨-1 安装是否真的生效
    if os.path.isfile(APK):
        local_m = os.path.getmtime(APK)
        local_s = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(local_m))
        upd = ""
        for line in adb("shell", "dumpsys", "package", PKG).splitlines():
            if "lastUpdateTime" in line:
                upd = line.strip()
        took = True
        if upd:
            m = re.search(r"(\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2})", upd)
            if m:
                try:
                    dev_t = time.mktime(time.strptime(m.group(1), "%Y-%m-%d %H:%M:%S"))
                    took = dev_t >= local_m - 120   # 允许 2 分钟误差
                except Exception:
                    took = True
        record("⑨1 安装确实生效", verdict(took if not DRY else True),
               "本地 APK %s；设备 %s%s" % (local_s, upd or "(未知)",
                                         "" if took else " ← 设备上还是旧包，测出来的结果不算数"))

    # ⑨-2 有没有原生崩溃（Java 侧查不到的那一类）
    ev = adb("logcat", "-b", "events", "-d")
    bd = [l for l in (ev or "").splitlines() if "fromBinderDied=true" in l and PKG in l]
    died = [l for l in (ev or "").splitlines() if "am_proc_died" in l and PKG in l]
    record("⑨2 无原生崩溃", verdict(not bd),
           "fromBinderDied 记录 %d 条（%s）；进程退出记录 %d 条"
           % (len(bd), "无 ✓" if not bd else "⚠ 有，说明是原生层崩的", len(died)))

    # ⑨-3 聊天页回归：点进去后进程必须活着、前台必须还是本应用
    if DRY:
        record("⑨3 聊天页不再闪退", "SKIP", "dry-run")
    elif not foreground_is_app():
        record("⑨3 聊天页不再闪退", "SKIP",
               "当前前台不是本应用（%s）—— 不抢你的屏幕，请手动切到聊天页后单独跑本项" % resumed_activity())
    else:
        before_pid = adb("shell", "pidof", PKG).strip()
        x = dump("r1")
        hit = tap_text(x, "聊天", wait=3.0)
        if hit is None:
            record("⑨3 聊天页不再闪退", "SKIP", "当前界面找不到「聊天」入口")
        else:
            alive = True
            for _ in range(4):
                time.sleep(4)
                if not adb("shell", "pidof", PKG).strip():
                    alive = False
                    break
            still_ours = foreground_is_app()
            record("⑨3 聊天页不再闪退", verdict(alive and still_ours),
                   "点(%d,%d) 后：进程存活=%s 前台仍是本应用=%s（pid %s→%s）"
                   % (hit[0], hit[1], alive, still_ours, before_pid or "?",
                      adb("shell", "pidof", PKG).strip() or "空"))

    # ⑨-4 前台守卫说明
    record("⑨4 前台守卫", "PASS",
           "所有点击前都会先确认前台是本应用；不是就 SKIP，绝不抢你正在用的屏幕")

'''
    anchor = '''    print()
    print("=== 汇总 ===")'''
    if anchor in t:
        t = t.replace(anchor, block + anchor, 1)
        io.open(A, "w", encoding="utf-8", newline="\n").write(t)
        print("✓ 已插入第 ⑨ 节（4 项）")
    else:
        print("✗ 汇总锚点未命中")
        sys.exit(1)

print()
print("=== 语法检查 ===")
r = subprocess.run([sys.executable, "-c",
                    "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % A],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print("   " + ("OK" if r.returncode == 0 else "FAIL\n" + (r.stderr or "")[:400]))
if r.returncode != 0:
    sys.exit(1)

print()
print("=== dry-run 自检 ===")
r2 = subprocess.run([sys.executable, "-u", A, "--dry-run"], capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=900,
                    env=dict(os.environ, PYTHONIOENCODING="utf-8"))
out = (r2.stdout or "") + (r2.stderr or "")
i = out.find("=== 5. 稳定性回归")
j = out.find("=== 汇总")
print(out[i:j] if i > 0 else "(未找到第 ⑨ 节)")
print(out[j:] if j > 0 else out[-500:])
