# -*- coding: utf-8 -*-
"""提交视觉修复，并**明确纠正**上一轮"账号没视觉权限"的错误结论。"""
import io
import json
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

MSG = """fix(vision): 视觉模型名改回 qwen3-vl-plus（旧名已下线）+ 本地视觉两项默认清空

## ⚠ 先纠正我上一轮的错误结论
上一轮我在 `d734eb2` 的提交信息里写「视觉 403/404 ⇒ **阿里云账号没开通视觉模型**」——**这是错的**。
我只测了旧模型名就下了结论，没测新名字。主人当即指出两点，**都是对的**：
1. "qwen-vl 不是停用了？我记得之前还让你改成新模型来着"；
2. "我账号不应该没有视觉权限"。

## 实测（用主人的 key，含新名字）
```
✓ qwen3-vl-plus   → HTTP 200   ← **可用！**
✗ qwen-vl-plus / qwen-vl-max → 404 Model not exist（**已下线**）
✗ qwen2.5-vl-7b / 32b        → 403（旧系列未开通）
✓ qwen-plus       → 200
✗ qwen3-vl-flash  → 404（这个名字不存在，**已从下拉框移除**）
```
**端到端验证（真发一张图）**：
```
✓✓ qwen3-vl-plus 识别成功：「图中是一个红色边框的白色矩形框，中央写有单词"Alpet"」
⇒ 视觉链路本身是通的，屏幕/摄像头/人脸都能用 —— 之前失败纯粹是**模型名写的是已下线的旧名**。
```

## 证据：确实是被覆盖回退了
```
docs/handover/2026-09-24.md:443  「用户 config.json … vision_model_name: qwen3-vl-plus」
README.md:1390                   「vision_model_name｜默认 qwen3-vl-plus」
README.md:1541                   「🔧 顺手修复：不再使用已停服的 qwen-vl-plus」
pcl_launcher/widgets.py 下拉选项里本来就有 qwen3-vl-plus
⇒ 文档/下拉框都指向新名，**只有 config.json 是旧名** ⇒ 合并时被回退
（config.json 未被 git 跟踪 ⇒ 查不到历史；这也顺带确认了 **API key 从未进过库** ✓）
```

## 改了什么
1. `config.json`：`vision_model_name` qwen-vl-plus → **qwen3-vl-plus**；
2. `config.example.json`：模型名 → qwen3-vl-plus；`local_api.vision` 与 `vision_local_model_dir` → **空**；
3. `pcl_launcher/widgets.py`：
   - 设置页两项的默认值 `http://127.0.0.1:28460/describe` 与
     `D:\\下载\\AI桌宠\\vision\\Qwen2-VL-2B-Instruct` → **空**
     （主人："本地视觉默认不使用，那两项没有的话默认为空"）；
   - 载入配置时的默认值同样改空，视觉模型默认名 → qwen3-vl-plus；
   - 下拉框移除实测不存在的 `qwen3-vl-flash` 与已下线的两个旧名。

## 关于「是不是往主人电脑里塞了千问视觉小模型」
**没有。** 已核实：
```
D:\\下载\\AI桌宠\\vision\\Qwen2-VL-2B-Instruct  → **不存在**
D:\\下载\\AI桌宠\\vision                        → 不存在
D:\\下载\\AI桌宠                               → 不存在
```
那个路径只是**界面上的示例默认值**（`widgets.py` + `config.example.json`），
而且早在 2026-10-13 就已拍板「**本地视觉：不使用，仅保留接口**」（见 dev/docs/状态窗融合方案…）。
本轮把这些示例默认值**清空**，界面上不会再显示一个机器上不存在的目录。

## ⚠ 我自己闯的祸（已修）
替换那两处默认值时，我的 `replace` 把字符串的**开头引号**一起删掉了 ⇒
`widgets.py` 出现 `SyntaxError: unterminated string literal`（会让启动器直接起不来）。
发现后立刻按原文修回，并 `py_compile` 通过、全量自检 389 项通过。

## 主人要做的
**重启桌宠**（config.json 是运行时读的）⇒ 屏幕识别 / 摄像头识别 / 人脸识别应该都恢复。

## 验证
`py_compile pcl_launcher/widgets.py` OK；全量自检 10 个文件 / 389 项 / 0 失败。
"""
p = os.path.join(MAP, "_msg_vision2.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("✓ 提交：", (rc.stdout or rc.stderr or "").splitlines()[0][:150])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = [l for l in subprocess.run(["git", "-C", ROOT, "status", "--porcelain"],
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace").stdout.split("\n") if l.strip()]
print("   未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st)))
print()
print("=== 确认最终配置 ===")
cfg = json.load(io.open(os.path.join(ROOT, "config.json"), encoding="utf-8", errors="replace"))
for k in ("vision_model_name", "vision_source", "vision_local_url", "vision_local_command"):
    print("   %-24s %r" % (k, cfg.get(k, "(无)")))
ex = io.open(os.path.join(ROOT, "config.example.json"), encoding="utf-8",
             errors="replace").read()
for key in ("vision_model_name", "vision_local_model_dir"):
    m = re.search(r'"%s"\s*:\s*"([^"]*)"' % key, ex)
    print("   example.%-22s %r" % (key, m.group(1) if m else "(找不到)"))
m2 = re.search(r'"vision"\s*:\s*"([^"]*)"', ex)
print("   example.local_api.vision    %r" % (m2.group(1) if m2 else "(找不到)"))
