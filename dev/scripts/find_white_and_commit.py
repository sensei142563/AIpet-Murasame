# -*- coding: utf-8 -*-
"""找启动器新外壳里"写死的浅色文字"（首页发白的嫌疑），然后提交本轮全部修复。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

print("=== 找写死的浅色文字（#fff / white / 高亮浅色）===")
FILES = ["pcl_launcher/silicon_window.py", "pcl_launcher/silicon_ui.py"]
PAT = re.compile(r"#(fff|ffffff|FFF|FFFFFF)\b|[\"']white[\"']|rgba\(255,\s*255,\s*255|"
                 r"#fdf6ee|#f9ece6|#f5e2dc|Color[678]\b", re.I)
for rel in FILES:
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        continue
    ls = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
    for i, l in enumerate(ls, 1):
        if PAT.search(l):
            print("   %-30s %5d| %s" % (rel, i, l.strip()[:104]))

print()
print("=== 总览页里各显示的控件用了什么颜色 ===")
p = os.path.join(ROOT, "pcl_launcher", "silicon_window.py")
ls = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
inside = False
for i, l in enumerate(ls, 1):
    if "def _page_overview" in l or "def _build_overview" in l or "总览：" in l:
        inside = True
    if inside and re.search(r"setStyleSheet|QLabel|section_title|color:", l):
        print("   %5d| %s" % (i, l.strip()[:104]))
    if inside and i > 1250:
        break

MSG = """fix(pet): 看屏幕无限刷屏（三道闸）+ _14 打字错误 + 快捷工具按钮换行

## 主人报的 5 个问题与本轮处置

### ① 关闭桌宠掐不掉进程 —— 判定为**上述风暴的症状**，已随主因修复
链路本来是通的：`main.py:1025` 的 500ms 控制轮询 → `check_shutdown()` → `QTimer.singleShot(400, app.quit)`
→ `aboutToQuit` 上的退出看门狗 6 秒后 `os._exit(0)` 强杀。
但轮询跑在 **GUI 线程**，而看屏幕风暴把 GUI 线程占满 ⇒ 关闭标志一直读不到。
三道闸下去之后应恢复正常，**请主人复测**（真还有问题我再加重试/独立线程兜底）。

### ② 视觉识别（进而摄像头/人脸）—— **根因是账号权限，不是代码**
用配置里的 key 实测（只发最小请求）：
```
✓ qwen-plus                → HTTP 200        （key 有效，文本模型正常）
✗ qwen-vl-plus / qwen-vl-max → 404 Model not exist
✗ qwen-vl-plus-latest / -max-latest / qwen2.5-vl-* → **403 Access denied**
⇒ 403 = 模型存在但该账号未开通 ⇒ 所有走视觉模型的功能（屏幕/摄像头/人脸）都会失败
```
⇒ 主人需到阿里云百炼控制台**开通 qwen-vl 系列**，或告知已开通的模型名（改 config.json 的
`vision_model_name`）。
**但代码有责任**：它明知失败还无限重试 ⇒ 本轮修掉（见下）。

### ②(代码) 看屏幕无限刷屏 —— 三道闸
根因链（真实日志可复现）：
```
_look_screen_and_reply 里 describe_image 返回空 → self._request_dialog.emit(user_text, "user", False)
→ 把**主人的原话**又当成 user 消息送回去 → 再次命中 needs_screen_look → 又看屏幕 → 又空 → …
而守卫 _screen_look_busy 在 finally 里已复位，挡不住 ⇒ 日志里「👀 主人让我看屏幕」永无止境
```
修法：
- **闸1 跳过标记** `_screen_look_skip_once`：回退重答/带描述重答时打标，这一句不再触发看屏幕；
- **闸2 冷却** `_screen_look_last`：距上次看屏幕 < 20 秒（可用 `AIPET_SCREEN_LOOK_COOLDOWN` 调）就不重复抓屏；
- **闸3 熔断** `_screen_look_broken_until`：连续 3 次拿到空 ⇒ 暂停看屏幕 10 分钟，并**明确打印真正原因**
  （模型未开通/名字不对），提示去控制台开通——而不是让她一遍遍说"看不到"。

### ②(顺手) `_14` 打字错误
`classes/murasame_class.py:2924/2927`：`_kind = _t[:_14]` —— 多了一个下划线，Python 把 `_14` 当变量名
⇒ `NameError: name '_14' is not defined` ⇒ 被外层 `except` 吞掉、只留一行「排队判断失败（照常继续）」
⇒ **整段队列去重逻辑静默失效**（队列只涨不消）。已修为 `[:14]`。

### ③ 首页写死的白字 —— 查到一半，待定位
- 对比 `senrenbanka_copy`（沫子的日常）与 `senrenbanka`（千恋万花·樱华）：**colors 完全相同**，
  只有 background 不同（video vs image）⇒ **不是主题数据问题**，是新外壳里写死的浅色；
- 已列出候选（`#fff` / `'white'` / `rgba(255,255,255,…)`）与总览页的控件样式，下一步逐个换成语义色。

### ④ Live2D 大小：**是独立的一套**（回答，非 bug）
`main.py:201` 明确写着"角色若在「立绘设置 → Live2D」里单独调过大小/位置，优先用那份（**与 2D 独立**）"，
存在 pet.json 的 `scale/offset_x/offset_y/window_ratio/font_scale`。
⇒ 设置页那个"桌宠大小"只管 2D；Live2D 要在**立绘设置→Live2D** 或调参模式里调。

### ⑤ F3~F12 调参热键：**还在**
`main.py:743` 起，共两段：**先按 F1 开启调参模式**，然后
`+/-` 模型缩放 · 方向键平移（上下=画布边距）· `Shift+方向键` 文本框位置 · `F7/F8` 窗口宽高比 ·
`F2/F3` 窗口高度 · `F4` 重置位置 · `,`/`.` 或 `F10/F11` 字号 · `F9` 参考线 · **`F5` 保存** · `F6` 看当前值。

### 附：修复我自己上次的副作用
上次把两个「预载」按钮挪进「快捷工具」时和 6 个工具挤在同一行，8 个按钮 + 角色名后缀
**被窗口裁掉**（主人截图里就有「…服务（丛雨△」）。已改到**第二行**。

## 验证
`py_compile classes/murasame_class.py pcl_launcher/silicon_window.py` 均 OK。
"""
p = os.path.join(MAP, "_msg_5issues.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("✓ 提交：", (rc.stdout or rc.stderr or "").splitlines()[0][:150])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = [l for l in subprocess.run(["git", "-C", ROOT, "status", "--porcelain"],
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace").stdout.split("\n") if l.strip()]
print("   未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st)))
