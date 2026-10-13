# -*- coding: utf-8 -*-
"""修 test_config_contracts 的三项（与协作者"健壮性"提交同一批问题，我自己实现）：
  ① tool/jp_names.py 重复字典键（值相同 ⇒ 删前一份，行为不变）
  ② qq/qq_config.py 窄真值比较 → as_bool
  ③ chat.py 顶层配置读取式下标 → .get(...)
"""
import io
import os
import py_compile
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")

# 先确认 as_bool 可用
cfg = io.open(os.path.join(ROOT, "tool", "config.py"), encoding="utf-8", errors="replace").read()
print("tool/config.py 有 as_bool:", "有 ✓" if "def as_bool" in cfg else "没有 ✗")
m = re.search(r"def as_bool\([^)]*\):[\s\S]{0,600}?\n(?=\ndef |\nclass |\Z)", cfg)
if m:
    print("   as_bool 实现片段：")
    for l in m.group(0).split("\n")[:12]:
        print("      " + l.rstrip()[:110])

# ---------- ① jp_names.py ----------
print()
print("=== ① tool/jp_names.py ===")
P1 = os.path.join(ROOT, "tool", "jp_names.py")
t1 = io.open(P1, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
before = t1
t1 = t1.replace('"納得顔": "接受的表情", "納得顔2": "接受的表情 2", "納得": "接受",\n',
                '"納得顔": "接受的表情", "納得顔2": "接受的表情 2",\n', 1)
t1 = t1.replace('"目を見開き驚く1": "瞪大眼睛（惊）1", "目を見開き驚く2": "瞪大眼睛（惊）2",\n'
                '    "肩目閉じで笑顔"',
                '"肩目閉じで笑顔"', 1)
if t1 != before:
    io.open(P1, "w", encoding="utf-8", newline="\n").write(t1)
    print("   ✓ 已删掉两份重复键（'納得' / '目を見開き驚く1|2' 的前一份，值完全相同）")
else:
    print("   ✗ 未改动（检查锚点）")

# ---------- ② qq_config.py ----------
print()
print("=== ② qq/qq_config.py ===")
P2 = os.path.join(ROOT, "qq", "qq_config.py")
t2 = io.open(P2, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
pat = re.compile(r'str\(cfg\.get\("(qq_[a-z_]+)", "(\w+)"\)\)\.lower\(\) == "true"')
hits = pat.findall(t2)
print("   找到 %d 处窄真值比较：%s" % (len(hits), [h[0] for h in hits]))
if hits:
    if "from tool.config import" in t2 and "as_bool" in t2:
        print("   · 已导入 as_bool")
    else:
        t2 = t2.replace("import json", "import json\nfrom tool.config import as_bool", 1) \
            if "import json" in t2 else "from tool.config import as_bool\n" + t2
        print("   ✓ 已补 from tool.config import as_bool")
    t2 = pat.sub(lambda mm: 'as_bool(cfg.get("%s"), %s)' % (
        mm.group(1), "True" if mm.group(2) == "true" else "False"), t2)
    io.open(P2, "w", encoding="utf-8", newline="\n").write(t2)
    print("   ✓ 已改为 as_bool(...)")

# ---------- ③ chat.py ----------
print()
print("=== ③ chat.py ===")
P3 = os.path.join(ROOT, "chat.py")
t3 = io.open(P3, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
old = ('ollama_url = get_config("./config.json")["local_api"]["ollama"]\n'
       'qwen3_lora_url = get_config("./config.json")["local_api"]["qwen3_lora"]\n'
       'gpt_sovits_tts_url = get_config("./config.json")["local_api"]["gpt_sovits_tts"]')
new = ('# ⚠ 顶层配置一律用 .get(...)：读取式下标遇到缺键会直接 KeyError 崩掉\n'
       '_cfg_local = (get_config("./config.json").get("local_api") or {})\n'
       'ollama_url = _cfg_local.get("ollama", "")\n'
       'qwen3_lora_url = _cfg_local.get("qwen3_lora", "")\n'
       'gpt_sovits_tts_url = _cfg_local.get("gpt_sovits_tts", "")')
if old in t3:
    t3 = t3.replace(old, new, 1)
    print("   ✓ local_api 三项已改 .get")
else:
    print("   ⚠ local_api 锚点未命中")
if 'tts_type = get_config("./config.json")["tts_type"]' in t3:
    t3 = t3.replace('tts_type = get_config("./config.json")["tts_type"]',
                    'tts_type = get_config("./config.json").get("tts_type", "")', 1)
    print("   ✓ tts_type 已改 .get")
io.open(P3, "w", encoding="utf-8", newline="\n").write(t3)

# ---------- 验证 ----------
print()
print("=== 验证 ===")
for f in ("tool/jp_names.py", "qq/qq_config.py", "chat.py"):
    try:
        py_compile.compile(os.path.join(ROOT, f), doraise=True)
        print("   ✓ py_compile %s" % f)
    except py_compile.PyCompileError as e:
        print("   ✗ %s: %s" % (f, str(e)[:250]))

r = subprocess.run([VENV, os.path.join("tests", "test_config_contracts.py")], cwd=ROOT,
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    if "[OK]" in l or "[FAIL]" in l or "FAILED" in l or "通过" in l:
        print("   " + l.strip()[:150])
print("   退出码 =", r.returncode)
