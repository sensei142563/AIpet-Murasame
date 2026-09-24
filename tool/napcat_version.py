# -*- coding: utf-8 -*-
"""NapCat / QQ 版本锚（NAPCAT_VERSION.txt）的解析与比对。

为什么要单独一个模块：版本核对以前**只在打包脚本里跑** —— 用户直接用「启动 QQ」时，
NapCat 被它自带的更新器升到未验证版本也没人提醒。这里做成纯函数，
打包检查（build_launcher）与启动自检（run_qq）共用同一份逻辑。

锚文件格式（# 后面是注释）::

    napcat=4.18.28                # 锁定的 NapCat 版本
    qq=9.9.35-52892              # 随包绿色 QQ 的版本
    qq_max_supported=9.9.35-52892  # NapCat 支持表的上限

对外只有 check() 是需要关心的：返回一串 {level, msg}，由调用方决定怎么显示。
"""
import json
import os
import re

ANCHOR_FILE = "NAPCAT_VERSION.txt"
ONEKEY_DIR = "NapCat.Shell.Windows.OneKey"
QQ_VERSION_JSON = os.path.join("bootmain", "versions", "config.json")
NAPCAT_MJS = os.path.join("NapCat", "napcat.mjs")


def read_anchor(base_dir: str) -> dict:
    """读版本锚；文件不存在或读不动时返回 {}（调用方按"跳过核对"处理）"""
    path = os.path.join(base_dir or ".", ANCHOR_FILE)
    if not os.path.isfile(path):
        return {}
    out = {}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for ln in f:
                ln = ln.split("#")[0].strip()
                if "=" in ln:
                    k, v = ln.split("=", 1)
                    out[k.strip()] = v.strip()
    except Exception:
        return {}
    return out


def napcat_version_of(onekey_dir: str) -> str:
    """NapCat 的实际版本：写在 napcat.mjs 里 —— ... && "4.18.28" || "1.0.0-dev" """
    p = os.path.join(onekey_dir or ".", NAPCAT_MJS)
    if not os.path.isfile(p):
        return ""
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            head = f.read(4_000_000)
    except Exception:
        return ""
    m = re.search(r'&&\s*"(\d+\.\d+\.\d+)"', head)
    return m.group(1) if m else ""


def bundled_qq_version(onekey_dir: str) -> str:
    """随包绿色 QQ 的版本：bootmain/versions/config.json 的 curVersion"""
    p = os.path.join(onekey_dir or ".", QQ_VERSION_JSON)
    if not os.path.isfile(p):
        return ""
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            d = json.load(f) or {}
    except Exception:
        return ""
    return str(d.get("curVersion") or d.get("baseVersion") or "")


def cmp_version(a: str, b: str) -> int:
    """版本号比较：a>b 返回 1，a<b 返回 -1，相同返回 0。

    为什么要自己写：QQ 版本长这样 `9.9.35-52892` —— 直接用字符串比较会得出
    「9.9.9 > 9.9.35」这种错结论（字符逐位比）。这里按数字段/字母段拆开比，
    段数不同就按 0 补齐（1.2 == 1.2.0）。
    """
    def _parts(s):
        return re.findall(r"\d+|[A-Za-z]+", str(s or ""))

    pa, pb = _parts(a), _parts(b)
    for i in range(max(len(pa), len(pb))):
        x = pa[i] if i < len(pa) else "0"
        y = pb[i] if i < len(pb) else "0"
        if x.isdigit() and y.isdigit():
            if int(x) != int(y):
                return 1 if int(x) > int(y) else -1
        elif x != y:
            return 1 if x > y else -1
    return 0


def check(base_dir: str, onekey_dir: str = None) -> list:
    """核对版本锚 → [{"level": "ok"|"info"|"warn", "msg": 人话}]

    base_dir   : 程序根目录（NAPCAT_VERSION.txt 所在处）
    onekey_dir : NapCat/QQ 装载目录，默认 base_dir/NapCat.Shell.Windows.OneKey
    """
    base_dir = base_dir or "."
    onekey = onekey_dir or os.path.join(base_dir, ONEKEY_DIR)
    out = []

    anchor = read_anchor(base_dir)
    if not anchor:
        out.append({"level": "info", "msg": "没找到 %s，跳过版本核对" % ANCHOR_FILE})
        return out

    want = anchor.get("napcat", "")
    got = napcat_version_of(onekey)
    if not got:
        out.append({"level": "warn",
                    "msg": "没能从 napcat.mjs 读出 NapCat 版本（文件结构可能变了）"})
    elif want and got != want:
        out.append({"level": "warn",
                    "msg": "NapCat 版本被改过：锁定 %s，实际 %s —— 可能被它自带的更新器升级了；"
                           "新版本未经验证，建议换回 %s" % (want, got, want)})
    else:
        out.append({"level": "ok", "msg": "NapCat %s 与 %s 一致" % (got, ANCHOR_FILE)})

    qq_max = anchor.get("qq_max_supported", "")
    bundled = bundled_qq_version(onekey)
    if bundled:
        if qq_max and cmp_version(bundled, qq_max) > 0:
            out.append({"level": "warn",
                        "msg": "随包绿色 QQ %s 超出支持上限 %s —— 会报"
                               "「不支持当前QQ版本架构」，请换成 ≤ %s 的 QQ"
                               % (bundled, qq_max, qq_max)})
        else:
            out.append({"level": "info",
                        "msg": "随包绿色 QQ %s%s" % (bundled,
                                                    "（支持上限 %s）" % qq_max if qq_max else "")})
    if qq_max:
        out.append({"level": "info",
                    "msg": "系统里装的 QQ 版本也要 ≤ %s；NapCat 自带的更新器和 QQ 自动更新都建议关掉"
                           % qq_max})
    return out
