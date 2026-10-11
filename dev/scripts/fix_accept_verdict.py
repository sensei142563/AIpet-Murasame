# -*- coding: utf-8 -*-
"""修 accept_all.py 的诚实性：dry-run 下未真实验证的项应为 SKIP 而不是 PASS。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
P = os.path.join(MAIN, "dev", "scripts", "accept_all.py")

t = io.open(P, encoding="utf-8").read().replace("\r\n", "\n")
if "def verdict(" in t:
    print("· 已有 verdict")
else:
    t = t.replace('''def record(name, status, evidence=""):''',
                  '''def verdict(cond, dry_note="(dry-run 未验证)"):
    """dry-run 下不谎报 PASS：一律 SKIP，避免"没验证却显示通过"。"""
    if DRY:
        return "SKIP"
    return "PASS" if cond else "FAIL"


def record(name, status, evidence=""):''', 1)
    # 把形如  "PASS" if (DRY or X) else "FAIL"  统一替换为 verdict(X)
    t = re.sub(r'"PASS" if \(DRY or (\(?[^)\n]*?\)?)\) else "FAIL"', lambda m: "verdict(%s)" % m.group(1), t)
    t = re.sub(r'"PASS" if \(DRY or ([^\n]+?)\) else "FAIL"', lambda m: "verdict(%s)" % m.group(1), t)
    io.open(P, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ 已加 verdict() 并替换判定")

# 特例：安装那一条用的是 (DRY or (r and r.returncode == 0))
t = io.open(P, encoding="utf-8").read().replace("\r\n", "\n")
t = t.replace('"PASS" if (DRY or (r and r.returncode == 0)) else "FAIL"',
              'verdict(r is not None and r.returncode == 0)')
t = t.replace('record("TTS 模型", "PASS" if not DRY else "SKIP", "已推送/已存在")',
              'record("TTS 模型", verdict(True), "已推送/已存在")')
io.open(P, "w", encoding="utf-8", newline="\n").write(t)

print()
print("=== 复核：还有没有 DRY 直接判 PASS 的地方 ===")
bad = [l.strip() for l in io.open(P, encoding="utf-8").read().split("\n")
       if "DRY" in l and '"PASS"' in l]
print("   " + ("无 ✓" if not bad else "\n   ".join(bad[:6])))

print()
print("=== 再跑 dry-run ===")
r = subprocess.run([sys.executable, "-u", P, "--dry-run"], capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=600)
out = (r.stdout or "") + (r.stderr or "")
# 只看汇总段
i = out.find("=== 汇总 ===")
print("\n".join("   " + l for l in out[i:].splitlines()[:18]) if i > 0 else out[-1500:])
print("   退出码:", r.returncode)
print()
print("判定:", "✓ dry-run 现在如实报 SKIP（不再把未验证项说成通过）" if r.returncode == 0 else "✗ 有问题")

print()
print("=== 提交 ===")
MSG = """test(accept): 一键真机验收脚本 accept_all.py（含 --dry-run 自检）

把"等你插线后要验的 10 项"固化成一条命令，避免靠临场记忆：
    python dev/scripts/accept_all.py            # 真跑
    python dev/scripts/accept_all.py --dry-run  # 无手机时自检脚本本身

覆盖：安装（记录 lastUpdateTime）/ 推送离线 TTS 模型与测试 VRM（已有则跳过）/
① 3D 页加载（读 files/vrm.log 找 title=VRM_OK）/
② 3D AR（读 files/vrm_ar.log 的"相机已绑定"与"相机 FOV"行 → 音量下键拍照看 shoot 日志 →
   点「试手」后在 dump 里找命中提示 → 点「干净」后确认控件确实消失）/
③ 首页 QQ chatter 卡（dump 文本）/
④ 返回键：**第一次按应存活、第二次才退出**（用 pidof 实测存活状态）/
⑤ 设置页「只回应呼唤」开关存在 + 点「离线音色」后读 live2d.log 的 [tts] 行 /
⑥ 点「识别自检」后读 vad.log 的 Silero 行 /
⑦ Termux+NapCat 需人工（给出文档位置与要看的日志）。
每项输出 PASS/FAIL/SKIP + 原始证据，最后写 dev/shots/accept_report.json。

诚实性修正（写脚本时自己发现的）：第一版在 --dry-run 下把"没验证的项"也报成 PASS
（比如"首页 QQ 卡 PASS"却附证据"未看到"）—— 这会误导。已改为 verdict() 统一判定：
**dry-run 一律 SKIP**，只有真机跑出来的结果才会是 PASS/FAIL。
"""
p = os.path.join(MAIN, "dev", "merge-map", "_msg_accept.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:130])
n = subprocess.run(["git", "-C", MAIN, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True).stdout.strip()
st = subprocess.run(["git", "-C", MAIN, "status", "--porcelain"],
                    capture_output=True, text=True).stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
