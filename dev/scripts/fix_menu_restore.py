# -*- coding: utf-8 -*-
"""补回右键菜单丢失的两个顶层主操作（输入对话 / 形象切换），并让子菜单标题显示当前状态。

依据（旧版备份 remotes/origin/backup/main-before-overwrite-20261001 的注释）：
  · 「💬 输入对话（打字）」—— 没有换装素材的角色（如诺瓦）右键曾是空菜单；
    也是"对话框不好点"的兜底入口。用户反馈后专门加的。
  · 「🎭 换回 2D 立绘 / 换成 Live2D」—— 用户报过「右键的更换为 live2d/2D 形象不见了」。
    main.py:625 至今写着"右键菜单也用这个回调"，但菜单已不使用它。
换基线（搬到协作者 main）时这两项没有带过来 ⇒ 用户感觉"右键的列表不如以前清楚"。
"""
import io
import os
import py_compile
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
P = os.path.join(ROOT, "classes", "murasame_class.py")

t = io.open(P, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
OLD = '''            menu = StoryMenu(self)
            # ★ 顶层只放三个分类，具体开关收进子菜单（以前十几项平铺，菜单太长）
            # ── ① 换装与立绘 ▸ ──
            _dress = submenu(menu, "换装与立绘")'''
NEW = '''            menu = StoryMenu(self)
            # ★★ 第一层必须留两个「主操作」（2026-10-13 补回）
            #   它们原本是用户反馈后专门加的，换基线（搬到协作者 main）时丢失了，
            #   于是右键菜单"不如以前清楚"：
            #   ① 输入对话：没有换装素材的角色（例如诺瓦）以前右键会是**空菜单**；
            #      也是"点下半身才能打字 / 对话框不好点"的兜底入口。
            #   ② 形象切换：用户报过「右键的更换为 live2d/2D 形象不见了」；
            #      回调由 main.py 挂在 pet.toggle_live2d_form（与长按 Shift 2 秒同一函数）。
            try:
                act_in = item(menu, "输入对话（打字）")
                act_in.setToolTip("进入打字模式（和点对话框一样）。Esc 取消。")
                act_in.triggered.connect(lambda *_: self._trigger_input_mode())
            except Exception as _e_menu_in:
                print(f"[桌宠] ⚠ 菜单「输入对话」失败: {_e_menu_in}")
            try:
                _form_cb = getattr(self, "toggle_live2d_form", None)
                if callable(_form_cb):
                    _live_now = bool(self.is_live2d_mode())
                    act_form = item(menu, "切换形象（当前：%s）"
                                    % ("Live2D" if _live_now else "2D 立绘"))
                    act_form.setToolTip("在 Live2D 与 2D 立绘之间切换（等效于长按 Shift 2 秒）。")
                    act_form.triggered.connect(lambda *_: _form_cb())
            except Exception as _e_menu_form:
                print(f"[桌宠] ⚠ 菜单「切换形象」失败: {_e_menu_form}")
            try:
                separator(menu)
            except Exception:
                pass
            # ── ① 换装与立绘 ▸（标题带上当前状态，省得点进去才知道）──
            _dress = submenu(menu, "换装与立绘（当前：%s%s）"
                             % (cur_name or "默认",
                                ("／" + str(cur_act)) if cur_act else ""))'''

if OLD in t:
    t = t.replace(OLD, NEW, 1)
    io.open(P, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ 已补回顶层「输入对话（打字）」与「切换形象（当前：…）」")
    print("✓ 已让「换装与立绘」标题显示当前服装/姿势")
else:
    print("✗ 锚点未命中 —— 先确认 menu = StoryMenu(self) 那段是否被改过")
    i = t.find("menu = StoryMenu(self)")
    print(t[max(0, i - 200):i + 400])
    sys.exit(1)

try:
    py_compile.compile(P, doraise=True)
    print("✓ 语法编译通过 (py_compile)")
except py_compile.PyCompileError as e:
    print("✗ 语法错误：", str(e)[:400])
    sys.exit(1)

# 复核：菜单里现在应该有这两个字符串
t2 = io.open(P, encoding="utf-8", errors="replace").read()
for k in ("输入对话（打字）", "切换形象（当前：", "换装与立绘（当前："):
    print("   复核 %-22s %s" % (k, "存在 ✓" if k in t2 else "缺失 ✗"))
