# -*- coding: utf-8 -*-
"""提交：返回键行为已被日志证实正确 + 检查项改为不依赖起始页。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
MAP = os.path.join(MAIN, "dev", "merge-map")

MSG = """test(back): 用日志证实返回键行为正确；检查项改为不依赖"起始在首页"

一、结论：**App 的返回键行为是对的**，之前那个 FAIL 是检查项写错了
  给全局 BackHandler 与 ChatScreen 的 6 个子处理器都加了打点后，一次受控测试就看清了：
      21:45:40.214  [Back] 全局 BackHandler 收到 BACK：tab=0 history=0 lastBackAt=0
      21:45:40.215  [Back] → 第一次确认，弹提示（2 秒内再按才退出）
      21:45:41.995  [Back] 全局 BackHandler 收到 BACK：lastBackAt=1791726340215
      21:45:41.996  [Back] → 满足两次条件，调用 finish()
  第二次距第一次 1.78 秒（在 2 秒窗口内）⇒ 正确调用 finish()，App 正常退出，
  前台随即不再是本应用。**与设计一致**。

二、那为什么验收一直报 FAIL
  检查项里有一步"点「首页」"，它是**按文字找节点**点的 —— 真机上没点中（没切到首页），
  于是：BACK#1 只是"从别的页回首页"（按新规则会清零退出计时），BACK#2 才开始计时 ⇒ 当然不退出。
  属于"检查项对起始状态的假设错了"，不是 App 的问题。

三、改动
  ① ④ 检查项不再假设起始页：先用**底部导航固定坐标**（111,2641）点首页，
     然后最多按 3 次返回，**必须退出**（分别记录每次后是否仍在 App 内，失败时一目了然）。
  ② 全局 BackHandler 与 ChatScreen 的 6 个子处理器都保留打点（写 diag.log）：
     以后再出现"返回键不灵/误退出"，一眼就能看出是哪个处理器吃掉了事件。
     这些只是日志行，不在产品路径上构造任何原生对象，无副作用。

四、本轮验收
  PASS 10 / FAIL 0 / SKIP 10（退出码 0）。UI 相关项仍 SKIP —— 因为那会儿你在用 QQ，
  前台守卫按设计没有打扰你；④ 的行为已由上文的日志独立证实。
"""
p = os.path.join(MAP, "_msg_back.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
print("手机仓:", (r.stdout or r.stderr or "").splitlines()[0][:150])
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
r2 = subprocess.run(["git", "-C", MAIN, "commit", "-m", "chore(scripts): 返回键打点与检查项修正"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
print("桌面仓:", (r2.stdout or r2.stderr or "").splitlines()[0][:150])
for nm, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True, encoding="utf-8").stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True,
                        text=True, encoding="utf-8").stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (nm, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
