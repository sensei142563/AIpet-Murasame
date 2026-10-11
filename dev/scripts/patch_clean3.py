# -*- coding: utf-8 -*-
"""只给 remove_video_clean.py 打三个短锚点补丁，然后执行它。"""
import io
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
P = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\scripts\remove_video_clean.py"
s = io.open(P, encoding="utf-8", newline="").read()

A = "# \u2463 \u5220 Recorder/VideoCapture \u6784\u5efa\u6bb5"
B = 's = "".join(L)'
C = "# \u6821\u9a8c\uff1a\u9664 import \u884c\u5916\u4e0d\u5e94\u518d\u6709\u5f55\u50cf\u76f8\u5173\u6807\u8bc6\u7b26"
for k, label in ((A, "A"), (B, "B"), (C, "C")):
    if s.count(k) != 1:
        print("✗ 锚点 %s 命中 %d 次，放弃" % (label, s.count(k)))
        sys.exit(1)

# ① burstLeft 续拍块删除（插在 Recorder 段之前）
ins_a = '''_b = next((i for i, l in enumerate(L) if "if (burstLeft > 0) {" in l), None)
note("定位 burstLeft 续拍块", _b is not None)
if _b is not None:
    _d = 0
    _e = None
    for _k in range(_b, len(L)):
        _d += L[_k].count("{") - L[_k].count("}")
        if _d <= 0 and _k >= _b:
            _e = _k
            break
    if _e is not None:
        _s0 = _b
        while _s0 > 0 and L[_s0 - 1].strip().startswith("//"):
            _s0 -= 1
        del L[_s0:_e + 1]
        note("删除 burstLeft 续拍块", True)

'''
s = s.replace(A, ins_a + A, 1)

# ② LaunchedEffect 去掉 videoMode
ins_b = '''if "LaunchedEffect(provider, useFront, videoMode)" in s:
    s = s.replace("LaunchedEffect(provider, useFront, videoMode)", "LaunchedEffect(provider, useFront)", 1)
    note("LaunchedEffect 去掉 videoMode", True)
'''
s = s.replace(B, B + "\n" + ins_b, 1)

# ③ 快门行注释修正在断言之前
ins_c = '''s = s.replace("// \u5feb\u95e8\u884c\uff1a\u5de6\uff1d\u76f8\u518c\u7f29\u7565\u56fe \u00b7 \u4e2d\uff1d\u5feb\u95e8\uff08\u70b9\u6309\u62cd\u7167 / \u957f\u6309\u5f55\u50cf\uff09\u00b7 \u53f3\uff1d\u7ffb\u8f6c",
              "// \u5feb\u95e8\u884c\uff1a\u5de6\uff1d\u76f8\u518c\u7f29\u7565\u56fe \u00b7 \u4e2d\uff1d\u5feb\u95e8\uff08\u70b9\u6309\u62cd\u7167\uff09\u00b7 \u53f3\uff1d\u7ffb\u8f6c", 1)

'''
s = s.replace(C, ins_c + C, 1)

io.open(P, "w", encoding="utf-8", newline="").write(s)
print("✓ 三个补丁已打，开始执行\n")

r = subprocess.run([sys.executable, "-u", P], capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=1800)
out = (r.stdout or "") + (r.stderr or "")
i = out.find("=== 编译 ===")
print(out[i:i + 4000] if i >= 0 else out[-4000:])
print("rc =", r.returncode)
