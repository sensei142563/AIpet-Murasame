# -*- coding: utf-8 -*-
"""把根目录那份调研报告归入 docs/，然后提交本轮成果。"""
import io
import os
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

src = os.path.join(ROOT, "调研-AI桌宠-聊天机器人方向.md")
dst = os.path.join(ROOT, "docs", "AI桌宠-聊天机器人方向调研.md")
if os.path.isfile(src):
    shutil.move(src, dst)
    print("✓ 已归档:", os.path.basename(dst))
else:
    print("· 根目录那份已不在（可能已归档）")

MSG = """docs+fix(menu): 文档贴合实现 + 补回右键菜单丢失的主操作 + PPT 规划与两份市场调研

用户本轮要求（2026-10-13）：
  ① 文档要贴合目前的实现  ② 准备汇报 PPT 规划  ③ 优化协作者相关改动
  （并明确：之前那些安卓/Termux/3D 的任务暂时挂起；"掀裙子"之类内容不写入任何文档）

一、右键菜单：补回两个**主操作**（这是"右键的列表不如以前清楚"的根因）
  证据：与「覆盖前备份」remotes/origin/backup/main-before-overwrite-20261001 对比，
  那份 classes/murasame_class.py 的第一层有：
      💬 输入对话（打字）           → self._trigger_input_mode
      🎭 换回 2D 立绘 / 换成 Live2D
  旧代码注释写明了它们为什么存在：
      · 「原来只能'点下半身'进输入模式，命中触摸区域时那一下会被触摸吃掉（用户报的
         '对话框不好点'）；没有换装素材的角色（例如诺瓦）右键菜单原本还是空的」
      · 「用户报『右键的更换为 live2d/2D 形象不见了』」
  而当前分支这份文件里连字符串都搜不到（git log -S 无结果）⇒ **不是被删，是换基线时没带过来**。
  同时 main.py:625 的注释至今写着"右键菜单也用这个回调做「换成 Live2D / 2D 形象」"，
  main.py:627 也仍在挂 pet.toggle_live2d_form —— 只有菜单不再使用它。

  修复（classes/murasame_class.py::_build_outfit_menu）：
      · 第一层恢复「输入对话（打字）」→ self._trigger_input_mode
      · 第一层恢复「切换形象（当前：Live2D / 2D 立绘）」→ pet.toggle_live2d_form
        （没有该回调时自动跳过，不影响其它角色）
      · 「换装与立绘」标题改为带当前状态：「换装与立绘（当前：刀服／默认姿势）」
        ⇒ 不展开也能看到现在穿什么，兼顾"短"与"一眼看清"
  已用**真实的 StoryMenu 类**离屏渲染出预览：dev/shots/menu_after_fix.png（及子菜单图）。
  语法经 py_compile 验证通过。

二、文档贴合实现
  · dev/docs/功能清点-功能与实现与状态.md 新增**第六章**：第 37~50 项（记忆互通与真机往返、
    手机端 3D/3D AR、画面级像素验收、手部互动链路、碰撞盒可视化、热点链接与蜂窝纠正、
    一键真机验收、离线回归闸门、离线识别/合成的真机结论、诊断代码纪律、两个可见开关），
    并新增 6.1「覆盖前 vs 现在」差异订正表、6.2 诚实清单（离线原生库不可用/手部检测器未接入/
    3D 用的是示例模型/手机 QQ 通道未装完）。第五章汇总补了指向第六章的说明。

三、PPT 规划与市场调研（两份调研报告已落盘）
  · dev/docs/汇报PPT规划-2026-10-13.md —— 讲故事骨架（四幕）+ 三块内容分页脚本
    + 需要录制的素材清单 + 制作顺序；明确保留"诚实页"（我们不是首创、不写"全球首个"），
    并注明"任何学校/专业/绩点等个人身份信息一律不写进 PPT"。
  · docs/桌面宠物市场调研-功能对比.md —— 开源桌宠与 Steam 商业桌宠逐项对比（含《你妈》，
    已查清其真实名/作者/平台上架信息与"为什么火"），带来源 URL 与 15 条未查证清单。
  · docs/AI桌宠-聊天机器人方向调研.md —— QQ/微信机器人框架与 AI 伴侣两条线的对比。
    核心结论：**"有形象的都不接 QQ/微信，接 QQ/微信的都没形象"**；唯一"四件齐全"的
    竞品是 super-agent-party（约 2.7k★，AGPLv3 强传染 + 商用需授权）；Open-LLM-VTuber
    （14k★）README 明写**长期记忆已暂时下线** ⇒ 记忆是我们最清晰的差异化点。
"""
p = os.path.join(MAP, "_msg_ppt_menu.txt")
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
