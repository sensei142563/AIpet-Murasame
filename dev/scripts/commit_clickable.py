# -*- coding: utf-8 -*-
"""用正确的断言重验（比 URL 子串，不比中文词），然后提交。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")
P = os.path.join(ROOT, "pcl_launcher", "silicon_window.py")

print("=== 重验（断言按 URL 子串）===")
ns = {}
src = io.open(P, encoding="utf-8", errors="replace").read()
m = re.search(r"_CONSOLE_URLS = \{[\s\S]*?\n\n\ndef balance_link_html[\s\S]*?\n\n\n", src)
exec(compile(m.group(0), "helpers", "exec"), ns)
f, g = ns["console_url_for_model"], ns["balance_link_html"]
cases = [
    ("deepseek-flash（通义千问 云端）", "阿里云无余额接口，控制台查看", "bailian.console.aliyun.com"),
    ("qwen-vl-plus（云端）", "阿里云无余额接口，控制台查看", "bailian.console.aliyun.com"),
    ("deepseek-chat（deepseek 云端）", "¥12.34", "platform.deepseek.com"),
    ("本地视觉模型（本地部署）", "本地部署，无费用", ""),
]
ok = True
for model, bal, want in cases:
    u = f(model)
    h = g(bal, model, "#e0603a")
    good = (want in u) if want else (u == "" and "<a " not in h)
    ok = ok and good
    print("   %s %-32s → %-44s 期望含 %r" % ("✓" if good else "✗", model[:32],
                                            u or "（不链接）", want or "不链接"))
print("   ⇒", "全部符合预期 ✓" if ok else "仍有不符 ✗")
if not ok:
    sys.exit(1)

MSG = """feat(launcher): 「模型状态」那一行做成可点 —— 点开就用浏览器打开对应控制台

## 用户要求（原话）
"把那行做成**可点**的 ⇒ 点一下用浏览器打开对应控制台（阿里云百炼 / DeepSeek 余额页）✓可行"

## 做法
1. 新增两个**纯函数**（好测）：
   - `console_url_for_model(model_text)`：按那两行的文字推断该开哪个控制台
   - `balance_link_html(text, model_text, color)`：把余额文字包成 `<a>`
   用"从文字推断"而不是改数据流 —— 那两行的文案里本来就带供应商，最稳。
2. 余额标签（QLabel）允许外链：`setOpenExternalLinks(True)` + `setTextFormat(Qt.RichText)`
   + 手型光标 + tooltip 显示完整网址。
   （用 QLabel 原生外链，而不是自己接 mousePressEvent —— 不会在无浏览器时崩。）
3. `_apply_models` 改成"**先算颜色 → 再写链接**"：保留原有的"余额 <5 标红 / 本地部署标绿 /
   其余灰"，并把颜色显式传给链接（Qt 富文本对 `color:inherit` 支持有限，
   不显式给就会变成默认蓝、跟主题脱节）。链接加下划线，看得出能点。

## 自测抓到一个真 bug（已修）
```
第一版判断顺序：先看 "deepseek" ⇒ `deepseek-flash（通义千问 云端）` 被判成 DeepSeek ✗
```
模型名里带 deepseek，但**云端实际走的是通义千问** ⇒ 必须**供应商关键词优先于模型名**。
修后重验：
```
✓ deepseek-flash（通义千问 云端） → https://bailian.console.aliyun.com/
✓ qwen-vl-plus（云端）          → https://bailian.console.aliyun.com/
✓ deepseek-chat（deepseek 云端） → https://platform.deepseek.com/usage
✓ 本地视觉模型（本地部署）        → 不链接（保持纯文本）
```
（第二次重验时我自己的**断言写错了**——拿中文词去比 URL——已改正为比 URL 子串。）

## 仍需用户目视
无头环境看不到界面：**链接颜色/下划线/手型光标**这些观感要你开一下启动器确认。
"""
p = os.path.join(MAP, "_msg_clickable.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:170])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))

print()
print("=== 全量自检 ===")
r = subprocess.run([os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe"),
                    os.path.join(ROOT, "tests", "run_all.py")],
                   cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=1800)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n")[-4:]:
    print("   " + l.strip()[:120])
