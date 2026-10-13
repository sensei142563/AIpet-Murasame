# -*- coding: utf-8 -*-
"""按用户 2026-10-13 的拍板（**本地视觉不使用、仅保留接口**）改 test_vision_interface 的判据：
  · 保留：接口本身的行为（第 1/3/4 节：默认 cloud、HTTP 四种形状、CLI 带参数、错误可读）
  · 改判：第 2 节由"示例配置/设置页必须有 vision_source 等" → 改为"**不应出现**这套 UI 面"
  · 改判：第 5 节由"摄像头必须按 vision_local.source() 分支" → 改为"**不**走本地视觉分支"
          同时保留两条有价值的不静默检查。
"""
import io
import os
import py_compile
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")
T = os.path.join(ROOT, "tests", "test_vision_interface.py")

t = io.open(T, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")

# ---------- 文档字符串补一句 ----------
t = t.replace('"""本地视觉模型「接口」体检（本项目不自带本地模型，只留接缝给用户接）。',
              '"""本地视觉模型「接口」体检（本项目不自带本地模型，只留接缝给用户接）。\n\n'
              '★ 2026-10-13 用户拍板：**本地视觉不使用，仅保留接口**。\n'
              '  所以本文件只校验"接口本身还在、行为可预期"，**不再要求**把上游那套 UI 面\n'
              '  （vision_source 选择器 / vision_local_url / vision_local_command 输入框等）接上 ——\n'
              '  那是被否决的设计。第 2、5 节已按此改判。', 1)

# ---------- 第 2 节：改为"不应出现" ----------
OLD2 = '''print("== 2) 示例配置 / UI 选项 / 代码取值集合一致 ==")
ex = json.load(io.open(os.path.join(REPO, "config.example.json"), encoding="utf-8"))
for k, want in (("vision_source", "cloud"), ("vision_local_url", ""),
                ("vision_local_command", ""), ("vision_local_model", "")):
    check("示例里有 %-22s 且默认 %r" % (k, want), ex.get(k) == want, repr(ex.get(k)))
check("代码的取值集合是 (cloud, local)", V.SOURCES == ("cloud", "local"), str(V.SOURCES))
w = io.open(os.path.join(REPO, "pcl_launcher", "widgets.py"), encoding="utf-8").read()
check("设置页给了视觉来源选择（左=本地、右=云端，与 tts_type 同向）",
      '"vision_source", "视觉来源", ["local", "cloud"], "cloud"' in w)
check("设置页给了本地地址 / 命令两个输入框",
      '"vision_local_url", "本地视觉服务地址"' in w
      and '"vision_local_command", "本地视觉命令"' in w)
check("设置页载入时也回填这三个键",
      w.count('_set_slider("vision_source"') >= 1 and w.count('_set_if("vision_local_url"') >= 1
      and w.count('_set_if("vision_local_command"') >= 1)
sp = io.open(os.path.join(REPO, "pcl_launcher", "status_panel.py"), encoding="utf-8").read()
check("状态页会显示「视觉来源」（本地/云端）", '"视觉来源"' in sp and "vision_local" in sp)'''

NEW2 = '''print("== 2) 本地视觉的 UI 面**按设计不存在**（接口保留，但不走这条路）==")
print("   （2026-10-13 用户拍板：本地视觉不使用、仅保留接口 ⇒ 上游那套 UI 面是被否决的设计，")
print("     所以这里反过来查：**不该**出现在示例配置与设置页里。真要接的人自己接。）")
ex = json.load(io.open(os.path.join(REPO, "config.example.json"), encoding="utf-8"))
for k in ("vision_source", "vision_local_url", "vision_local_command", "vision_local_model"):
    check("示例配置里**没有** %-22s（本地视觉不启用）" % k, k not in ex, repr(ex.get(k)))
check("代码的取值集合仍是 (cloud, local)（接口没被删）",
      V.SOURCES == ("cloud", "local"), str(V.SOURCES))
w = io.open(os.path.join(REPO, "pcl_launcher", "widgets.py"), encoding="utf-8").read()
check("设置页**没有**「视觉来源」选择器（上游那套未采纳）",
      '"vision_source", "视觉来源" not in w')
check("设置页**没有**本地地址 / 命令输入框",
      '"vision_local_url", "本地视觉服务地址"' not in w
      and '"vision_local_command", "本地视觉命令"' not in w)'''

if OLD2 in t:
    t = t.replace(OLD2, NEW2, 1)
    print("✓ 第 2 节已改判（要求 UI 面不出现）")
else:
    print("✗ 第 2 节锚点未命中")

# ---------- 第 5 节：改为"不走本地视觉分支" ----------
OLD5 = '''check("摄像头识图按 vision_local.source() 分支",
      "if _vl.source() == \\"local\\":" in mc and "_vl.describe(url)" in mc)
check("云端分支没配模型时**不再静默**（原来直接 return）",
      "没配视觉模型（vision_model_name / APIKEY）" in mc)
check("本地失败时打印可读原因（不静默）", "本地视觉没给出描述" in mc)'''

NEW5 = '''# 按拍板：摄像头识图**不**分支到本地视觉（上游那套语义未采纳）。
# 仍要防的两件事：① 云端没配模型时不许静默 return；② 本地视觉模块不许被静默 import 进来。
check("摄像头识图**不**走 vision_local 分支（本地视觉不启用）",
      "if _vl.source() == \\"local\\":" not in mc)
check("也没有活的 `from tool import vision_local`（保持注释状态）",
      "\\nfrom tool import vision_local" not in mc
      and "\\n    from tool import vision_local" not in mc)
check("云端分支没配模型时**不再静默**（原来直接 return）",
      "没配视觉模型（vision_model_name / APIKEY）" in mc)'''

if OLD5 in t:
    t = t.replace(OLD5, NEW5, 1)
    print("✓ 第 5 节已改判（校验不走本地视觉分支）")
else:
    print("✗ 第 5 节锚点未命中")

io.open(T, "w", encoding="utf-8", newline="\n").write(t)

print()
print("=== 验证 ===")
try:
    py_compile.compile(T, doraise=True)
    print("   ✓ py_compile")
except py_compile.PyCompileError as e:
    print("   ✗", str(e)[:300])
    sys.exit(1)
r = subprocess.run([VENV, os.path.join("tests", "test_vision_interface.py")], cwd=ROOT,
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n"):
    if "[FAIL]" in l or "FAILED" in l or "通过" in l:
        print("   " + l.strip()[:150])
print("   退出码 =", r.returncode)
