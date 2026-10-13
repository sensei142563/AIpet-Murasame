# -*- coding: utf-8 -*-
"""离屏渲染右键菜单（用真实的 tool/pet_menu.StoryMenu），产出 PNG 供肉眼确认清楚度。

为什么离屏：启动整个桌宠要 Live2D/GPU，慢且可能干扰你；这里只验证"菜单本身长什么样"。
菜单项按 _build_outfit_menu 的**当前结构**摆（补回后的第一层）。
"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
sys.path.insert(0, ROOT)

from PyQt5.QtWidgets import QApplication          # noqa: E402
from PyQt5.QtGui import QPixmap                  # noqa: E402
from PyQt5.QtCore import Qt                      # noqa: E402

app = QApplication(sys.argv)
from tool.pet_menu import StoryMenu, section, item, submenu, separator  # noqa: E402

m = StoryMenu(None)
# 第一层：补回的两个主操作 + 分隔线（与改后的代码一致）
act_in = item(m, "输入对话（打字）")
live = True
act_form = item(m, "切换形象（当前：%s）" % ("Live2D" if live else "2D 立绘"))
separator(m)
d = submenu(m, "换装与立绘（当前：刀服／默认姿势）")
submenu(d, "切换服装（当前：刀服）")
submenu(d, "切换动作（手臂姿势）")
submenu(d, "装饰（可多选）")
submenu(d, "切换立绘类型（a / b）")
item(d, "自动切换立绘类型", checked=True)
ai = submenu(m, "电脑与学习")
item(ai, "允许操控电脑（键鼠）", checked=True)
item(ai, "自主学习（自己记东西）", checked=True)
item(ai, "她的状态 / 记忆 / 提醒")
ui = submenu(m, "界面")
item(ui, "显示快捷按钮（对话 / 菜单）", checked=True)

m.adjustSize()
m.show()
app.processEvents()
pm = m.grab()
out = os.path.join(ROOT, "dev", "shots", "menu_after_fix.png")
os.makedirs(os.path.dirname(out), exist_ok=True)
pm.save(out)
print("菜单尺寸:", pm.width(), "x", pm.height())
print("已保存:", out)

# 顺便把"子菜单展开"的样子也导一张（切换服装那个子菜单）
sub = None
for a in d.actions():
    if a.menu() is not None and "切换服装" in a.text():
        sub = a.menu()
        break
if sub is not None:
    for n in ("制服", "睡衣", "私服", "刀服"):
        item(sub, n, checked=(n == "刀服"))
    sub.adjustSize()
    sub.show()
    app.processEvents()
    p2 = sub.grab()
    out2 = os.path.join(ROOT, "dev", "shots", "menu_after_fix_submenu.png")
    p2.save(out2)
    print("子菜单尺寸:", p2.width(), "x", p2.height(), "→", out2)
