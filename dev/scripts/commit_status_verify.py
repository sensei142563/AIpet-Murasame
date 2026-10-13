# -*- coding: utf-8 -*-
"""收尾：停掉启动器 + 提交 S6 的接线验证记录。"""
import io
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

print("=== 停掉启动器 ===")
for pid in ("1428",):
    r = subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    print("   pid %s → %s" % (pid, (r.stdout or r.stderr or "").strip()[:70]))
time.sleep(1)
r = subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-Process | Where-Object { $_.MainWindowTitle -like '*启动器*' } | "
                    "Select-Object -ExpandProperty Id"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
left = [x for x in (r.stdout or "").split() if x.strip()]
print("   仍在跑的启动器窗口:", left or "无 ✓")

D = os.path.join(ROOT, "dev", "docs", "启动器状态页接线验证-2026-10-13.md")
io.open(D, "w", encoding="utf-8", newline="\n").write("""# 录屏素材 S6 的前置验证：启动器「状态」页

> 操作单里的 S6 是"启动器 → 侧栏『状态』页"，而**这一项是本轮新加的功能**，
> 此前只跑过单测、**没亲眼看过**。录屏前先验，免得现场才发现是空白页。

## 一、实际把启动器跑起来（真机、真窗口）
```
启动：启动启动器.bat（cmd 拉起）→ PID 1428  python  "AIpet 丛雨桌宠 · 启动器"
前台截图：侧栏完整显示 总览 / 桌宠 / 状态 / 记忆 / 提示词 / 插件 / 主题 / 设置
```
⇒ **「状态」入口确实在侧栏里**（这是本轮改动最担心的一点，已确认）。

## 二、点开其它页，确认侧栏切换机制本身是通的
用 UIA 的 Invoke 分别切到「提示词」与「记忆」两页，**都正常渲染**：
- 提示词：短文本/长文本两个编辑区、角色下拉、保存/重新加载按钮都在；
- 记忆：记忆文件清单（短文本 156 条 / 长文本 24 条 / 私聊若干）、预览区、备份与清空按钮、
  QQ 离线补拉状态，都在。
⇒ 侧栏 → 内容页的**切换机制正常**，不是"只有入口没有内容"。

## 三、为什么没给「状态」页的截图：坐标不可靠
侧栏各项的 **y 坐标随当前页面的布局高度浮动**（同一个「状态」在两次截图里差 28px），
而且 `get_window_state` 几次返回了**同一张缓存帧**（sha256 相同），
所以"盲点坐标"会点到相邻项上。要稳定点击必须拿到元素的 `element_token`，
而当前工具返回里没有该字段。
**没有拿到干净截图，就不假装拿到了** —— 这一条如实记下。

## 四、改用代码级确证（比"看起来对"更硬）
```
silicon_window.py
   56| NAV = [ … ("status", "", "状态", "状态 · 习惯 · 记忆 · 提醒") ]
  164| def _status_page_enabled() -> bool:      # 读 config 的 status_page_enabled，默认开
  172|     .get("status_page_enabled"), True)
 2084| # 「状态」页可以在设置里关掉 → 侧栏就不建这一项
 2085| if key == "status" and not _status_page_enabled():
 2144| self._host_page("status", _mk("pcl_launcher.status_panel", "PCLStatusPanel"))
 2906| _q = ["plugins", "pets", "status", "memory", "settings", "prompt", "themes"]
 2907| if not _status_page_enabled():
 2908|     _q = [k for k in _q if k != "status"]   # 关掉了就别预热它
status_panel.py
   class PCLStatusPanel      （内部用 QTabWidget —— 就是那四个页签：状态/习惯/记忆/提醒）
导入级检查（venv 解释器，不建窗口）：status_panel 导入成功，rc=0，
   QApplication / QTabWidget / QScrollArea 等全部就位。
```

## 五、结论与遗留
- ✅ **入口在、接线在、面板类在、能导入** —— S6 不是"空白页"风险；
- ⚠ **「状态」页的视觉外观仍未被亲眼确认**（缓存帧 + 坐标浮动导致的取证失败，已如实记录）；
- 建议：录 S6 时顺手点一下「状态」页 —— 如果它真的空白，**当场就能发现并告诉我**，
  而不是等到 PPT 做完了才发现。

## 六、顺带发现（与本轮无关但值得记）
启动器「总览 → 模型状态」里显示 **"视觉模型：本地视觉模型（本地部署）"**。
但既定决策是 **"本地视觉：不使用，仅保留接口"**，且 `config.example.json` 里的
`vision_source` 已被移除。这行显示可能已经过时/误导，**建议下一步核对**
（它出现在启动器首页，最容易被人看到）。
""")
print("✓ 已写验证记录 dev/docs/启动器状态页接线验证-2026-10-13.md")

MSG = """docs: 录屏 S6 的前置验证 —— 启动器「状态」页入口与接线确认（附一条新发现）

操作单里的 S6 是"启动器 → 侧栏『状态』页"，而这一项是本轮新加的功能，
此前只跑过单测、没亲眼看过。录屏前先验，免得现场才发现是空白页。

## 一、真机跑起来看了
`启动启动器.bat` → PID 1428「AIpet 丛雨桌宠 · 启动器」；
侧栏完整：总览 / 桌宠 / **状态** / 记忆 / 提示词 / 插件 / 主题 / 设置
⇒ **「状态」入口确实在**（本轮最担心的一点，已确认）。

## 二、侧栏切换机制本身也是通的
用 UIA Invoke 切到「提示词」「记忆」两页，**都正常渲染**（前者有双编辑区与角色下拉，
后者有记忆文件清单/预览/备份清空/QQ 离线补拉）⇒ 不是"只有入口没有内容"。

## 三、⚠ 没拿到「状态」页截图，如实记下原因
侧栏各项的 y 坐标**随当前页面布局浮动**（同一个「状态」两次截图差 28px），
且 `get_window_state` 几次返回**同一张缓存帧**（sha256 相同）⇒ 盲点坐标会点到相邻项。
要稳定点击需元素的 `element_token`，当前工具返回里没有该字段。
**拿不到干净截图就不假装拿到了。**

## 四、改用代码级确证（比"看起来对"更硬）
```
silicon_window.py
   56| NAV = [ … ("status", "", "状态", "状态 · 习惯 · 记忆 · 提醒") ]
  164| def _status_page_enabled() -> bool:      # 读 config，默认开
 2085| if key == "status" and not _status_page_enabled():   # 关掉就不建这一项
 2144| self._host_page("status", _mk("pcl_launcher.status_panel", "PCLStatusPanel"))
 2906-2908| 预热列表含 "status"，关掉时剔除
status_panel.py：class PCLStatusPanel（内部 QTabWidget = 状态/习惯/记忆/提醒 四页签）
导入级检查（venv，不建窗口）：导入成功 rc=0，Qt 组件全部就位。
```

## 五、结论与遗留
✅ 入口在、接线在、面板类在、能导入 ⇒ S6 不存在"空白页"风险；
⚠ 「状态」页的**视觉外观仍未被亲眼确认**；
建议录 S6 时顺手点一下，若真空白当场就能发现。

## 六、顺带发现（建议下一步核对）
启动器「总览 → 模型状态」显示 **"视觉模型：本地视觉模型（本地部署）"**，
但既定决策是"本地视觉：不使用，仅保留接口"，且 `config.example.json` 的 `vision_source` 已移除。
这行显示可能已过时/误导，且出现在**启动器首页**（最容易被看到）。
"""
p = os.path.join(MAP, "_msg_status_verify.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:170])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
