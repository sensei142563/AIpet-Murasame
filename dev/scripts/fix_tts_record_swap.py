# -*- coding: utf-8 -*-
"""修 run.py 记录 data/tts_model.json 时把 gpt/sovits 标签写反的 bug。

根因：按下标取参数 —— `_extra = ["-s", <sovits>, "-g", <gpt>]`，
      却写 `"gpt": _extra[1]`（其实是 sovits）、`"sovits": _extra[3]`（其实是 gpt）。
后果：tool/tts_service.py 拿这个文件的 gpt/sovits 与"当前应该加载的"比对，
      want 侧标签正确、have 侧标签互换 ⇒ **永远判为不一致** ⇒ 每次预载都杀掉重启语音服务
      （重新加载模型 1~2 分钟），也解释了那个 GPT-SoVITS 终端为何反复出现。

修法：改成按 `-s` / `-g` **标志**取值，不再依赖参数顺序（以后顺序变了也不会错）。
并加一条源码守卫，防止有人改回下标写法。
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
RUN = os.path.join(ROOT, "run.py")

t = io.open(RUN, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")

# ---------- ① 插入按标志取值的助手 ----------
HELPER = '''

def _flag_arg(extra: list, flag: str) -> str:
    """从 ["-s", <soVITS>, "-g", <GPT>] 里按**标志**取参数的文件名。

    ⚠ 不要改成按下标取（`_extra[1]` / `_extra[3]`）——曾经就是这么写的，
      结果把 gpt / sovits 的标签写反了：记录文件 data/tts_model.json 里
      gpt 存的是 SoVITS、sovits 存的是 GPT。而 tool/tts_service.py 正是拿这两个字段
      判断"要不要重启语音服务"，标签一互换就**永远判为不一致**，
      于是每次预载都杀一次服务、重载模型（1~2 分钟），表现为那个 TTS 终端反复出现。
    """
    try:
        i = list(extra).index(flag)
        return os.path.basename(str(list(extra)[i + 1]))
    except Exception:
        return ""

'''
if "_flag_arg" not in t:
    # 插在 _console_flags 之前（同一区域的工具函数）
    anchor = "def _console_flags("
    if anchor in t:
        t = t.replace(anchor, HELPER.strip() + "\n\n\n" + anchor, 1)
        print("✓ ① 已加 _flag_arg（按标志取参数）")
    else:
        print("✗ ① 锚点未命中 _console_flags")
else:
    print("· ① 已有 _flag_arg")

# ---------- ② 改记录处 ----------
OLD = '''                    "gpt": os.path.basename(_extra[1]) if len(_extra) > 1 else "",
                    "sovits": os.path.basename(_extra[3]) if len(_extra) > 3 else "",'''
NEW = '''                    "gpt": _flag_arg(_extra, "-g"),
                    "sovits": _flag_arg(_extra, "-s"),'''
if OLD in t:
    t = t.replace(OLD, NEW, 1)
    print("✓ ② 已改为按 -g / -s 标志取值（不再按下标）")
else:
    print("✗ ② 锚点未命中（记录处）")

io.open(RUN, "w", encoding="utf-8", newline="\n").write(t)

print()
print("=== 复核 run.py 相关行 ===")
for i, l in enumerate(io.open(RUN, encoding="utf-8", errors="replace").read().split("\n"), 1):
    if "_flag_arg" in l or ('"gpt"' in l and "basename" in l) or ('"sovits"' in l and "basename" in l):
        print("   %5d| %s" % (i, l.strip()[:112]))

# ---------- ③ 直接验证助手行为（把函数抠出来跑） ----------
print()
print("=== ③ 用真实 _extra 验证（抠函数跑，不启动 TTS）===")
ns = {"os": os}
src = io.open(RUN, encoding="utf-8", errors="replace").read()
m = re.search(r"def _flag_arg\(extra: list, flag: str\) -> str:[\s\S]*?\n\n\n", src)
if m:
    exec(compile(m.group(0), "run.py:_flag_arg", "exec"), ns)
    f = ns["_flag_arg"]
    extra = ["-s", r"E:\...\SoVITS_weights/murasame-sovits.pth",
             "-g", r"E:\...\GPT_weights/murasame-gpt.ckpt"]
    print("   _extra =", extra)
    print("   gpt    =", f(extra, "-g"), "   ← 应为 murasame-gpt.ckpt")
    print("   sovits =", f(extra, "-s"), "   ← 应为 murasame-sovits.pth")
    ok = (f(extra, "-g") == "murasame-gpt.ckpt" and f(extra, "-s") == "murasame-sovits.pth")
    print("   结论:", "✓ 标签正确" if ok else "✗ 仍有问题")
    # 顺序颠倒也要对
    rev = ["-g", extra[3], "-s", extra[1]]
    ok2 = (f(rev, "-g") == "murasame-gpt.ckpt" and f(rev, "-s") == "murasame-sovits.pth")
    print("   顺序颠倒后仍然正确:", "✓" if ok2 else "✗")
else:
    print("   ✗ 抠函数失败")

print()
print("=== ④ py_compile ===")
import py_compile  # noqa: E402
try:
    py_compile.compile(RUN, doraise=True)
    print("   OK ✓")
except Exception as e:
    print("   ✗", e)
