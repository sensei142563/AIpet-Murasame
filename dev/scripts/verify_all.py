# -*- coding: utf-8 -*-
"""离线回归闸门：一条命令跑完全部离线验证，打印一张总表；任一失败即退出非 0。

用法：python dev/scripts/verify_all.py [--quick]
  --quick  跳过 Kotlin 单测（只想快速确认 Python 侧）
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
PY = sys.executable
ROWS = []


def run(cmd, cwd=None, timeout=3600, env_extra=None):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    if env_extra:
        env.update(env_extra)
    t0 = time.time()
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout, env=env)
    return r.returncode, ((r.stdout or "") + (r.stderr or "")), time.time() - t0


def row(name, ok, detail, secs=None):
    ROWS.append((name, ok, detail, secs))
    print("   [%s] %-34s %s" % ("PASS" if ok else "FAIL", name, detail[:110]))


print("=" * 78)
print("离线回归闸门（不需要手机）   %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
print("=" * 78)

# ---------- ① 记忆导入导出（真实数据往返必须无损）----------
print("\n① 记忆导入导出（真实记忆往返）")
rc, out, secs = run([PY, "-u", os.path.join(MAIN, "dev", "scripts", "mem_adversarial.py")])
m = re.search(r"汇总：(\d+)/(\d+) 通过", out)
row("mem_adversarial（19 项）", rc == 0 and bool(m),
    (m.group(0) if m else "未找到汇总"), secs)
if rc != 0:
    print("     失败详情：\n" + "\n".join("       " + l for l in out.splitlines()[-14:]))

# 真实数据无损：导出 → 导入临时角色 → 比条数 → 清理
mem = os.path.join(MAIN, "pets", "murasame", "memory", "history.json")
if os.path.isfile(mem):
    n_src = len(json.loads(io.open(mem, encoding="utf-8").read()).get("history", []))
    rc2, out2, secs2 = run([PY, os.path.join(MAIN, "tool", "memory_transfer.py"),
                            "export", "--pet", "murasame"], cwd=MAIN)
    outdir = os.path.join(MAIN, "dev", "memory_io")
    latest = os.path.join(outdir, sorted(os.listdir(outdir))[-1]) if os.path.isdir(outdir) else None
    n_rt = None
    if latest:
        run([PY, os.path.join(MAIN, "tool", "memory_transfer.py"), "import", latest,
             "--pet", "_verify_rt"], cwd=MAIN)
        rt = os.path.join(MAIN, "pets", "_verify_rt", "memory", "history.json")
        if os.path.isfile(rt):
            n_rt = len(json.loads(io.open(rt, encoding="utf-8").read()).get("history", []))
        shutil.rmtree(os.path.join(MAIN, "pets", "_verify_rt"), ignore_errors=True)
    ok = (n_rt == n_src)
    row("真实记忆往返无损", ok, "原始 %s 条 → 往返后 %s 条" % (n_src, n_rt), secs2)

# ---------- ② QQ 发送队列（并发零丢失）----------
print("\n② QQ 发送队列")
rc, out, secs = run([PY, "-u", os.path.join(MAIN, "dev", "scripts", "qq_outbox_adversarial.py")])
m = re.search(r"汇总：(\d+)/(\d+) 通过", out)
row("qq_outbox_adversarial（18 项）", rc == 0 and bool(m), (m.group(0) if m else "未找到汇总"), secs)
if rc != 0:
    print("     失败详情：\n" + "\n".join("       " + l for l in out.splitlines()[-14:]))

# ---------- ③ 重型任务闸门 ----------
print("\n③ 重型任务闸门")
rc, out, secs = run([PY, "-u", os.path.join(MAIN, "dev", "scripts", "test_heavy_gate.py")])
row("test_heavy_gate", rc == 0, ("互斥与超时行为正确" if rc == 0 else out.strip().splitlines()[-1:][0][:100]), secs)

# ---------- ④ 能量法 VAD ----------
print("\n④ 能量法 VAD")
rc, out, secs = run([PY, "-u", os.path.join(MAIN, "dev", "scripts", "test_vad.py")])
row("test_vad（7 场景）", rc == 0, ("与 Kotlin 版同信号同期望" if rc == 0 else "见上方输出"), secs)

# ---------- ⑤ Silero 真模型（用她的真实语音 + 合成负例）----------
print("\n⑤ Silero 真模型（PC 侧，onnxruntime）")
try:
    sys.path.insert(0, MAIN)
    from tool import silero_vad
    voice_dir = os.path.join(CHAT, "app/src/main/assets/voice/murasame")
    wavs = sorted(f for f in os.listdir(voice_dir) if f.endswith(".wav"))[:4] if os.path.isdir(voice_dir) else []
    speech_ok = 0
    peaks = []
    for w in wavs:
        r = silero_vad.analyze_file(os.path.join(voice_dir, w))
        if r["is_speech"]:
            speech_ok += 1
            peaks.append(r.get("peak", 0))
    shots = os.path.join(MAIN, "dev", "shots")
    neg = [("vad_silence.wav", "静音"), ("vad_loudtone.wav", "响亮纯音"),
           ("vad_noise.wav", "方波噪声"), ("gate_probe.wav", "旧探针嗡嗡声")]
    neg_ok = 0
    neg_seen = 0
    for f, _ in neg:
        p = os.path.join(shots, f)
        if os.path.isfile(p):
            neg_seen += 1
            if not silero_vad.analyze_file(p)["is_speech"]:
                neg_ok += 1
    ok = (speech_ok == len(wavs) and len(wavs) > 0 and neg_ok == neg_seen)
    row("Silero：真实语音全命中 + 负例全拒绝", ok,
        "语音 %d/%d（峰值 %.2f~%.2f）· 负例拒绝 %d/%d"
        % (speech_ok, len(wavs), min(peaks) if peaks else 0, max(peaks) if peaks else 0,
           neg_ok, neg_seen))
except Exception as e:
    row("Silero 真模型", False, "%s: %s" % (type(e).__name__, e))

# ---------- ⑥ Kotlin 单测（122 个用例）----------
if "--quick" not in sys.argv:
    print("\n⑥ Kotlin 单测（手机仓）")
    env = dict(os.environ)
    env["JAVA_HOME"] = r"E:\Android Studio\jbr"
    env["PATH"] = r"E:\Android Studio\jbr\bin;" + env.get("PATH", "")
    rc, out, secs = run([os.path.join(CHAT, "gradlew.bat"), ":app:testDebugUnitTest",
                         "--console=plain"], cwd=CHAT, timeout=7200, env_extra=env)
    d = os.path.join(CHAT, "app/build/test-results/testDebugUnitTest")
    tot = fail = 0
    classes = []
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if not f.endswith(".xml"):
                continue
            x = io.open(os.path.join(d, f), encoding="utf-8", errors="replace").read()
            mm = re.search(r'tests="(\d+)" skipped="\d+" failures="(\d+)" errors="(\d+)"', x)
            if mm:
                t = int(mm.group(1)); fl = int(mm.group(2)) + int(mm.group(3))
                tot += t; fail += fl
                classes.append("%s=%d%s" % (f.replace("TEST-com.aipet.murasame.", "").replace(".xml", ""),
                                            t, "" if fl == 0 else "(%d失败)" % fl))
    row("Kotlin 单测（%d 个类）" % len(classes), rc == 0 and fail == 0 and tot > 0,
        "%d 个用例，失败 %d" % (tot, fail), secs)
    if rc != 0 or fail:
        print("     " + " ".join(classes))

# ---------- 总表 ----------
print("\n" + "=" * 78)
print("%-36s %-6s %-10s %s" % ("检查项", "结果", "耗时", "关键数字"))
print("-" * 78)
npass = 0
for name, ok, detail, secs in ROWS:
    if ok:
        npass += 1
    print("%-36s %-6s %-10s %s" % (name[:35], "PASS" if ok else "FAIL",
                                   ("%.1fs" % secs) if secs else "-", detail[:70]))
print("-" * 78)
print("合计 %d/%d 通过" % (npass, len(ROWS)))
print("=" * 78)
sys.exit(0 if npass == len(ROWS) else 1)
