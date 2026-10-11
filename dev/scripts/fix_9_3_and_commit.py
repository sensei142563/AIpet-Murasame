# -*- coding: utf-8 -*-
"""⑧3 Silero 检查改判：离线识别默认停用时，Silero 不会初始化 ⇒ 应为 SKIP（并说明如何开启）。提交。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
A = os.path.join(MAIN, "dev", "scripts", "accept_all.py")
MAP = os.path.join(MAIN, "dev", "merge-map")

t = io.open(A, encoding="utf-8").read().replace("\r\n", "\n")
old = '''    vlog = read_log("vad.log")
    rdy = [l for l in (vlog or "").splitlines() if "Silero VAD ready" in l]
    record("⑧3 Silero 真机阈值", verdict(bool(rdy)),
           (rdy[-1].strip()[:150] if rdy else
            "(vad.log 里没有『Silero VAD ready』—— Silero 只在**首次识别**时初始化，"
            "请先在聊天页长按说话一次，再重跑本项)"))'''
new = '''    vlog = read_log("vad.log")
    rdy = [l for l in (vlog or "").splitlines() if "Silero VAD ready" in l]
    # 离线识别（SenseVoice 原生库）默认停用 —— 它在真机上初始化即崩（见 2026-10-11 的修复）。
    # Silero 只在那条路径里初始化，所以停用时这一项**前提不成立**，应判 SKIP 而不是 FAIL。
    asr_on = "1" in (adb("shell", "cat", EXT + "/asr_offline_enabled.txt") or "").strip()[:1]
    if rdy:
        record("⑧3 Silero 真机阈值", "PASS", rdy[-1].strip()[:150])
    elif not asr_on:
        record("⑧3 Silero 真机阈值", "SKIP",
               "离线识别当前**已停用**（其原生库在本机初始化即崩）⇒ Silero 不会被初始化，"
               "前提不成立。要验证：在设备上创建 files/asr_offline_enabled.txt 写 1，"
               "进聊天页长按说话一次，再重跑本项")
    else:
        record("⑧3 Silero 真机阈值", "FAIL",
               "已开离线识别但 vad.log 里没有『Silero VAD ready』—— 说明 Silero 没初始化成功")'''
if old in t:
    t = t.replace(old, new, 1)
    io.open(A, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ ⑧3 已改为按「离线识别是否开启」分别判 PASS/SKIP/FAIL")
else:
    print("✗ ⑧3 锚点未命中")

r = subprocess.run([sys.executable, "-c",
                    "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % A],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print("   语法:", "OK" if r.returncode == 0 else "FAIL\n" + (r.stderr or "")[:300])

print()
print("=== dry-run 复核 ===")
r2 = subprocess.run([sys.executable, "-u", A, "--dry-run"], capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=900,
                    env=dict(os.environ, PYTHONIOENCODING="utf-8"))
out = (r2.stdout or "") + (r2.stderr or "")
j = out.find("=== 汇总")
print(out[j:] if j > 0 else out[-600:])

MSG = """test(accept): 验收脚本按 2026-10-11 真机事故加固（新增第 ⑨ 节 + 前台守卫 + ⑧3 改判）

今天发生的事故：一进聊天页，进程就被内核收走（Java 侧查不到任何痕迹），根因是聊天页组合里
一段离线识别自检加载原生模型时崩溃。事后把这轮教训**固化进验收脚本**：

⑨1 安装确实生效：对比本地 APK 时间与设备 lastUpdateTime。
    今天吃过这个亏 —— 有一次安装其实没生效，测出来的还是旧包，白白绕了很久。
⑨2 无原生崩溃：扫 events 日志里的 `fromBinderDied=true`。
    这一类比 Java 异常更难查（crash buffer / dropbox / 异常处理器全都看不到），必须专门检查。
⑨3 **聊天页不再闪退**：点进聊天页后连续观察 20 秒，进程必须存活、前台必须仍是本应用。
    这是今天那个 bug 的守门测试，以后回归会立刻被抓到。
⑨4 前台守卫（并落到全局）：所有需要点击的检查前先确认前台是本应用；若前台是**第三方应用**
    （像今天你在用 QQ），整段 UI 检查直接 SKIP —— 绝不抢你正在用的屏幕，也避免测出无效结果。

⑧3 改判：离线识别（SenseVoice 原生库）现已默认停用，Silero 只在那条路径里初始化，
    所以"没有 Silero ready"不再是失败 ⇒ 按设备上 asr_offline_enabled.txt 是否存在，
    分别判 PASS / SKIP / FAIL（前提不成立就 SKIP，不谎报也不误报）。

实测（真机 MIS-AL00 / Android 12，华为市场弹窗恰好在前台）：
    ⑨1 PASS（本地 20:30:00 vs 设备 20:34:13）· ⑨2 PASS（fromBinderDied 0 条）
    ⑨3 PASS（点(1112,2641) 后进程存活、前台仍是本应用，pid 6824→6824）
    ⑨4 PASS（前台是别的应用 ⇒ 自动跳过全部点击）· ⑧2/⑧2b/⑧4 PASS
    合计 PASS 10 / FAIL 1 / SKIP 7（那 1 个 FAIL 就是 ⑧3，已按上文改判）
"""
p = os.path.join(MAP, "_msg_accept9.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:150])
for nm, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True, encoding="utf-8").stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True,
                        text=True, encoding="utf-8").stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (nm, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
