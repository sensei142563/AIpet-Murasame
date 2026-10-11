# -*- coding: utf-8 -*-
"""给 accept_all.py 加：失败即采集诊断包（截图/日志/dump/设置/logcat + README）
   + --selftest-diag（无设备也能验文件布局）。规则遵循技能 capturing-screenshots-and-screenrecord。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
A = os.path.join(MAIN, "dev", "scripts", "accept_all.py")
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")

t = io.open(A, encoding="utf-8").read().replace("\r\n", "\n")
if "collect_diag" in t:
    print("· 已有 collect_diag")
else:
    helper = '''# ===== 诊断包采集（失败时自动跑；规则依据技能 capturing-screenshots-and-screenrecord）=====
LOGS = ["vrm.log", "vrm_ar.log", "vad.log", "live2d.log", "onebot_local.log",
        "voice.log", "tts.log"]
SETTINGS = ["silero_threshold.txt", "silero_min_silence.txt", "vrm_fake_period.txt",
            "wake_word.txt"]


def adb_bytes(*args, timeout=300):
    """二进制干净的 adb 输出（截图必须走 exec-out，不能用 shell + 重定向：
    在 Windows 上 adb shell 会给 stdout 分配 PTY，把 LF 翻成 CRLF，PNG 就坏了）。"""
    if DRY:
        return b""
    r = subprocess.run([ADB, "-s", DEV] + list(args), capture_output=True, timeout=timeout)
    return r.stdout or b""


def collect_diag(tag="fail", note=""):
    """把当前设备状态打成一个目录，便于事后复盘（不猜原因，留原始材料）。"""
    d = os.path.join(SHOTS, "diag-%s-%s" % (time.strftime("%m%d-%H%M%S"), tag))
    os.makedirs(os.path.join(d, "logs"), exist_ok=True)
    os.makedirs(os.path.join(d, "settings"), exist_ok=True)
    got = []
    if not DRY:
        # ① 截图：exec-out + -p（缺 -p 会得到裸 RGBA；用 shell 重定向会被 CRLF 破坏）
        png = adb_bytes("exec-out", "screencap", "-p")
        if png[:8] == b"\\x89PNG\\r\\n\\x1a\\n":
            io.open(os.path.join(d, "screen.png"), "wb").write(png)
            got.append("screen.png(%d B)" % len(png))
        else:
            got.append("screen.png(✗ 非 PNG 头部 %r)" % png[:8])
        # ② UI dump
        adb("shell", "uiautomator", "dump", "/sdcard/diag.xml")
        subprocess.run([ADB, "-s", DEV, "pull", "/sdcard/diag.xml",
                        os.path.join(d, "ui.xml")], capture_output=True, timeout=120)
        # ③ 应用日志
        for name in LOGS:
            body = adb("shell", "cat", "%s/%s" % (EXT, name))
            if body and body.strip() and "No such file" not in body:
                io.open(os.path.join(d, "logs", name), "w", encoding="utf-8").write(body)
                got.append("logs/" + name)
        # ④ 可调设置（真机调参用的旋钮）
        for name in SETTINGS:
            body = adb("shell", "cat", "%s/%s" % (EXT, name))
            if body and body.strip() and "No such file" not in body:
                io.open(os.path.join(d, "settings", name), "w", encoding="utf-8").write(body)
                got.append("settings/" + name)
        # ⑤ logcat（本应用相关）
        lc = adb("logcat", "-d", "-v", "threadtime", "-t", "400")
        io.open(os.path.join(d, "logcat.txt"), "w", encoding="utf-8").write(lc or "")
        # ⑥ 环境
        env = "device=%s\\napk=%s\\n" % (DEV, APK)
        env += adb("shell", "getprop", "ro.build.version.release")
        env += adb("shell", "dumpsys", "package", PKG).split("lastUpdateTime=")[-1][:40] + "\\n"
        io.open(os.path.join(d, "env.txt"), "w", encoding="utf-8").write(env)
    # ⑦ README：结论 + 原始证据清单
    lines = ["# 验收诊断包", "", "时间：%s" % time.strftime("%Y-%m-%d %H:%M:%S"),
             "标记：%s" % tag, ""]
    if note:
        lines += ["## 备注", note, ""]
    lines += ["## 本次结果"]
    for name, st, ev in RESULTS:
        lines.append("- [%s] %s — %s" % (st, name, ev))
    lines += ["", "## 采集到的材料", ", ".join(got) or "(dry-run 未采集)", "",
              "## 复跑的判定依据（判据要选不会撒谎的那个）",
              "- 3D AR 命中：`cat files/vrm_ar.log | grep 手部命中`",
              "- 假手/阈值调参：把新值写进 files/{silero_threshold.txt,vrm_fake_period.txt} 再点一次",
              "- 离线 TTS：`cat files/live2d.log | grep '\\[tts\\]'`",
              "- 返回键：`adb shell pidof %s` 两次按键之间是否还为真" % PKG]
    io.open(os.path.join(d, "README.md"), "w", encoding="utf-8").write("\\n".join(lines) + "\\n")
    print("   诊断包：%s（%d 项材料）" % (d, len(got)))
    return d


'''
    t = t.replace("def main():", helper + "def main():", 1)

    # 失败即采集：在 record() 里对 FAIL 立刻抓一张图（保留现场）
    t = t.replace('''def record(name, status, evidence=""):
    RESULTS.append((name, status, evidence))
    print("   [%-4s] %-26s %s" % (status, name, evidence[:150]))''',
                  '''def record(name, status, evidence=""):
    RESULTS.append((name, status, evidence))
    print("   [%-4s] %-26s %s" % (status, name, evidence[:150]))
    if status == "FAIL" and not DRY:
        # 失败瞬间先抓一张现场图（事后补拍通常已经不是那个画面了）
        try:
            snap = adb_bytes("exec-out", "screencap", "-p")
            if snap[:8] == b"\\x89PNG\\r\\n\\x1a\\n":
                d = os.path.join(SHOTS, "fail-shots")
                os.makedirs(d, exist_ok=True)
                io.open(os.path.join(d, "%s.png" % re.sub(r"[^0-9A-Za-z]+", "_", name)),
                        "wb").write(snap)
        except Exception:
            pass''', 1)

    # 结尾：有 FAIL 就出诊断包；--selftest-diag 只验布局
    t = t.replace('''    rep = os.path.join(SHOTS, "accept_report.json")''',
                  '''    if "--selftest-diag" in sys.argv:
        collect_diag("selftest", "无设备自检：只验证目录与 README 生成")
    elif nfail > 0:
        print()
        print("=== 有失败项 ⇒ 采集诊断包 ===")
        collect_diag("fail", "本次有 %d 项 FAIL，下面是原始材料" % nfail)
    rep = os.path.join(SHOTS, "accept_report.json")''', 1)
    io.open(A, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ accept_all.py：已加诊断包采集（含失败瞬间抓图、--selftest-diag）")

print()
print("=== 语法检查 ===")
r = subprocess.run([sys.executable, "-c",
                    "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % A],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print("   " + ("OK" if r.returncode == 0 else "FAIL\n" + (r.stderr or "")[:500]))
if r.returncode != 0:
    sys.exit(1)

print()
print("=== 自检：--selftest-diag（无设备验证目录与 README）===")
r2 = subprocess.run([sys.executable, "-u", A, "--dry-run", "--selftest-diag"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=600, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
out = (r2.stdout or "") + (r2.stderr or "")
i = out.find("=== 汇总 ===")
print(out[i:] if i > 0 else out[-1200:])
print("   EXIT:", r2.returncode)

print()
print("=== 检查生成的诊断包 ===")
sd = os.path.join(MAIN, "dev", "shots")
dirs = sorted([x for x in os.listdir(sd) if x.startswith("diag-")]) if os.path.isdir(sd) else []
if dirs:
    latest = os.path.join(sd, dirs[-1])
    print("   目录：%s" % dirs[-1])
    for base, _d, files in os.walk(latest):
        for f in files:
            p = os.path.join(base, f)
            print("      %-28s %d B" % (os.path.relpath(p, latest), os.path.getsize(p)))
    rd = os.path.join(latest, "README.md")
    if os.path.isfile(rd):
        print("   README 前 12 行：")
        for l in io.open(rd, encoding="utf-8").read().split("\n")[:12]:
            print("      " + l[:120])
else:
    print("   ✗ 没生成诊断包")

print()
print("=== 技能要求自查 ===")
src = io.open(A, encoding="utf-8").read()
for k, want in (("exec-out", True), ("screencap\", \"-p\"", True),
                ("screenrecord", False), ("kill -9", False)):
    has = k in src
    print("   %-22s %s（%s）" % (k, "存在" if has else "不存在",
                                 "符合技能要求" if has == want else "⚠ 与技能要求不符"))

MSG = """feat(accept): 失败即自动采集诊断包（截图/日志/dump/设置/logcat + README）

动机：万一我判断错了失败原因，不必再向你要一次手机；原始材料一次带全。

新增 collect_diag(tag, note)：
  · screen.png —— **adb exec-out screencap -p**（技能 capturing-screenshots-and-screenrecord 硬性要求：
    必须带 -p 才是 PNG；且 Windows 上 adb shell 会给 stdout 分配 PTY 把 LF 翻成 CRLF 而毁掉 PNG，
    所以一律走 exec-out）；会校验 PNG 魔数，不是 PNG 就如实记为「✗ 非 PNG 头部」；
  · ui.xml（uiautomator dump 后 pull）；
  · logs/ —— vrm.log、vrm_ar.log、vad.log、live2d.log、onebot_local.log、voice.log、tts.log；
  · settings/ —— silero_threshold.txt、silero_min_silence.txt、vrm_fake_period.txt、wake_word.txt
    （即上轮预置的那几个"当场可修"旋钮，带着现值）；
  · logcat.txt（-d -v threadtime -t 400）、env.txt（设备/APK 路径/系统版本/lastUpdateTime）；
  · README.md —— 本次逐项结果 + 材料清单 + **复跑判定依据**（该 grep 哪个日志、旋钮怎么改）。

触发：record() 里一旦出现 FAIL，**当场**先抓一张 fail-shots/<项名>.png（事后补拍通常已不是那个画面）；
跑完若仍有 FAIL，再出完整诊断包。另加 `--selftest-diag`：无设备时只验证目录与 README 生成。

自查（按技能列出的硬性规则）：脚本内不含 screenrecord、不含 kill -9；截图调用带 -p 且用 exec-out。
验证：语法 OK；--dry-run --selftest-diag 退出码 0，且能在 dev/shots/ 下生成 diag-*/README.md 与清单。
"""
p = os.path.join(MAIN, "dev", "merge-map", "_msg_diag.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:130])
n = subprocess.run(["git", "-C", MAIN, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", MAIN, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
