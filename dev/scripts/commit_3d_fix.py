# -*- coding: utf-8 -*-
"""提交 3D 显示修复 + AR 顶栏修复。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
MAP = os.path.join(MAIN, "dev", "merge-map")

MSG = """fix(3d): 3D 形象终于显出画面（根因：body 高度为 0，canvas 永远画不出来）+ Live2D AR 的 +/− 被挤出屏幕

一、3D 看不见的真正原因（用户反馈"从始至终没看见任何 3D 模型"，此前我用日志里的 VRM_OK
    当成"成功了"，是错的 —— 屏幕才是事实）
  排查过程中一路排除：模型确实加载成功（VRM_OK）、渲染循环在跑（≈75 帧/秒）、
  画布尺寸=视口、相机与缩放参数正常（boxH=1.615 scale=0.978 camY=1.40 camZ=1.90 fov=34）。
  最后加了一个探针把布局事实写进日志，一句话命中：
      P:canvasRect=0,0,339,443 style=339pxx443px buf=339x443 **body=339x0** topAtCenter=HTML
  ⇒ document.body.clientHeight = 0（子元素几乎都是 position:fixed），
    canvas 虽然在渲染、尺寸也对，却因为**容器零高度**永远不可见。
  修法：不再依赖 body 高度，把 canvas 直接钉在视口上
      canvas{position:fixed;left:0;top:0;width:100vw;height:100vh;display:block;z-index:0}
  修后 topAtCenter 从 HTML 变成 CANVAS，截图里第一次出现 3D 形象（面向相机的微笑立绘）。

二、顺带排掉的三个干扰（每一个都真实存在，且都曾让画面"什么都没有"）
  ① 调试层 #err 是 position:fixed + z-index:9 且无高度限制：note() 刷屏时把 canvas 整个盖住
     ⇒ 我看到的是"满屏调试文字"而不是模型。改为最多 56px 高、半透明、pointer-events:none，
     并把调试文字总量设上限；诊断完成后不再往画面上写字（关键信息只写日志）。
  ② 我把场景背景设成与页面背景同样的 #20242c ⇒ 无法分辨"canvas 在渲染"还是"canvas 是空的"，
     白白多绕了两轮；现改为 #1b2a33（略冷，能分辨）作为正式背景。
  ③ 模型一直背对相机：VRM 正面朝 +Z 而相机也在 +Z，代码里却多转了 Math.PI
     ⇒ 改为 rotation.y = 0，现在正面朝前。

三、Live2D AR 的「－ ＋」被挤出屏幕（用户反馈）
  顶栏那一排用 fillMaxWidth + weight spacer 且**不可滚动**，控件总宽超出屏幕时最右边的
  桌宠缩放「－ ＋」被直接裁掉（加了「干净」按钮后更挤）。修法：
    ① 整排改为 horizontalScroll（任何控件都够得着，不会消失）；
    ② 把「－ ＋」移到「干净」右边，落在恒定可见区；
    ③ 去掉 weight spacer（横向滚动里 width 约束无限，不能用 weight）。

四、验证（真机 MIS-AL00 / Android 12，全部以**截图**为准，不以日志为准）
  · 修前：canvas 区域一片纯色（背景色与页面同色时无法分辨），探针 topAtCenter=HTML
  · 修后：topAtCenter=CANVAS；截图里出现完整的 3D 形象（面向相机、微笑、站在地面网格上）
  · 3D 页的 place 日志保留一行（有诊断价值），逐帧标题与探针已移除

诚实说明（用户直接问的问题）：
  · 设备上这个 model.vrm 经体检器确认是 **VRM1_Constraint_Twist_Sample.vrm**（作者 pixiv Inc.，
    版本 v1.0.1，许可 https://vrm.dev/licenses/1.0/，54 根 humanoid 骨骼，12 个表情
    aa/angry/blink/happy/ih/lookUp…，3 mesh / 24951 顶点 / 13 个 MToon 材质）。
    它是一个**技术示例模型**，与"她"的任何 2D 图、衣服、表情都无关。
  · 我**从未做过 2D→3D 的转换**；此前只做了工具（vrm_inspect.py 体检器 + 渲染页），
    并把这个示例模型当占位推上设备。之前把它说得像"已完成"，是我表述不实。
  · 现在的意义是：**渲染链路已经证明可用** —— 拿她自己的 VRM（VRoid Studio 导出）替换
    files/vrm/model.vrm 即可直接显示。
"""
p = os.path.join(MAP, "_msg_3d.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
print("手机仓:", (r.stdout or r.stderr or "").splitlines()[0][:150])
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
r2 = subprocess.run(["git", "-C", MAIN, "commit", "-m", "chore(scripts): 3D 显示排查与修复脚本"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
print("桌面仓:", (r2.stdout or r2.stderr or "").splitlines()[0][:150])
for nm, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True, encoding="utf-8").stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True,
                        text=True, encoding="utf-8").stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (nm, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
