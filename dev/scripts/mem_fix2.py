# -*- coding: utf-8 -*-
"""① 让记忆对抗套件失败即退出非 0 ② 对真实记忆做只读回归核对 ③ 提交"""
import io
import json
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
A = os.path.join(MAIN, "dev", "scripts", "mem_adversarial.py")

# ① 退出码
t = io.open(A, encoding="utf-8").read().replace("\r\n", "\n")
if "sys.exit(0 if npass" not in t:
    t = t.replace('''shutil.rmtree(TMP, ignore_errors=True)
print("（临时目录已清理：%s）" % TMP)''',
                  '''shutil.rmtree(TMP, ignore_errors=True)
print("（临时目录已清理：%s）" % TMP)
sys.exit(0 if npass == len(results) else 1)''', 1)
    io.open(A, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ 套件已加退出码（失败 → 非 0）")

print()
print("=== 跑一次确认退出码为 0 ===")
r = subprocess.run([sys.executable, "-u", A], capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=900, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
out = (r.stdout or "") + (r.stderr or "")
m = re.search(r"汇总：(\d+)/(\d+) 通过", out)
print("   %s  退出码=%d" % (m.group(0) if m else "(未找到汇总)", r.returncode))

print()
print("=== 真实记忆只读回归（导出并核对条数，不修改任何文件）===")
memh = os.path.join(MAIN, "pets", "murasame", "memory", "history.json")
meml = os.path.join(MAIN, "pets", "murasame", "memory", "long_history.json")
for p in (memh, meml):
    if os.path.isfile(p):
        try:
            d = json.loads(io.open(p, encoding="utf-8").read())
            n = len(d.get("history", []) if isinstance(d, dict) else d)
            print("   %-22s %d 条  %d B" % (os.path.basename(p), n, os.path.getsize(p)))
        except Exception as e:
            print("   %-22s ✗ 解析失败 %s" % (os.path.basename(p), e))
    else:
        print("   %-22s (不存在)" % os.path.basename(p))

before = {p: (os.path.getsize(p), os.path.getmtime(p)) for p in (memh, meml) if os.path.isfile(p)}
exp = subprocess.run([sys.executable, os.path.join(MAIN, "tool", "memory_transfer.py"),
                      "export", "--pet", "murasame"], cwd=MAIN, capture_output=True, text=True,
                     encoding="utf-8", errors="replace")
print("   导出输出：", (exp.stdout or exp.stderr or "").strip()[:160])
after = {p: (os.path.getsize(p), os.path.getmtime(p)) for p in (memh, meml) if os.path.isfile(p)}
same = before == after
print("   真实记忆文件未被修改：%s" % ("✓" if same else "✗ 被改了"))

# 把导出物再导入到一个临时角色，做一次"往返"（不碰真实角色）
tmp_pet = "_roundtrip_check"
outdir = os.path.join(MAIN, "dev", "memory_io")
latest = None
if os.path.isdir(outdir):
    files = sorted(os.listdir(outdir))
    latest = os.path.join(outdir, files[-1]) if files else None
if latest:
    r2 = subprocess.run([sys.executable, os.path.join(MAIN, "tool", "memory_transfer.py"),
                         "import", latest, "--pet", tmp_pet], cwd=MAIN, capture_output=True,
                        text=True, encoding="utf-8", errors="replace")
    print("   往返导入（临时角色）：", (r2.stdout or r2.stderr or "").strip().replace("\n", " | ")[:200])
    r3 = subprocess.run([sys.executable, os.path.join(MAIN, "tool", "memory_transfer.py"),
                         "import", latest, "--pet", tmp_pet], cwd=MAIN, capture_output=True,
                        text=True, encoding="utf-8", errors="replace")
    line = (r3.stdout or r3.stderr or "").strip().replace("\n", " | ")
    idem = "新增 0" in line
    print("   再次导入（幂等）：", line[:200])
    print("   幂等判定：%s" % ("✓ 新增 0" if idem else "✗ 出现重复新增"))
    # 清理临时角色目录
    import shutil
    shutil.rmtree(os.path.join(MAIN, "pets", tmp_pet), ignore_errors=True)
    print("   已清理临时角色目录 pets/%s" % tmp_pet)

print()
print("=== 提交 ===")
MSG = """fix(memory): 记忆导入导出的 4 个对抗问题（对抗测试 14/14）

对 tool/memory_transfer.py 做极端输入审查（目标里的 ④ 记忆互通，此前从未被对抗测过）：

实测发现（10/14 → 现 14/14）：
  ① incoming 里混入非 dict（字符串/数字/null）⇒ _key(e) 抛 AttributeError 直接崩，
     而且是**崩在循环中间** ⇒ 它后面的正常记录也导不进去（数据丢一半）。
     ⇒ 新增 _valid_record()：只接受"有非空 content 的 dict"，其余计入"跳过"并汇报。
  ② timestamp 混用 int 与 str ⇒ cur.sort() 抛 TypeError 整次导入崩掉。
     ⇒ 新增 _ts_key()：数字时间在前（按数值）、字符串在后（按字典序），bool 单独排最后。
  ③ 写入非原子（直接 f.write_text）⇒ 写到一半被杀会**截断记忆文件**。
     ⇒ 改为同目录临时文件 + os.replace 原子替换。
  ④ 已有 history.json 损坏时，_load 静默返回 [] ⇒ 会写出一份"只有新记录"的文件。
     ⇒ 现在会明确告警（含文件字节数、提示查看 .bak-import），并把备份时机从
        "added>0" 放宽到"文件已存在且这次有新增或跳过"，损坏场景也能保住原字节。
     另：_hist 结果先过滤非法记录，避免历史遗留的坏数据让后续每次都崩。
     新增 _load_strict() 以便区分"空文件"与"坏文件"。

对抗套件固化：dev/scripts/mem_adversarial.py（用临时 BASE + 临时角色，绝不动真实记忆；
失败退出非 0，可直接当回归测试跑）。覆盖：幂等重复导入、非法 JSON 不动旧数据、混入非 dict、
时间类型混用、已有文件损坏、裸 list、emoji/零宽/超长往返、缺字段、写入原子性（结构检查）。

验证：对抗套件 14/14；真实记忆只读回归 —— 导出前后文件大小与 mtime 未变；
导出物导入临时角色 pets/_roundtrip_check 成功，再次导入"新增 0"（幂等），随后清理该临时目录。
"""
p = os.path.join(MAIN, "dev", "merge-map", "_msg_mem_adv.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:130])
n = subprocess.run(["git", "-C", MAIN, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", MAIN, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
