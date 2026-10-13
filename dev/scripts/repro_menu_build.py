# -*- coding: utf-8 -*-
"""直接复现：造一个 Murasame()，调 _build_outfit_menu()，把真实异常打出来（不走吞异常的 except）。"""
import io
import os
import sys
import traceback

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from PyQt5.QtWidgets import QApplication          # noqa: E402

app = QApplication(sys.argv)

print("=== 1) 直接 import 并构造 Murasame ===")
try:
    from classes.murasame_class import Murasame
    pet = Murasame()
    print("   ✓ 构造成功")
except Exception:
    print("   ✗ 构造失败:")
    traceback.print_exc()
    sys.exit(1)

print()
print("=== 2) 调 _build_outfit_menu()（原样，看它自己的 except 说什么）===")
try:
    menu = pet._build_outfit_menu()
    print("   返回:", type(menu).__name__ if menu is not None else "None")
    if menu is not None:
        print("   菜单项:")
        for a in menu.actions():
            print("      • %r" % a.text())
except Exception:
    print("   ✗ 抛异常:")
    traceback.print_exc()

print()
print("=== 3) 手工重放 _build_outfit_menu 的前几步，定位具体哪一步炸 ===")
try:
    from tool.pet_menu import StoryMenu, section, item, submenu, separator
    from tool.portrait_outfit import SETS, load_outfit
    from qq.qq_portrait import clothes_for, actions_for, decors_for
    _pid = pet._pet_id or None
    cur_set = pet._current_set()
    print("   cur_set =", cur_set, " pet_id =", _pid)
    cur = load_outfit(cur_set)
    print("   load_outfit ok:", str(cur)[:100])
    try:
        cloths = list(clothes_for(cur_set, _pid))
        print("   clothes_for ok: %d 条 %s" % (len(cloths), str(cloths[:3])[:110]))
    except Exception:
        print("   ✗ clothes_for 抛异常:"); traceback.print_exc()
    try:
        acts = list(actions_for(cur_set, _pid))
        print("   actions_for ok: %d 条" % len(acts))
    except Exception:
        print("   ✗ actions_for 抛异常:"); traceback.print_exc()
    try:
        decs = list(decors_for(cur_set, _pid))
        print("   decors_for ok: %d 条" % len(decs))
    except Exception:
        print("   ✗ decors_for 抛异常:"); traceback.print_exc()
    m = StoryMenu(pet)
    print("   StoryMenu 构造 ok")
    item(m, "输入对话（打字）")
    separator(m)
    d = submenu(m, "换装与立绘（当前：测试）")
    print("   submenu ok, 顶层项数 =", len(m.actions()))
except Exception:
    print("   ✗ 手工重放抛异常:"); traceback.print_exc()
