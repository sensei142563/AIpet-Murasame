# -*- coding: utf-8 -*-
"""系统性审计：对比「我们当前树」与「协作者已补回的三件事」+「覆盖前备份」，找丢失项。

依据（origin/main 上协作者的三个提交信息）：
  e7fb17a merge(lab): 补回 natsume 的 decor_rules（我们独有的 2 个键）
  a4a5f8e merge(lab): 补回 secondary_text（我们 57f0e55c 的 UI 颜色辅助，他们完全没有）
  c414905 fix: tool/plugins.py 取我们的超集版本（补齐 handle_reply 等，修好他们自己那条红测试）
"""
import io
import json
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"


def sh(*a):
    r = subprocess.run(["git", "-C", ROOT, *a], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=300)
    return (r.stdout or "")


def show(ref, path):
    return sh("show", "%s:%s" % (ref, path))


print("=" * 78)
print("审计 1：pets/natsume/pet.json 的 decor_rules（协作者说他们那边补回了 2 个键）")
print("=" * 78)
p = os.path.join(ROOT, "pets", "natsume", "pet.json")
if os.path.isfile(p):
    try:
        cur = json.loads(io.open(p, encoding="utf-8", errors="replace").read())
        dr = cur.get("decor_rules")
        print("   当前树 decor_rules:", json.dumps(dr, ensure_ascii=False)[:200] if dr else "**没有** ✗")
        print("   键数量:", len(dr) if isinstance(dr, dict) else (len(dr) if isinstance(dr, list) else 0))
    except Exception as e:
        print("   解析失败:", e)
else:
    print("   文件不存在:", p)
for ref in ("remotes/origin/main", "remotes/origin/backup/main-before-overwrite-20261001"):
    t = show(ref, "pets/natsume/pet.json")
    if t:
        try:
            o = json.loads(t)
            dr = o.get("decor_rules")
            print("   %-52s decor_rules 键数=%s" % (ref.split("/")[-1],
                  len(dr) if isinstance(dr, (dict, list)) else 0))
        except Exception as e:
            print("   %s 解析失败 %s" % (ref, e))

print()
print("=" * 78)
print("审计 2：pcl_launcher/colors.py 的 secondary_text")
print("=" * 78)
cp = os.path.join(ROOT, "pcl_launcher", "colors.py")
cur_txt = io.open(cp, encoding="utf-8", errors="replace").read() if os.path.isfile(cp) else ""
print("   当前树有 secondary_text:", "有 ✓" if "secondary_text" in cur_txt else "**没有** ✗")
for ref in ("remotes/origin/main", "remotes/origin/backup/main-before-overwrite-20261001"):
    t = show(ref, "pcl_launcher/colors.py")
    print("   %-52s %s" % (ref.split("/")[-1],
          "有 secondary_text ✓" if "secondary_text" in t else ("没有 ✗" if t else "(取不到)")))

print()
print("=" * 78)
print("审计 3：tool/plugins.py 是否具备 handle_reply 等（协作者说取了他们的超集版本）")
print("=" * 78)
pp = os.path.join(ROOT, "tool", "plugins.py")
cur_p = io.open(pp, encoding="utf-8", errors="replace").read() if os.path.isfile(pp) else ""
print("   当前树行数:", len(cur_p.split("\n")))
for k in ("handle_reply", "def enabled", "def set_enabled", "register", "on_message"):
    print("      %-14s %s" % (k, "有 ✓" if k in cur_p else "没有 ✗"))
for ref in ("remotes/origin/main", "remotes/origin/backup/main-before-overwrite-20261001"):
    t = show(ref, "tool/plugins.py")
    if t:
        print("   %-52s 行数=%-5d handle_reply=%s" % (ref.split("/")[-1], len(t.split("\n")),
              "有" if "handle_reply" in t else "没有"))
