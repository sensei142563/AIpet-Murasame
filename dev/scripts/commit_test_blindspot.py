# -*- coding: utf-8 -*-
"""提交：测试盲区修复 + 它抓出的 2 处真漏网。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

MSG = """test(vision): 修掉"标签断言"盲区 —— 它当场又抓出 2 处 vision_source 默认 local

## 为什么要动这个测试（不是为了让测试通过，是让它真的能失败）
`tests/test_vision_interface.py` 原第 76 行：
    check("设置页**没有**「视觉来源」选择器", '"vision_source", "视觉来源" not in w')
它查的标签是「**视觉来源**」，而设置页实际用的标签是「**识别来源**」。
字符串对不上 ⇒ 断言**永远成立** ⇒ "设置页不该乱暴露 vision_source"这条意图
**从未被真正检查过**，所以 `widgets.py` 里默认值写成 local（与实现缺省 cloud 相反）
能一路全绿。**改一次文案就等于把检查悄悄关掉**，这类断言不能再这么写。

## 改成了什么（加断言，不是删断言）
· 按**键名 + 取值集合 + 默认值**整体钉住：
  `_add_choice("vision_source", "识别来源", ["local", "cloud"], "cloud"`
· 防回归：不允许出现该调用的默认值为 local；
· 保留"没有本地地址/命令输入框"两条（原本就对）；
· 新增**全仓守卫**：任何文件都不得再写 `vision_source … or "local"`
  （覆盖 silicon_window.py / widgets.py / plugins_panel.py）。

## ⚠ 新断言立刻见效：抓出 2 处真漏网 + 1 处我自己的误报
真漏网（与上一提交同一个 bug，`widgets.py` 里还有两处）：
```
 881| self._set_slider("vision_source", str(cfg.get("vision_source") or "local"))   ← 载入控件状态
1028| if str(cfg.get("vision_source") or "local").strip().lower() != "local":       ← 设置页状态探测
 358| 注释"…（tool/vision_service.py + tool/chat.describe_image），默认就是 local。"
```
⇒ 三处都改成 `or "cloud"` / 更正注释（上游那套默认 local，本工程实现默认 cloud，
两套语义要分清 —— 这正是当初注释想提醒的事，但它自己写错了方向）。

我自己的误报（一并修）：第一版防回归模式写成 `["local", "cloud"], "local"`，
结果命中的是 **TTS** 的 `_add_choice("tts_type", "TTS 语音合成", ["local","cloud"], "local")`
—— 那是**合理配置**。已收窄为只盯 `vision_source` 这一处。

## 验证
```
tests/test_vision_interface.py  ⇒ 全通过（检查项 24 → 27）
tests/run_all.py                ⇒ 10 个文件 / **384 项通过** / 0 个文件失败
复核 widgets.py：`vision_source … or "local"` 残留 = 0
```
"""
p = os.path.join(MAP, "_msg_test_blindspot.txt")
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
