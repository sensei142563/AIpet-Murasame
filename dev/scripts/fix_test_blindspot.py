# -*- coding: utf-8 -*-
"""把 test_vision_interface.py 第 76~80 行的"标签断言"改成"键名/取值断言"。
  背景：原断言查的是 '"vision_source", "视觉来源"' —— 而设置页实际用的标签是「识别来源」，
        字符串对不上 ⇒ 断言**永远成立** ⇒ "设置页不该乱暴露这个选项"这条意图从未被真正检查，
        于是 widgets.py 里默认值写成 "local"（与实现缺省 cloud 相反）一路全绿到手工翻代码才发现。
  做法：**加断言**（不是删断言）——直接钉住"键名 + 取值集合 + 默认值"，
        并保留"不该有本地地址/命令输入框"那条（它本来就对）。
"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
F = os.path.join(ROOT, "tests", "test_vision_interface.py")

t = io.open(F, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")

# ---------- ① 注释更新（说明现行设计 + 为什么要按键名查）----------
OLD_C = '''print("== 2) 本地视觉的 UI 面**按设计不存在**（接口保留，但不走这条路）==")
print("   （2026-10-13 用户拍板：本地视觉不使用、仅保留接口 ⇒ 上游那套 UI 面是被否决的设计，")
print("     所以这里反过来查：**不该**出现在示例配置与设置页里。真要接的人自己接。）")'''
NEW_C = '''print("== 2) 本地视觉：接口保留、默认不使用（按**键名与取值**查，不按标签查）==")
print("   （2026-10-13 用户拍板：本地视觉不使用、仅保留接口。现行设计是——")
print("     示例配置里不出现这些键；设置页里**有**「识别来源」下拉（vision_source），")
print("     但**没有**上游那套本地地址/命令输入框。")
print("     ⚠ 这里特意**按键名与取值**断言而不是按标签文案：")
print("       上一版查的是 `\\"vision_source\\", \\"视觉来源\\"`，可设置页用的标签是「识别来源」，")
print("       字符串对不上 ⇒ 断言永远成立 ⇒ 默认值被写成 local（与实现缺省 cloud 相反）")
print("       也能一路全绿。改文案就等于把检查悄悄关掉，这类断言不能再这么写。）")'''
if OLD_C in t:
    t = t.replace(OLD_C, NEW_C, 1)
    print("✓ ① 已更新第 2 节的说明（讲清现行设计 + 为什么按键名查）")
else:
    print("✗ ① 注释锚点未命中")

# ---------- ② 断言改强 ----------
OLD_A = '''w = io.open(os.path.join(REPO, "pcl_launcher", "widgets.py"), encoding="utf-8").read()
check("设置页**没有**「视觉来源」选择器（上游那套未采纳）",
      '"vision_source", "视觉来源" not in w')
check("设置页**没有**本地地址 / 命令输入框",
      '"vision_local_url", "本地视觉服务地址"' not in w
      and '"vision_local_command", "本地视觉命令"' not in w)'''
NEW_A = '''w = io.open(os.path.join(REPO, "pcl_launcher", "widgets.py"), encoding="utf-8").read()
# ① 设置页**应当**有「识别来源」选择器，且**默认值必须是 cloud**（与 tool/vision_local.py 的缺省一致）。
#    直接钉住"键名 + 取值集合 + 默认值"这一整串 —— 这正是当初被放过的那一处。
check("设置页有「识别来源」且默认 cloud（与实现缺省一致）",
      '_add_choice("vision_source", "识别来源", ["local", "cloud"], "cloud"' in w)
# ② 防回归：不允许出现"默认选 local"的写法（无论标签叫什么）
check("设置页**没有**把 vision_source 默认写成 local（防回归）",
      '["local", "cloud"], "local"' not in w)
# ③ 上游那套输入框仍然不该有（这一条原本就正确，保留）
check("设置页**没有**本地地址输入框",
      '"vision_local_url"' not in w)
check("设置页**没有**本地命令输入框",
      '"vision_local_command"' not in w)
# ④ 启动器侧同样不得把"没配"当成 local（2026-10-13 修过的 bug：首页会写"本地视觉模型（本地部署）"）
sw = io.open(os.path.join(REPO, "pcl_launcher", "silicon_window.py"), encoding="utf-8").read()
check("启动器不再把 vision_source 缺省当 local（防回归）",
      'cfg.get("vision_source") or "local"' not in sw
      and '_vcfg.get("vision_source") or "local"' not in sw)'''
if OLD_A in t:
    t = t.replace(OLD_A, NEW_A, 1)
    print("✓ ② 已把标签断言换成键名/取值断言（4 条，含两条防回归）")
else:
    print("✗ ② 断言锚点未命中")

io.open(F, "w", encoding="utf-8", newline="\n").write(t)

print()
print("=== 复核：第 2 节现在的样子 ===")
lines = io.open(F, encoding="utf-8", errors="replace").read().split("\n")
start = next((i for i, l in enumerate(lines) if "== 2)" in l), 0)
for i in range(start, min(len(lines), start + 30)):
    print("   %4d| %s" % (i + 1, lines[i].rstrip()[:108]))
