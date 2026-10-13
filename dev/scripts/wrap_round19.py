# -*- coding: utf-8 -*-
"""收尾本轮：清临时文件、提交探针脚本、给出最后一项的下一步。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

# 清临时文件
for f in ("dev/tmp_probe.txt",):
    p = os.path.join(ROOT, f)
    if os.path.isfile(p):
        os.remove(p)
        print("✓ 已删除临时文件 %s" % f)

MSG = """chore(probe): 留一个"pixmap vs grab"的对照探针；本轮该实验没出输出，下一轮换跑法

目的（收最后一项「连续换装只有第一次生效」）：
  区分**产品 bug**（合成出来的 pixmap 就没变）与**取图假象**（grab() 拿到上一帧）——
  直接对 `pet.pixmap()`（QLabel 里真正被设进去的那张）取图像摘要，并与 `pet.grab()` 对照。

做法：`dev/scripts/probe_pixmap_vs_grab.py`
  逐套 `_switch_cloth()` → 取 `pet.pixmap()` 摘要 + `app.processEvents()` 后 `pet.grab()` 摘要。

⚠ 本轮结果：**该探针没有任何输出**（退出码 0、0 行），说明这个"外层脚本 + `python -c` 内层"
  的跑法有问题（内层连异常都没吐出来）。下一轮改用**落地成 .py 文件直接跑**的方式重做这个实验，
  不要再用 `-c` 拼长脚本。

下一轮的两条判据（谁先证实就按谁修）：
  · 若 `pet.pixmap()` 的摘要四套各不相同 ⇒ **产品侧正常**，是 grab/重画的问题（改测试取图方式）；
  · 若 `pet.pixmap()` 的摘要同样只有第一次不同 ⇒ **合成有缓存**，去查 `_compose_pixmap()`
    是否按衣服号命中了旧缓存。
"""
p = os.path.join(MAP, "_msg_probe.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:160])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
