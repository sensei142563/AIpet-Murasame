# -*- coding: utf-8 -*-
"""提交本轮的恢复与修复。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

MSG = """fix(lost): 恢复换基线时丢掉的两处真实功能 + 修好 4 项红测试（菜单相关）

背景：用户要求"优化协作者相关改动，有些可以**对标协作者优化前的内容**"。
做法：与「覆盖前备份」remotes/origin/backup/main-before-overwrite-20261001 系统对比，
      逐项判断"是不是真的会坏"，只修**有证据会坏**的，避免把双方各自的新东西覆盖掉。

一、tool/plugins.py：恢复为 504 行超集版（补齐 14 个函数）
  证据：本树只有 303 行，缺 handle_reply / load_plugin / manifest_dirs / due_schedules /
        pending_results / summary_text / root / timeout_sec / _cfg / _find / _is_off /
        _work / reset_cache / results_note；而**覆盖前备份与 origin/main 的函数集合完全相同**。
  影响证据：tests/test_plugin_markup.py:101 调用 P.handle_reply(...)（本树会 AttributeError）。
  配套改动：本树唯一一处短版接口调用点 classes/murasame_class.py `_plg2._root()` → `_plg2.root()`
        （备份版里叫 root；全仓只有这一处）。
  验证：tests/test_plugin_markup.py **19 OK / 0 FAIL、退出码 0**（含"端到端真跑一个插件"）。

二、pets/natsume/pet.json：补回 decor_rules
  证据：tool/portrait_outfit.py 全程在用这个键（247 / 1115 / 1459 / 1476 行，
        apply_decor_rules 读的就是 pet 的 decor_rules），而本树**任何 pet.json 都没有它**
        ⇒ "装扮随情绪联动"整条不生效。
  取值与 origin/main 完全对齐：sets.a = []、sets.b = [{"decor": "嫌弃阴影", "emotion": "嫌弃"}]。
  验证：JSON 合法；与 origin/main 的值逐字一致。

三、tests/test_bugfix_0930.py：菜单捕获桩同步到新实现（**断言一条未改**）
  真因：菜单弹出方式已从 QMenu.exec_() 改成动画 popup()（classes/murasame_class.py:3212
        _popup_menu_animated），而测试只打桩 exec_ ⇒ 永远捕获不到 ⇒ menu=None ⇒ 4 项全红。
  修法：两种弹出方式都打桩 + 加 pet._outfit_menu 兜底；检查项文本与阈值一律不动。
  验证：该文件从 10 项失败降到 **7 项**，菜单这 4 项转绿，其中"★ 有「Live2D / 2D 形象」切换项"
        现在能看到完整菜单项列表 —— 这也**反证**了本次补回的入口正是项目原本的要求。

四、发现但**未动**的（避免误伤，留给用户定）
  · pcl_launcher/colors.py 是**双向分叉**：本树 700 行 / 备份 605 行，
    备份有 secondary_text / _ACTIVE_THEME_ID / 8 级灰阶派生，本树有 _mix_color / _theme_text_color。
    （当前全仓**没有** secondary_text 的调用点 ⇒ 暂不报错，只缺"浅色主题次级文字可读性"。）
  · pets/natsume/pet.json 的 height_ratio 本树 0.95 / 备份 0.55 —— 属显示设置，可能是有意改的。

五、本轮同时暴露的项目自检状态（重要，供后续排期）
  `runtime\\venv\\Scripts\\python.exe tests\\run_all.py` ⇒ **10 个文件里 7 个红、共 39 项失败**：
     test_bounds.py(2) · test_bugfix_0930.py(7，其中菜单 4 项已修) · test_bugfix_0930b.py(2)
     · test_config_contracts.py(3，全仓重复字典键，如 tool/jp_names.py '納得')
     · test_frontend_style.py(13) · test_qt_lifecycle.py(直接 ValueError 崩)
     · test_vision_interface.py(9)
  最集中的一类：**「状态窗 / 状态页」整套没接上**（status_page_enabled、QDialog#statusWindow
  的 QSS、卡片 WA_StyledBackground、侧栏「状态」项都缺）。
"""
p = os.path.join(MAP, "_msg_lost_fix.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
r = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
print("桌面仓:", (r.stdout or r.stderr or "").splitlines()[0][:160])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
