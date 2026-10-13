# -*- coding: utf-8 -*-
"""修两处：
  ① 判断顺序错误：deepseek-flash（通义千问 云端）应判为 qwen ⇒ **供应商关键词优先于模型名**
  ② 链接颜色：Qt 富文本对 color:inherit 支持有限，改成显式颜色（可读 + 保留"余额少标红"）
"""
import io
import os
import py_compile
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
P = os.path.join(ROOT, "pcl_launcher", "silicon_window.py")
t = io.open(P, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")

# ---------- ① 判断顺序：先供应商关键词，再模型名 ----------
OLD1 = '''def console_url_for_model(model_text: str) -> str:
    """按模型名/来源文字推断要打开哪个控制台；判断不了就返回空串（那就保持纯文本）。"""
    t = str(model_text or "").lower()
    if "deepseek" in t:
        return _CONSOLE_URLS["deepseek"]
    if ("通义" in t) or ("qwen" in t) or ("阿里" in t) or ("百炼" in t) or ("dashscope" in t):
        return _CONSOLE_URLS["qwen"]
    return ""'''
NEW1 = '''def console_url_for_model(model_text: str) -> str:
    """按模型名/来源文字推断要打开哪个控制台；判断不了就返回空串（那就保持纯文本）。

    ⚠ 顺序要紧：**先看供应商关键词，再看模型名**。
      反例（自测抓到）：`deepseek-flash（通义千问 云端）` —— 模型名里带 deepseek，
      但云端实际走的是通义千问 ⇒ 该打开阿里云百炼，而不是 DeepSeek 用量页。
    """
    t = str(model_text or "").lower()
    if ("通义" in t) or ("qwen" in t) or ("阿里" in t) or ("百炼" in t) or ("dashscope" in t):
        return _CONSOLE_URLS["qwen"]
    if "deepseek" in t:
        return _CONSOLE_URLS["deepseek"]
    return ""'''
if OLD1 in t:
    t = t.replace(OLD1, NEW1, 1)
    print("✓ ① 判断顺序已改为「供应商优先」")
else:
    print("✗ ① 锚点未命中（判断函数）")

# ---------- ② 链接显式颜色 ----------
OLD2 = '''def balance_link_html(text: str, model_text: str) -> str:
    """把余额文字包成可点链接（判断不出控制台就原样返回纯文本）。"""
    url = console_url_for_model(model_text)
    if not url:
        return str(text)
    esc = (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    # 颜色交给外层样式表（标红/绿/灰都由 _apply_models 决定），这里只管"能点"
    return '<a href="%s" style="text-decoration:none; color:inherit;">%s</a>' % (url, esc)'''
NEW2 = '''def balance_link_html(text: str, model_text: str, color: str = "") -> str:
    """把余额文字包成可点链接（判断不出控制台就原样返回纯文本）。

    color：显式给链接颜色（Qt 富文本对 `color:inherit` 支持有限，不给就会是默认蓝）。
           余额不足时调用方会传红色，保持"余额少标红"的提醒。
    """
    url = console_url_for_model(model_text)
    if not url:
        return str(text)
    esc = (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    style = "text-decoration:underline;"
    if color:
        style += " color:%s;" % color
    return '<a href="%s" style="%s">%s</a>' % (url, style, esc)'''
if OLD2 in t:
    t = t.replace(OLD2, NEW2, 1)
    print("✓ ② 链接改为显式颜色 + 下划线（看得出能点）")
else:
    print("✗ ② 锚点未命中（链接函数）")

# ---------- ③ _apply_models：先算颜色，再写链接 ----------
OLD3 = '''                name_lbl.setText(str(model))
                # ★ 可点：包成指向对应控制台的链接（判断不出控制台时自动退回纯文本）
                bal_lbl.setText(balance_link_html(str(bal), str(model)))
                if balance_link_html(str(bal), str(model)) != str(bal):
                    bal_lbl.setToolTip("点击打开控制台（余额 / 用量在那里看）：%s"
                                       % console_url_for_model(str(model)))
                # 余额少的标红提醒（本地部署/查询失败保持灰色）
                warn = False
                s = str(bal)
                if s.startswith(("¥", "$")):
                    try:
                        warn = float(s[1:]) < 5.0
                    except Exception:
                        warn = False
                bal_lbl.setStyleSheet(
                    f"color: {'#e0603a' if warn else '#3d9e6a' if s and not warn and '无费用' in s else Gray2.name()};"
                    f" font-size: 13px; font-family: '{silicon_ui.M.font}';")'''
NEW3 = '''                name_lbl.setText(str(model))
                # 余额少的标红提醒（本地部署/查询失败保持灰色）
                warn = False
                s = str(bal)
                if s.startswith(("¥", "$")):
                    try:
                        warn = float(s[1:]) < 5.0
                    except Exception:
                        warn = False
                color = ('#e0603a' if warn else
                         '#3d9e6a' if s and not warn and '无费用' in s else Gray2.name())
                # ★ 2026-10-14：包成可点链接（点开=对应控制台）。
                #   颜色显式传给链接，免得 Qt 富文本把主题色覆盖成默认蓝。
                bal_lbl.setText(balance_link_html(str(bal), str(model), color))
                _u = console_url_for_model(str(model))
                if _u:
                    bal_lbl.setToolTip("点击打开控制台（余额 / 用量在那里看）：\\n%s" % _u)
                else:
                    bal_lbl.setToolTip("")
                bal_lbl.setStyleSheet(
                    f"color: {color};"
                    f" font-size: 13px; font-family: '{silicon_ui.M.font}';")'''
if OLD3 in t:
    t = t.replace(OLD3, NEW3, 1)
    print("✓ ③ _apply_models 已改为「先算颜色 → 再写链接」")
else:
    print("✗ ③ 锚点未命中（_apply_models）")

io.open(P, "w", encoding="utf-8", newline="\n").write(t)
try:
    py_compile.compile(P, doraise=True)
    print("✓ py_compile OK")
except Exception as e:
    print("✗ py_compile:", e)
    sys.exit(1)

print()
print("=== ④ 重跑纯函数自测（重点看第一例修没修好）===")
ns = {}
src = io.open(P, encoding="utf-8", errors="replace").read()
m = re.search(r"_CONSOLE_URLS = \{[\s\S]*?\n\n\ndef balance_link_html[\s\S]*?\n\n\n", src)
exec(compile(m.group(0), "helpers", "exec"), ns)
f, g = ns["console_url_for_model"], ns["balance_link_html"]
cases = [
    ("deepseek-flash（通义千问 云端）", "阿里云无余额接口，控制台查看", "该→百炼"),
    ("qwen-vl-plus（云端）", "阿里云无余额接口，控制台查看", "该→百炼"),
    ("deepseek-chat（deepseek 云端）", "¥12.34", "该→DeepSeek"),
    ("本地视觉模型（本地部署）", "本地部署，无费用", "不该链接"),
]
ok = True
for model, bal, want in cases:
    u = f(model)
    h = g(bal, model, "#e0603a")
    good = (
        ("百炼" in u) if "百炼" in want else
        ("deepseek" in u) if "DeepSeek" in want else
        (u == "")
    )
    ok = ok and good
    print("   %s %-32s → %-46s %s" % ("✓" if good else "✗", model[:32], u or "（不链接）", want))
print("   ⇒", "全部符合预期 ✓" if ok else "仍有不符 ✗")
