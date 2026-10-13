# -*- coding: utf-8 -*-
"""提交「换装不生效」的排查结论与实验脚本。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")
MAP = os.path.join(ROOT, "dev", "merge-map")

print("=== 全量（确认没弄坏东西）===")
r = subprocess.run([VENV, os.path.join("tests", "run_all.py")], cwd=ROOT, capture_output=True,
                   text=True, encoding="utf-8", errors="replace", timeout=1800)
out = (r.stdout or "") + (r.stderr or "")
for l in out.split("\n"):
    if re.match(r"\s*test_\w+\.py\s+-?\d", l) or "总计" in l:
        print("   " + l.strip()[:135])

MSG = """docs: 「换装不生效」排查结论 —— 产品侧解析正常，是测试那次调用用错了入口

背景：test_bugfix_0930b 的「★ 四套衣服画出来各不相同（换装确实生效）」失败，
四套的不透明占比完全相同（32.61 / 37.06），看起来像"换装不生效"这种严重功能问题。

本轮用**三个递进实验**把责任分清了（脚本在 dev/scripts/probe_outfit_*.py）：
  A 改 data/portrait_choice.json **顶层 b.cloth**（测试的写法）→ 四套全 37.06，无变化
  B 改 **pets.murasame.b.cloth** → 仍全 37.06（**写错了 set**，当前 set 是 a）
  C 改 **pets.murasame.a.cloth**（代码真正读的地方）→ load_outfit() **正确解析出四套**
      制服→校服 1952 / 睡衣→睡袍 1956 / 私服→便服 1978 / 刀服→刀装 1950
      但渲染占比仍全 37.06

根因（C 已经证明解析层是好的）：
  classes/murasame_class.py::update_portrait(target, layers) 的 **layers 由调用方传入**，
  而测试调用写的是 `_pet2.update_portrait(_pet2.portrait_target, _pet2.first_portrait)`
  —— `first_portrait` 是**固定不变的初始图层表**，从头到尾没变过 ⇒ 合成结果当然一样。
  **真实换装走的是右键菜单那条路**（重新 load_outfit() 拿新图层再重画），测试绕过了解析、
  直接喂了一个常量。⇒ **不是产品 bug，是测试用错了入口。**

要修的（下一轮）：
  ① 测试改写 `pets.<id>.<set>.cloth`（代码真正读的位置）；
  ② 走真实入口（重新 load_outfit() 取 cloth_id 再交给 update_portrait）；
  ③ 断言加两层：`cloth_id` 四套互不相同（解析层）**且**渲染占比 ≥3 种（渲染层），
     以后再出问题能立刻分清是哪一层坏的。

顺带记录的易踩点（写进文档）：
  data/portrait_choice.json 有**两种布局** —— 顶层 a/b/active 给**无 portrait.sets 的老角色**；
  pets.<角色id>.<set> 给**有 portrait.sets 的角色**（murasame 就属于后者，顶层 a/b 对它无效）。
  走哪一套由 tool/portrait_outfit.py::_pet_tables() 决定。

新增 dev/docs/换装不生效-排查结论-2026-10-13.md（含三层实验表与代码行号）。
"""
p = os.path.join(MAP, "_msg_outfit.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:160])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
