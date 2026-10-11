# -*- coding: utf-8 -*-
"""补丁：把 remove_video_clean.py 里的绑定替换改成按行版，然后执行它。"""
import io
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
P = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\scripts\remove_video_clean.py"
s = io.open(P, encoding="utf-8", newline="").read()

old = (
    'if "preview, cap, vcap," in s:\n'
    '    s = s.replace("preview, cap, vcap,", "preview, cap,", 1)\n'
    '    note("\u7ed1\u5b9a\u6539\u56de \u9884\u89c8+\u62cd\u7167", True)'
)
new = (
    '_ls = s.splitlines(keepends=True)\n'
    '_ln = next((i for i, l in enumerate(_ls) if l.strip() == "cap, vcap,"), None)\n'
    'if _ln is not None:\n'
    '    _ind = re.match(r"(\\s*)", _ls[_ln]).group(1)\n'
    '    _ls[_ln] = _ind + "cap,\\n"\n'
    '    s = "".join(_ls)\n'
    '    note("\u7ed1\u5b9a\u6539\u56de \u9884\u89c8+\u62cd\u7167\uff08\u6309\u884c\uff09", True)\n'
    'elif "vcap" not in s:\n'
    '    note("\u7ed1\u5b9a\u6539\u56de \u9884\u89c8+\u62cd\u7167\uff08\u5df2\u65e0 vcap\uff09", True)\n'
    'else:\n'
    '    note("\u7ed1\u5b9a\u6539\u56de \u9884\u89c8+\u62cd\u7167", False)'
)
if old not in s:
    print("✗ 找不到旧片段，打印附近内容：")
    i = s.find("preview, cap, vcap")
    print(s[max(0, i - 300):i + 300])
    sys.exit(1)
s = s.replace(old, new, 1)
io.open(P, "w", encoding="utf-8", newline="").write(s)
print("✓ 已改为按行替换，开始执行\n")

r = subprocess.run([sys.executable, "-u", P], capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=1800)
out = (r.stdout or "") + (r.stderr or "")
i = out.find("=== 编译 ===")
print(out[i:i + 4000] if i >= 0 else out[-4000:])
print("rc =", r.returncode)
