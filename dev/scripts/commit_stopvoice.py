# -*- coding: utf-8 -*-
"""跑全量并提交 stop_voice 默认值 + 2D 字体判据改判。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")
MAP = os.path.join(ROOT, "dev", "merge-map")

print("=== 全量 ===")
r = subprocess.run([VENV, os.path.join("tests", "run_all.py")], cwd=ROOT, capture_output=True,
                   text=True, encoding="utf-8", errors="replace", timeout=1800)
out = (r.stdout or "") + (r.stderr or "")
for l in out.split("\n"):
    if re.match(r"\s*test_\w+\.py\s+-?\d", l) or "总计" in l:
        print("   " + l.strip()[:135])

MSG = """fix(pet): pause_all_ai 默认不停语音 + 2D 字体判据改判；0930b 6 项 → 1 项

一、`pause_all_ai(stop_voice=...)` 默认值反了（真 bug）
  · 签名由 `stop_voice: bool = True` 改为 **`False`**。
    注释里本来就写着它该是 False：「stop_voice=False 用于『窗口获得焦点』这类被动触发：
    只暂停自动行为（截图/空闲检测），不掐断正在念的那句话」，而且说明了用户反馈的症状：
    「以前一律 QSound.stop()：点她、点对话框、系统把焦点切过来都会走到这里 →
      正在念的句子被半路掐掉，而句子队列照常往下走，听起来就是『有的句子/几个字没声』，
      而且是随机的」。默认值却还是 True ⇒ 等于那个 bug 没修掉。
  · `focusInEvent` 的调用由 `self.pause_all_ai(stop_voice=False)` 改为 **`self.pause_all_ai()`**
    （走默认，语义更直白；测试也是查这个形状）。
  · 全仓调用点核对：只剩两处 —— 1209 行（focusInEvent，无参 = 不停语音）与
    1485 行（用户主动输入，**显式** `stop_voice=True`），语义正确。

二、2D 字体判据改判（与本地视觉那次同类的"判据与有意修复相反"）
  测试原本要求源码里是 `QFont(self._font_family, max(8, int(scaled_font_size)))`，
  但本项目**有意**改成了 `QFont(self._resolve_pet_font(), ...)` —— 旧写法正是
  「主题页换了界面字体，桌宠对话框的字还是老样子（用户反馈『没变成』）」那个 bug 的根因
  （代码注释里写着：`self._font_family` 的初值是写死的 "思源黑体Bold.otf"，
  根本没走 `_resolve_pet_font()`）。想要"真加载字体 + 像素字号"的老做法可开 `text_font_native`。
  ⇒ 判据改为断言**修好后的写法**，并把理由写进测试注释。

验证：`tests/test_bugfix_0930b.py` 失败项 **6 → 1**（仅剩「四套衣服画出来各不相同」，
其排查结论见 dev/docs/换装不生效-排查结论-2026-10-13.md：解析层正常，
是测试那次把**固定不变的 `first_portrait`** 当 layers 传进去，绕过了解析入口）。
"""
p = os.path.join(MAP, "_msg_stopvoice.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:160])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
