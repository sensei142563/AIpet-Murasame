# -*- coding: utf-8 -*-
"""把 README 的「最新版本」章节同步成 `更新日志/V<版本>.md`（启动器的「更新日志」功能读这个目录）。

为什么要有它：README 的版本历史是唯一权威来源，但启动器的「更新日志」按钮读的是
程序目录下的 `更新日志/` 文件夹（绿色版/安装版都靠它），以前这个文件夹是空的 →
点「更新日志」只会弹「未找到更新日志文件」。与其手抄一份（早晚和 README 走偏），
不如**从 README 生成**，并用 `--check` 在自测里盯着有没有漏同步。

用法：
    python tool/gen_changelog.py            # 生成/更新 更新日志/*.md
    python tool/gen_changelog.py --check    # 只校验是否与 README 一致（自测用）
    python tool/gen_changelog.py --print    # 打印解析结果（排查解析问题时用）
"""
import argparse
import io
import os
import re
import sys

try:  # 控制台被重定向（管道/日志）时 Windows 会用 GBK 编码 stdout，
    # 打印 emoji / 全角符号会 UnicodeEncodeError 直接打断进程 → 统一降级成替换字符
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(ROOT, "README.md")
OUT_DIR = os.path.join(ROOT, "更新日志")

# `**V1.16.1** — 环境加固 + N卡实机修复`
BOLD_RE = re.compile(r"^\*\*(V[0-9][0-9A-Za-z.]*)\*\*\s*(?:[—\-–]+\s*(.*))?$")
# `### V1.16.1 变更` / `### V1.10.x 修复与增强`
HEAD_RE = re.compile(r"^###\s+(V[0-9][0-9A-Za-z.]*)\s*(.*)$")
SECTION_RE = re.compile(r"^##\s+.*最新版本")

GEN_NOTE = ("<!-- 由 tool/gen_changelog.py 从 README.md 的「最新版本」章节生成，勿手改；"
            "改 README 后重跑该脚本即可 -->")


def target_dir() -> str:
    """生成目标：源码用项目根；打包后可被覆盖（测试里也用它做隔离）"""
    return os.environ.get("AIPET_CHANGELOG_DIR") or OUT_DIR


def readme_path() -> str:
    return os.environ.get("AIPET_README") or README


def _ver_key(ver: str):
    """V 号 → 可比较的元组（1.16.1 → (1,16,1)）；带 x 的取能解析的部分"""
    parts = []
    for p in str(ver).split("."):
        m = re.match(r"^(\d+)", p)
        if not m:
            break
        parts.append(int(m.group(1)))
    return tuple(parts) or (0,)


def _tail(ver: str):
    """同号多段的排序尾（V1.16.1 > V1.16）"""
    return _ver_key(ver)


def parse_readme(path: str = None):
    """解析 README → [(ver, desc, body_lines)]，按 README 顺序（最新在前）"""
    path = path or readme_path()
    lines = io.open(path, encoding="utf-8").read().splitlines()
    start = None
    for i, ln in enumerate(lines):
        if SECTION_RE.match(ln):
            start = i + 1
            break
    if start is None:
        raise SystemExit("README 里找不到「## 最新版本」章节，无法生成更新日志")
    end = len(lines)
    for i in range(start, len(lines)):
        if lines[i].startswith("## "):
            end = i
            break

    blocks = []            # [{"ver","heading","desc","body"}]
    pending = None         # 最近一条 **Vx** 行（还没被哪个 ### 认领）
    orphan_bold = []
    cur = None
    for ln in lines[start:end]:
        s = ln.strip()
        m = BOLD_RE.match(s)
        if m:
            pending = (m.group(1)[1:], (m.group(2) or "").strip())
            continue
        m = HEAD_RE.match(s)
        if m:
            hv, suffix = m.group(1)[1:], (m.group(2) or "").strip()
            ver, desc = hv, ""
            if pending:
                pv, pd = pending
                # `### V1.10.x 修复与增强` 配 `**V1.10.2** — …`：用具体版本号当文件名
                if pv == hv or (hv.endswith(".x") and pv.startswith(hv[:-2])):
                    ver, desc = pv, pd
                pending = None
            cur = {"ver": ver, "heading": hv, "desc": desc, "body": []}
            blocks.append(cur)
            continue
        if s.startswith("### "):
            if "历史版本" in s:
                cur = {"ver": "1.4.0-及更早", "heading": "历史版本",
                       "desc": "历史版本（README 只留摘要）", "body": []}
                blocks.append(cur)
            else:
                cur = None
            pending = None
            continue
        if cur is not None:
            if s.startswith("---") or s == "---":
                continue
            cur["body"].append(ln)
    if pending:
        orphan_bold.append(pending)

    out = []
    for b in blocks:
        body = list(b["body"])
        while body and not body[-1].strip():
            body.pop()
        out.append((b["ver"], b["desc"], body))
    if orphan_bold:
        print("[gen_changelog] ⚠ README 里这些 `**Vx**` 没有任何 `###` 段落承接：%s"
              % "、".join(v for v, _ in orphan_bold))
    return out


def render(ver: str, desc: str, body) -> str:
    head = f"# V{ver}" + (f" — {desc}" if desc else "")
    return "\n".join([GEN_NOTE, "", head, ""] + list(body)) + "\n"


def build(path: str = None):
    """→ {文件名: 内容}"""
    files = {}
    for ver, desc, body in parse_readme(path):
        files[f"V{ver}.md"] = render(ver, desc, body)
    return files


def main() -> int:
    ap = argparse.ArgumentParser(description="从 README 生成更新日志")
    ap.add_argument("--check", action="store_true", help="只校验是否与 README 一致")
    ap.add_argument("--print", dest="do_print", action="store_true", help="打印解析结果")
    a = ap.parse_args()

    want = build()
    if a.do_print:
        for name, text in want.items():
            print("=" * 70)
            print(name)
            print(text)
        return 0

    out_dir = target_dir()
    if a.check:
        bad = []
        have = set()
        if os.path.isdir(out_dir):
            have = {f for f in os.listdir(out_dir) if f.endswith(".md")}
        for name, text in want.items():
            p = os.path.join(out_dir, name)
            if not os.path.isfile(p):
                bad.append("缺文件：%s" % name)
                continue
            got = io.open(p, encoding="utf-8").read()
            if got.replace("\r\n", "\n") != text:
                bad.append("内容与 README 不一致：%s" % name)
        for name in sorted(have - set(want)):
            bad.append("多出来的文件（README 里没有这个版本）：%s" % name)
        if bad:
            print("[FAIL] 更新日志与 README 不同步（跑 python tool/gen_changelog.py 重新生成）：")
            for b in bad:
                print("   " + b)
            return 1
        print("[OK] 更新日志与 README 一致（%d 个版本）" % len(want))
        return 0

    os.makedirs(out_dir, exist_ok=True)
    n = 0
    for name, text in want.items():
        p = os.path.join(out_dir, name)
        old = io.open(p, encoding="utf-8").read() if os.path.isfile(p) else None
        if old == text:
            continue
        io.open(p, "w", encoding="utf-8", newline="\n").write(text)
        print("  %s %s" % ("更新" if old is not None else "新增", name))
        n += 1
    for f in sorted(os.listdir(out_dir)):
        if f.endswith(".md") and f not in want:
            print("  ⚠ 目录里多出来的（README 已无此版本，请确认后删除）：%s" % f)
    print("[OK] 更新日志已同步：%d 个版本，%d 个文件%s"
          % (len(want), n, "（无变化）" if n == 0 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
