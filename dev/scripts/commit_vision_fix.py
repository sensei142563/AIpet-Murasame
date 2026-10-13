# -*- coding: utf-8 -*-
"""提交启动器 vision_source 缺省方向的修复。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

MSG = """fix(pcl): 启动器把 vision_source 缺省当"本地"，与实现相反 —— 首页显示错误已修

## 怎么发现的
上一轮为了验录屏素材 S6 去开启动器，在「总览 → 模型状态」里看到一行：
    **视觉模型：本地视觉模型（本地部署）**
但既定决策是"本地视觉：**不使用**，仅保留接口"，而且 `config.example.json` 里的
`vision_source` **已被移除**。于是回头核对，确认这行与实现相反。

## 权威口径（不是我猜的，是代码与测试写的）
```
tool/vision_local.py:14    vision_source  **"cloud"（默认）** | "local"
tool/vision_local.py:63    enum_of(_cfg().get("vision_source"), SOURCES, **"cloud"**, "vision_source")
tests/test_vision_interface.py:10   "**默认必须等于从前**：vision_source 没配 → 走云端，一个字的行为都不变"
tests/test_vision_interface.py:52   check("没配 vision_source → cloud（默认，走原链路）")
```
另已核对：用户机器的 `config.json` 里**没有** `vision_source` ⇒ 实际走云端。
而启动器 4 处都写 `or "local"` ⇒ 把"没配"当成"本地" ⇒ **首页与状态探测全反了**。

## 修了什么
`pcl_launcher/silicon_window.py` 4 处 `cfg.get("vision_source") or "local"`
→ `or "cloud"`（516 起本地服务 / 1204 预载按钮 / 1338 状态探测 / 664 首页模型卡片）。
无残留、`py_compile` 通过。

## 验证（**文本级取证，不靠截图**）
上一轮吃过亏：侧栏坐标随页面浮动、`get_window_state` 还返回过缓存帧。
这次直接用 UIA 读文本，改完重启启动器后读到：
```
[24] Text "● 视觉服务：**云端 API**"
[50] Text "deepseek-flash（通义千问 云端）"
[53] Text "**qwen-vl-plus（云端）**"        ← 与 config.json 的 vision_model_name 一致
```
改前 664 行会渲染成"本地视觉模型（本地部署）"，现在与实现、与配置三方一致。

## 回归
`tests\\run_all.py` ⇒ **总计 10 个文件 / 381 项通过 / 0 个文件失败**（含 `test_vision_interface.py` 24 项），
说明本改动与既有契约一致，没有把"接口保留"那条给改掉。

## 遗留（下一步）
`README.md` 仍把本地视觉写成**默认路径**（1215 行"本地视觉模型（默认）"、
1382 行仍列 `vision_source`、以及 4.4GB 模型下载与"本地视觉为什么会让电脑卡"整段）。
这不是本次能顺手改完的（涉及整节口径），**列出来单独处理**。
"""
p = os.path.join(MAP, "_msg_vision_fix.txt")
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
