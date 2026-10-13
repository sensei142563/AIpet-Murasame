# -*- coding: utf-8 -*-
"""把「模型状态」的余额那一行做成**可点链接**（点开浏览器到对应控制台）。
   供应商从**模型名文字**推断（"通义千问/qwen/阿里" → 百炼控制台；"deepseek" → DeepSeek 用量页），
   这样不用改数据流，也不会因为上游字段变化而失效。
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

# ---------- ① 模块级：控制台地址 + 两个纯函数（可单测） ----------
ANCHOR = 'def _balance_for(provider: str, key: str) -> str:'
HELPERS = '''# ★ 2026-10-14（主人要求）：模型状态那一行做成**可点**的 —— 点一下用浏览器打开对应控制台。
#   为什么用"从文字推断"而不是走数据流：那两行的文案里本来就带供应商
#   （如 "deepseek-flash（通义千问 云端）"），据此判断最稳，上游字段变了也不会失效。
_CONSOLE_URLS = {
    "deepseek": "https://platform.deepseek.com/usage",
    "qwen": "https://bailian.console.aliyun.com/",
}


def console_url_for_model(model_text: str) -> str:
    """按模型名/来源文字推断要打开哪个控制台；判断不了就返回空串（那就保持纯文本）。"""
    t = str(model_text or "").lower()
    if "deepseek" in t:
        return _CONSOLE_URLS["deepseek"]
    if ("通义" in t) or ("qwen" in t) or ("阿里" in t) or ("百炼" in t) or ("dashscope" in t):
        return _CONSOLE_URLS["qwen"]
    return ""


def balance_link_html(text: str, model_text: str) -> str:
    """把余额文字包成可点链接（判断不出控制台就原样返回纯文本）。"""
    url = console_url_for_model(model_text)
    if not url:
        return str(text)
    esc = (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    # 颜色交给外层样式表（标红/绿/灰都由 _apply_models 决定），这里只管"能点"
    return '<a href="%s" style="text-decoration:none; color:inherit;">%s</a>' % (url, esc)


'''
if "_CONSOLE_URLS" not in t and ANCHOR in t:
    t = t.replace(ANCHOR, HELPERS + ANCHOR, 1)
    print("✓ ① 已加 console_url_for_model / balance_link_html（纯函数，易测）")
else:
    print("· ① 已存在或锚点未命中")

# ---------- ② 建标签时允许外链 + 手型光标 ----------
OLD2 = """            bal_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row.addWidget(tag)"""
NEW2 = """            bal_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            # ★ 2026-10-14：这一行是可点的（点开=对应控制台）。QLabel 原生支持外链，
            #   比自己接 mousePressEvent 稳（也不会在只读/无浏览器时崩）。
            bal_lbl.setOpenExternalLinks(True)
            bal_lbl.setTextFormat(Qt.RichText)
            bal_lbl.setCursor(Qt.PointingHandCursor)
            bal_lbl.setToolTip("点击打开控制台（余额 / 用量在那里看）")
            row.addWidget(tag)"""
if OLD2 in t:
    t = t.replace(OLD2, NEW2, 1)
    print("✓ ② 余额标签已允许外链 + 手型光标 + 提示")
else:
    print("✗ ② 锚点未命中（建标签处）")

# ---------- ③ 显示时包成链接（保留原有的标红/绿/灰判定） ----------
OLD3 = """                name_lbl.setText(str(model))
                bal_lbl.setText(str(bal))"""
NEW3 = """                name_lbl.setText(str(model))
                # ★ 可点：包成指向对应控制台的链接（判断不出控制台时自动退回纯文本）
                bal_lbl.setText(balance_link_html(str(bal), str(model)))
                if balance_link_html(str(bal), str(model)) != str(bal):
                    bal_lbl.setToolTip("点击打开控制台（余额 / 用量在那里看）：%s"
                                       % console_url_for_model(str(model)))"""
if OLD3 in t:
    t = t.replace(OLD3, NEW3, 1)
    print("✓ ③ _apply_models 已改为写链接")
else:
    print("✗ ③ 锚点未命中（_apply_models）")

io.open(P, "w", encoding="utf-8", newline="\n").write(t)
try:
    py_compile.compile(P, doraise=True)
    print("✓ py_compile OK")
except Exception as e:
    print("✗ py_compile:", e)
    sys.exit(1)

# ---------- ④ 纯函数自测 ----------
print()
print("=== ④ 纯函数自测：该打开哪个控制台 ===")
ns = {}
src = io.open(P, encoding="utf-8", errors="replace").read()
m = re.search(r"_CONSOLE_URLS = \{[\s\S]*?\n\n\ndef balance_link_html[\s\S]*?\n\n\n", src)
if m:
    exec(compile(m.group(0), "silicon_window.py:helpers", "exec"), ns)
    f, g = ns["console_url_for_model"], ns["balance_link_html"]
    cases = [
        ("deepseek-flash（通义千问 云端）", "阿里云无余额接口，控制台查看"),
        ("qwen-vl-plus（云端）", "阿里云无余额接口，控制台查看"),
        ("deepseek-chat（deepseek 云端）", "¥12.34"),
        ("本地视觉模型（本地部署）", "本地部署，无费用"),
    ]
    for model, bal in cases:
        u = f(model)
        h = g(bal, model)
        print("   模型=%-30s → %s" % (model[:30], u or "（不链接）"))
        print("        余额文字 → %s" % h[:96])
else:
    print("   ✗ 抠函数失败")
