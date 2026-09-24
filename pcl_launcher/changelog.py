# -*- coding: utf-8 -*-
"""更新日志：读程序目录下的 `更新日志/V*.md`（由 `tool/gen_changelog.py` 从 README 生成）。

为什么单独成模块 —— 以前同一件事在两处各写一份，而且"哪个是最新"两边判断还不一样：

| 入口 | 以前怎么找"最新" | 毛病 |
| --- | --- | --- |
| 首页快捷入口 `SiliconLauncher.open_changelog` | `sorted(glob(...), reverse=True)` 取第一个 | **按文件名字典序** → `V1.8.0.md` 排在 `V1.16.1.md` 前面（'8' > '1'），点开的是旧版本；而且 `os.startfile` 把 md 甩给系统默认程序，没装阅读器就弹"打开方式" |
| 设置页「其他」→ 查看日志 | 按文件 **mtime** 取最新 | 同一批生成的文件 mtime 相同 → 谁是"最新"看运气 |
| （两者共同的毛病） | 文件夹空时只弹"未找到更新日志文件" | —— |

现在统一到本模块：**按版本号排序**（1.16.1 > 1.8.0），一个主题化阅读窗口（可切版本），
文件夹为空时**回退去读 README 的「最新版本」章节**（源码版/绿色版都有 README，
即使 `更新日志/` 没随包带上也能看）。
"""
import glob
import os
import re

from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QPushButton,
                             QTextBrowser, QVBoxLayout)

from .colors import Color1, Color3, Color4, Color5, Color7, Gray2, _app_base_dir, btn_radius

VER_RE = re.compile(r"^V(\d+(?:\.\d+)*)")


def changelog_dir() -> str:
    """更新日志目录：<程序目录>/更新日志（frozen 时= exe 旁）"""
    return os.path.join(_app_base_dir(), "更新日志")


def _ver_key(name: str):
    """文件名 → 可比较的版本元组；解析不出给 None"""
    m = VER_RE.match(os.path.basename(name))
    if not m:
        return None
    return tuple(int(x) for x in m.group(1).split("."))


def entries():
    """[{"ver","name","path"}]，**按版本号从新到旧**；解析不出 V 号的排最后（按 mtime）"""
    folder = changelog_dir()
    out = []
    try:
        names = [f for f in os.listdir(folder) if f.lower().endswith((".md", ".txt"))]
    except Exception:
        return out
    for f in names:
        p = os.path.join(folder, f)
        out.append({"ver": _ver_key(f), "name": f, "path": p})
    numbered = sorted([e for e in out if e["ver"]], key=lambda e: e["ver"], reverse=True)
    others = sorted([e for e in out if not e["ver"]],
                    key=lambda e: os.path.getmtime(e["path"]), reverse=True)
    return numbered + others


def latest():
    """最新一篇日志的路径；没有给 None"""
    es = entries()
    return es[0]["path"] if es else None


def read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def readme_history():
    """回退：从 README 的「最新版本」章节现取（→ (标题, 文本) 或 None）。

    复用 `tool/gen_changelog` 的解析器，避免"两套解析各写一遍"。
    冻结版（安装器）里 README 可能在 `sys._MEIPASS`，两处都找。
    """
    import sys
    cands = [os.path.join(_app_base_dir(), "README.md")]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        cands.append(os.path.join(meipass, "README.md"))
    for p in cands:
        if not os.path.isfile(p):
            continue
        try:
            import sys as _sys
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if root not in _sys.path:
                _sys.path.insert(0, root)
            from tool.gen_changelog import parse_readme
            blocks = parse_readme(p)
        except Exception as e:
            print(f"[Changelog] ⚠ 解析 README 版本历史失败: {e}")
            continue
        if not blocks:
            continue
        lines = []
        for ver, desc, body in blocks:
            lines.append(f"# V{ver}" + (f" — {desc}" if desc else ""))
            lines.append("")
            lines.extend(body)
            lines.append("")
        return (f"README.md · 最新版本（更新日志目录为空，现读 README）",
                "\n".join(lines).strip() + "\n")
    return None


# ══════════════════════ 主题化阅读窗口 ══════════════════════
def show(parent=None):
    """打开更新日志阅读窗口（可切版本）。返回对话框；没有任何内容时给提示。"""
    from .silicon_dialog import page_msg, SiliconDialog
    es = entries()
    fallback = None
    if not es:
        fallback = readme_history()
        if not fallback:
            page_msg(parent, "更新日志",
                     "没找到更新日志。",
                     "程序目录下没有「更新日志」文件夹，也没有能读取的 README.md。\n"
                     f"位置：{changelog_dir()}\n\n"
                     "（源码版可执行 `python tool/gen_changelog.py` 从 README 生成）")
            return None

    dlg = SiliconDialog("📜 更新日志", parent, width=900, height=660, opaque=True)
    lay = QVBoxLayout()
    lay.setContentsMargins(14, 10, 14, 12)
    lay.setSpacing(10)

    top = QHBoxLayout()
    top.setSpacing(8)
    cmb = QComboBox()
    cmb.setMinimumWidth(220)
    if es:
        for i, e in enumerate(es):
            label = ("V" + ".".join(str(x) for x in e["ver"])) if e["ver"] else e["name"]
            cmb.addItem(label + ("　（最新）" if i == 0 else ""), e["path"])
    else:
        cmb.addItem("README.md（回退）", "")
        cmb.setEnabled(False)
    top.addWidget(QLabel("版本："))
    top.addWidget(cmb)
    top.addStretch()
    lay.addLayout(top)

    tb = QTextBrowser()
    tb.setOpenExternalLinks(True)
    tb.setStyleSheet(
        f"QTextBrowser {{ background: {Color7.name()}; color: {Color1.name()};"
        f" border: 1px solid {Color5.name()}; border-radius: {int(btn_radius())}px;"
        f" padding: 12px; font-size: 13px; }}")
    lay.addWidget(tb, 1)

    def _load(path: str = ""):
        if path:
            try:
                text = read(path)
            except Exception as e:
                text = f"读取失败：{e}"
        else:
            text = fallback[1] if fallback else ""
        try:
            tb.document().setMarkdown(text)          # Qt5.14+：直接把 md 渲染出来
        except Exception:
            tb.setPlainText(text)
        tb.moveCursor(QTextCursor.Start)

    row = QHBoxLayout()
    row.setSpacing(8)
    b_dir = QPushButton("📂 打开目录")
    b_dir.setStyleSheet(f"""
        QPushButton {{ background: {Color3.name()}; color: white; border: none;
            padding: 7px 16px; font-size: 13px; border-radius: {int(btn_radius())}px; }}
        QPushButton:hover {{ background: {Color4.name()}; }}
    """)
    b_open = QPushButton("📄 用系统程序打开")
    b_open.setStyleSheet(f"""
        QPushButton {{ background: transparent; color: {Gray2.name()};
            border: 1px solid {Color5.name()}; padding: 7px 16px; font-size: 13px;
            border-radius: {int(btn_radius())}px; }}
        QPushButton:hover {{ color: {Color1.name()}; border-color: {Color3.name()}; }}
    """)
    b_close = QPushButton("关闭")
    b_close.setStyleSheet(f"""
        QPushButton {{ background: {Color3.name()}; color: white; border: none;
            padding: 7px 22px; font-size: 13px; border-radius: {int(btn_radius())}px; }}
        QPushButton:hover {{ background: {Color4.name()}; }}
    """)

    def _open_dir():
        from .silicon_dialog import page_msg as _pm
        try:
            os.makedirs(changelog_dir(), exist_ok=True)
            os.startfile(changelog_dir())            # noqa
        except Exception as e:
            _pm(dlg, "打开失败", str(e))

    def _open_system():
        from .silicon_dialog import page_msg as _pm
        p = cmb.currentData() or (es[0]["path"] if es else "")
        if not p:
            _pm(dlg, "打开失败", "没有可打开的文件。")
            return
        try:
            os.startfile(p)                          # noqa
        except Exception as e:
            _pm(dlg, "打开失败", str(e))

    b_dir.clicked.connect(_open_dir)
    b_open.clicked.connect(_open_system)
    b_close.clicked.connect(dlg.accept)
    cmb.currentIndexChanged.connect(lambda _i: _load(cmb.currentData() or ""))
    row.addWidget(b_dir)
    row.addWidget(b_open)
    row.addStretch()
    row.addWidget(b_close)
    lay.addLayout(row)

    try:
        dlg.content.addLayout(lay, 1)
    except Exception:
        _wrap = QVBoxLayout(dlg)
        _wrap.addLayout(lay)
    _load(es[0]["path"] if es else "")
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
    return dlg
