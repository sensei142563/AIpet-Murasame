# -*- coding: utf-8 -*-
"""精确修补：① 安装判据改为 lastUpdateTime >= 本地 APK 时间 + 装完自动关市场弹窗
             ② ⑧2 在重新拉起后再确认前台，不是本应用则 SKIP"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
A = os.path.join(MAIN, "dev", "scripts", "accept_all.py")

t = io.open(A, encoding="utf-8").read().replace("\r\n", "\n")

# ---------- ① 安装 ----------
old = '''    print("=== 1. 安装 ===")
    r = subprocess.run([ADB, "-s", DEV, "install", "-r", "--no-streaming", APK],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=3600) if not DRY else None
    ver = adb("shell", "dumpsys", "package", PKG)
    m = re.search(r"lastUpdateTime=([^\\n]+)", ver or "")
    record("安装", verdict((r and r.returncode == 0)),
           "lastUpdateTime=" + (m.group(1).strip() if m else "?"))'''
new = '''    print("=== 1. 安装 ===")
    r = subprocess.run([ADB, "-s", DEV, "install", "-r", "--no-streaming", APK],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=3600) if not DRY else None
    # 装完先把这个弹窗关掉：华为市场的"安装完成/建议开启增强防护"会一直压在最上面，
    # 让后面所有 UI 检查都 dump 到市场界面（要么误判、要么全被前台守卫 SKIP）。
    dismiss_market_dialog()
    ver = adb("shell", "dumpsys", "package", PKG)
    m = re.search(r"lastUpdateTime=([^\\n]+)", ver or "")
    dev_s = m.group(1).strip() if m else "?"
    # 判据：设备上的安装时间**不早于**本地 APK 的构建时间（允许 2 分钟误差）。
    # 之前看安装命令的返回码，但华为是"推送安装"，输出里未必有 Success，会误报失败。
    fresh = False
    if m:
        try:
            fresh = time.mktime(time.strptime(dev_s, "%Y-%m-%d %H:%M:%S")) >= \\
                os.path.getmtime(APK) - 120
        except Exception:
            fresh = bool(r and r.returncode == 0)
    record("安装", verdict(fresh if not DRY else True),
           "设备 lastUpdateTime=%s；本地 APK %s ⇒ %s"
           % (dev_s, time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(APK))),
              "确认为本次构建 ✓" if fresh else "⚠ 设备上可能还是旧包"))'''
if old in t:
    t = t.replace(old, new, 1)
    print("✓ ① 安装判据已改 + 装完自动关市场弹窗")
else:
    print("✗ ① 安装锚点未命中")

# ---------- ② ⑧2 前台再确认 ----------
old2 = '''    ensure_foreground("⑧2 资产种子")
    home = dump("c1")
    names = [n for n in ("丛雨", "诺瓦", "Murasame", "murasame") if n in home]
    tap_text_any(dump("c2"), ["☰"])
    drawer = dump("c3")
    has_pet_entry = any(n in drawer for n in ("丛雨", "诺瓦", "murasame", "Murasame"))
    record("⑧2 资产种子（UI 判据）", verdict(bool(names)),
           "主页可见角色=%s；抽屉含角色=%s（内部 pets/ 目录 adb 读不到，故以 UI 为准）"
           % (names or "无", has_pet_entry))'''
new2 = '''    ensure_foreground("⑧2 资产种子")
    # 重新拉起后**再确认一次**前台：今天遇到过"市场安装弹窗又抢走前台"⇒ dump 到的是市场页，
    # 结果误报 FAIL。不是我们的界面就 SKIP（既不误报失败，也不硬抢用户的屏幕）。
    if not DRY and not foreground_is_app():
        record("⑧2 资产种子（UI 判据）", "SKIP",
               "重新拉起后前台仍不是本应用（%s）—— 多半是别的窗口抢了前台，稍后重跑" % resumed_activity())
    else:
        home = dump("c1")
        names = [n for n in ("丛雨", "诺瓦", "Murasame", "murasame") if n in home]
        tap_text_any(dump("c2"), ["☰"])
        drawer = dump("c3")
        has_pet_entry = any(n in drawer for n in ("丛雨", "诺瓦", "murasame", "Murasame"))
        record("⑧2 资产种子（UI 判据）", verdict(bool(names)) if not DRY else "SKIP",
               "主页可见角色=%s；抽屉含角色=%s（内部 pets/ 目录 adb 读不到，故以 UI 为准）"
               % (names or "无", has_pet_entry))'''
if old2 in t:
    t = t.replace(old2, new2, 1)
    print("✓ ② ⑧2 已加前台再确认（不是本应用则 SKIP）")
else:
    print("✗ ② ⑧2 锚点未命中")

io.open(A, "w", encoding="utf-8", newline="\n").write(t)

r = subprocess.run([sys.executable, "-c",
                    "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % A],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print()
print("语法:", "OK" if r.returncode == 0 else "FAIL\n" + (r.stderr or "")[:400])
if r.returncode != 0:
    sys.exit(1)
print()
print("=== dry-run ===")
r2 = subprocess.run([sys.executable, "-u", A, "--dry-run"], capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=900,
                    env=dict(os.environ, PYTHONIOENCODING="utf-8"))
out = (r2.stdout or "") + (r2.stderr or "")
j = out.find("=== 汇总")
print(out[j:] if j > 0 else out[-600:])
