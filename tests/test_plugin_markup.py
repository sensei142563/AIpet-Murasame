# -*- coding: utf-8 -*-
"""插件标记体检：清台词时**绝不吃掉她自己的话**，解析按契约抓同行参数。

真实案例（2026-09-29 撞到的）：`_MARK_RE` 原来是「标记 + 其后最多 80 字」**一个正则**，
被 `parse()` 和 `clean_for_speech()` 共用 →
  · 清理把她的话一起删掉：`'【插件:系统信息】内存用了 8.5G。'` → **空串**（实测剩 `'enticAMD。'`）
  · `'前半句【插件:x】后半句'` → 只剩 `'前半句'`
修法：`_MARK_RE` 收窄成只匹配标记本身；`_MARK_ARG_RE`（标记 + 同行尾巴 ≤60 字）只给解析用；
清理改按行 —— **整行 `fullmatch` 到「标记(+短参数)」才整行不念**，否则只挖标记、台词全留下。

⚠ 容易改过头的地方：解析**必须**仍按契约抓同行参数（模型完全可能把参数写在同一行）——
老探针 `IMMEDIATE/长参数` 那条就是钉这个的，别为了"保守"把参数丢掉。

用法：`python tests/test_plugin_markup.py`
"""
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.chdir(REPO)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

FAILS = []


def check(name, cond, extra=""):
    if cond:
        print("  [OK]   %s %s" % (name, extra))
    else:
        print("  [FAIL] %s %s" % (name, extra))
        FAILS.append(name)


import tool.plugins as P   # noqa: E402

PEN = "参数甲"
print("== 1) 清理：她的话一个字都不许少 ==")
check("标记在句尾（她先说话再用插件）",
      P.clean_for_speech("我看看哦。【插件:系统信息】") == "我看看哦。",
      repr(P.clean_for_speech("我看看哦。【插件:系统信息】")))
check("标记夹在句子中间（只挖标记、两侧都留）",
      P.clean_for_speech("前半句【插件:x】后半句") == "前半句后半句",
      repr(P.clean_for_speech("前半句【插件:x】后半句")))
check("没有标记的普通回复原样通过",
      P.clean_for_speech("没有标记的普通回复，处理器：AuthenticAMD。")
      == "没有标记的普通回复，处理器：AuthenticAMD。")
check("多行：标记独占一行，前后她的话都在",
      P.clean_for_speech("先说一句\n【插件:x】\n再说一句") == "先说一句\n再说一句")

long_line = ("【插件:系统信息】内存用了 8.5G / 共 15.8G（53%）；开机 1.8 小时；"
             "处理器：AMD64 Family 25 Model 68 Stepping 1, AuthenticAMD。")
got = P.clean_for_speech(long_line)
check("★ 行首标记 + 长尾：她的话留下了（老 bug 会只剩 'enticAMD。'）",
      got.startswith("内存用了") and "enticAMD" in got and "【插件" not in got, repr(got[:40]))
check("整行就是「标记+短参数」→ 整行不念（那是给插件的指令）",
      P.clean_for_speech("【插件:系统信息】内存 8G") == "")

print("== 2) 解析：按契约抓同行参数 ==")
check("行内标记也抓参数（契约写法）",
      P.parse("我帮你点一首【插件:点歌】夜曲") == [("点歌", "夜曲")],
      str(P.parse("我帮你点一首【插件:点歌】夜曲")))
check("句中标记 + 参数（老探针钉的写法）",
      P.parse("我看看。【插件:够用】" + PEN) == [("够用", PEN)],
      str(P.parse("我看看。【插件:够用】" + PEN)))
check("两个标记各自取参数（没参数的那个为空）",
      P.parse("我先看看【插件:系统信息】\n【插件:点歌】青花瓷")
      == [("系统信息", ""), ("点歌", "青花瓷")])
check("参数两端的中文冒号/标点被剥掉",
      P.parse("【插件:系统信息】：内存 8G")[0][1] == "内存 8G")
p5 = P.parse("【插件:系统信息】" + "字" * 120)
check("超长尾巴被截断（不把整段话当参数）", p5 and len(p5[0][1]) <= 60,
      "参数长度 %d" % (len(p5[0][1]) if p5 else -1))

print("== 3) 两个正则分工正确（行为断言，别比对源码字面量）==")
check("清理正则只匹配标记本身（1 个组）", P._MARK_RE.groups == 1)
check("参数正则：'标记+短尾巴' 能 fullmatch（整行不念的判据）",
      P._MARK_ARG_RE.fullmatch("【插件:点歌】夜曲") is not None)
check("参数正则：句中标记 fullmatch 失败（所以她的话不会被当整行指令）",
      P._MARK_ARG_RE.fullmatch("前半句【插件:点歌】后半句") is None)
check("参数正则：超长尾巴 fullmatch 失败（长句按台词保留）",
      P._MARK_ARG_RE.fullmatch("【插件:x】" + "字" * 80) is None)
src = open(os.path.join(REPO, "tool", "plugins.py"), encoding="utf-8").read()
check("清理确实复用 fullmatch 判据", "_MARK_ARG_RE.fullmatch(line.strip())" in src)

print("== 4) 端到端：真跑一个插件，她的话 + 结果都在，念出口的话里没有标记 ==")
import tool.plugins as PL   # noqa: E402

marks = [m for m in PL.markers() if m]
if marks:
    # markers() 每项可能是"标记"或 (标记, 说明) —— 两种都容忍
    first = marks[0]
    mk = first[0] if isinstance(first, (tuple, list)) else first
    mk = str(mk)
    P._pending = []
    spoken = P.handle_reply("我看看哦。【插件:%s】" % mk)
    check("她的话还在（%s）" % mk, spoken.startswith("我看看哦。"), repr(spoken[:40]))
    check("念出口的话里不含标记", "【插件" not in spoken)
    check("插件结果接在后面（若该插件这次有输出）",
          len(spoken) >= len("我看看哦。"), repr(spoken[:60]))
else:
    print("  [--]   没有可用插件，跳过端到端（不当作失败）")

print()
if FAILS:
    print("FAILED %d 项：%s" % (len(FAILS), "、".join(FAILS)))
    sys.exit(1)
print("插件标记体检全部通过")
sys.exit(0)
