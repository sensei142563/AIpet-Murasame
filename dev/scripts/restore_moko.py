# -*- coding: utf-8 -*-
"""恢复「沫子的日常」（senrenbanka_copy）：
  ① 从 git 历史取回它的 theme.json
  ② 检查/修正里面的 name（应为「沫子的日常」）与背景声明（应为 video + assets/bg_custom.mp4）
  ③ 写回磁盘
  ④ 验证启动器能枚举到它（跑 colors.py 的主题枚举）
"""
import io
import json
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
TD = os.path.join(ROOT, "pcl_launcher", "themes", "senrenbanka_copy")
OUT = os.path.join(TD, "theme.json")

print("=== ① 从 git 历史取出原文（c974e6db）===")
r = subprocess.run(["git", "-C", ROOT, "show",
                    "c974e6db:pcl_launcher/themes/senrenbanka_copy/theme.json"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
raw = r.stdout or ""
print(raw)
print("   （%d 字节，git 退出码 %d）" % (len(raw), r.returncode))

if not raw.strip():
    print("   ✗ 没取到内容，退出")
    sys.exit(1)

# ---------- ② 检查 name 与背景 ----------
try:
    obj = json.loads(raw)
except Exception as e:
    print("   ✗ JSON 解析失败：%s" % e)
    sys.exit(1)

print("=== ② 关键字段 ===")
print("   id        =", obj.get("id"))
print("   name      =", obj.get("name"))
print("   builtin   =", obj.get("builtin"))
for k in ("background", "bg", "wallpaper", "video", "bg_video", "assets"):
    if k in obj:
        print("   %-10s= %r" % (k, obj[k]))

changed = []
if obj.get("name") != "沫子的日常":
    print("   → name 改为「沫子的日常」（原来是 %r）" % obj.get("name"))
    obj["name"] = "沫子的日常"
    changed.append("name")

# 背景声明：确保指向 assets/bg_custom.mp4（磁盘上就是这么个文件）
mp4 = os.path.join(TD, "assets", "bg_custom.mp4")
if os.path.isfile(mp4):
    # 找找它现在怎么声明背景的
    def find_bg(o, path=""):
        hit = []
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, str) and v.lower().endswith((".mp4", ".webm", ".mkv")):
                    hit.append((path + "." + k, v))
                hit += find_bg(v, path + "." + k)
        return hit
    hb = find_bg(obj)
    print("   → 现存的视频声明：", hb or "（没有）")
    if not hb:
        obj["background"] = {"type": "video", "path": "assets/bg_custom.mp4", "opacity": 1.0}
        changed.append("background(video)")
        print("   → 已补上 background = video / assets/bg_custom.mp4")

if changed:
    io.open(OUT, "w", encoding="utf-8", newline="\n").write(
        json.dumps(obj, ensure_ascii=False, indent=2))
    print("   ✓ 已写回 %s（改动：%s）" % (OUT, "、".join(changed)))
else:
    # 内容一致也写回去（原来磁盘上没有这个文件）
    io.open(OUT, "w", encoding="utf-8", newline="\n").write(raw)
    print("   ✓ 已按历史原文写回 %s" % OUT)

print()
print("=== ③ 磁盘现状 ===")
for dp, dn, fn in os.walk(TD):
    for f in sorted(fn):
        p = os.path.join(dp, f)
        print("   %-40s %8.1f MB" % (p.replace(TD + os.sep, "")[:40],
                                     os.path.getsize(p) / 1048576))

print()
print("=== ④ 验证：启动器能不能枚举到四个主题 ===")
code = (
    "import sys, json, os\n"
    "sys.path.insert(0, r'%s')\n"
    "sys.path.insert(0, r'%s')\n"
    "from pcl_launcher import colors as C\n"
    "fn = None\n"
    "for n in ('list_themes','available_themes','themes','iter_themes','load_themes'):\n"
    "    if hasattr(C, n): fn = getattr(C, n); print('用函数:', n); break\n"
    "if fn:\n"
    "    try:\n"
    "        r = fn()\n"
    "        print('枚举结果:', json.dumps(r, ensure_ascii=False)[:600])\n"
    "    except Exception as e:\n"
    "        print('调用失败:', e)\n"
    "else:\n"
    "    print('colors.py 里没有枚举函数，改为直接读目录：')\n"
    "    th = os.path.join(r'%s', 'pcl_launcher', 'themes')\n"
    "    for d in sorted(os.listdir(th)):\n"
    "        tj = os.path.join(th, d, 'theme.json')\n"
    "        nm = ''\n"
    "        if os.path.isfile(tj):\n"
    "            try: nm = json.load(open(tj, encoding='utf-8')).get('name','')\n"
    "            except Exception as e: nm = '解析失败:' + str(e)\n"
    "        print('   %-20s %s' % (d, nm or '(无 theme.json ⇒ 枚举不到)'))\n"
) % (ROOT, os.path.join(ROOT, "pcl_launcher"), ROOT)
p = os.path.join(ROOT, "dev", "scripts", "_verify_themes.py")
io.open(p, "w", encoding="utf-8", newline="\n").write(code)
r2 = subprocess.run([sys.executable, p], cwd=ROOT, capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=600)
print((r2.stdout or "") + (r2.stderr or "")[:600])
