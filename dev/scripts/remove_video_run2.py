# -*- coding: utf-8 -*-
"""补掉最后 3 处：burstLeft 续拍块、LaunchedEffect 的 videoMode、断言顺序 → 再执行 remove_video_clean.py。"""
import io
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
P = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\scripts\remove_video_clean.py"
s = io.open(P, encoding="utf-8", newline="").read()

# ① 加删 burstLeft 续拍块（在状态删除之后）
old1 = '''# ④ 删 Recorder/VideoCapture 构建段'''
new1 = '''# ③b 删连拍续拍块（burstLeft 相关，原属连拍功能，用户已不要）
_b = next((i for i, l in enumerate(L) if "if (burstLeft > 0) {" in l), None)
note("定位 burstLeft 续拍块", _b is not None)
if _b is not None:
    _ind = re.match(r"(\\s*)", L[_b]).group(1)
    _e = None
    _d = 0
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

# ④ 删 Recorder/VideoCapture 构建段'''
assert old1 in s, "✗ ① 锚点"
s = s.replace(old1, new1, 1)

# ② LaunchedEffect 去掉 videoMode
old2 = '''s = "".join(L)
# ⑤ 绑定改回两路'''
new2 = '''s = "".join(L)
# ④b LaunchedEffect 去掉 videoMode
if "LaunchedEffect(provider, useFront, videoMode)" in s:
    s = s.replace("LaunchedEffect(provider, useFront, videoMode)", "LaunchedEffect(provider, useFront)", 1)
    note("LaunchedEffect 去掉 videoMode", True)
# ⑤ 绑定改回两路'''
assert old2 in s, "✗ ② 锚点"
s = s.replace(old2, new2, 1)

# ③ 把 ⑦ 注释修正提前到断言之前
old3 = '''# 校验：除 import 行外不应再有录像相关标识符'''
new3 = '''# ⑦ 顺手改掉快门行注释（必须在断言之前）
s = s.replace("// 快门行：左＝相册缩略图 · 中＝快门（点按拍照 / 长按录像）· 右＝翻转",
              "// 快门行：左＝相册缩略图 · 中＝快门（点按拍照）· 右＝翻转", 1)

# 校验：除 import 行外不应再有录像相关标识符'''
assert old3 in s, "✗ ③ 锚点"
s = s.replace(old3, new3, 1)

# ④ 删掉原来位置那个重复的 ⑦
old4 = '''# ⑦ 顺手改掉快门行注释
s = s.replace("// 快门行：左＝相册缩略图 · 中＝快门（点按拍照 / 长按录像）· 右＝翻转",
              "// 快门行：左＝相册缩略图 · 中＝快门（点按拍照）· 右＝翻转", 1)

if not ok:'''
new4 = '''if not ok:'''
assert old4 in s, "✗ ④ 锚点"
s = s.replace(old4, new4, 1)

io.open(P, "w", encoding="utf-8", newline="").write(s)
print("✓ 已补 3 处，开始执行\n")

r = subprocess.run([sys.executable, "-u", P], capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=1800)
out = (r.stdout or "") + (r.stderr or "")
i = out.find("=== 编译 ===")
print(out[i:i + 3500] if i >= 0 else out[-3500:])
print("rc =", r.returncode)
