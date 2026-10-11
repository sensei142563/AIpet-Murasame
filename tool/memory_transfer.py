# -*- coding: utf-8 -*-
"""记忆导出 / 导入（与手机端 chatter 的 MemoryStore 同协议）。

格式（与 docs/plan/03 ADR-001/009 一致，"事件日志 + 物化视图"退化为导出格式）：
    {"schema":"aipet.memory/1","pet":"murasame","source":"aipet-desktop",
     "exported_at":"...","history":[{role,content,timestamp}],"long_history":[...]}

用法：
    python tool/memory_transfer.py export --pet murasame [--out 路径.json]
    python tool/memory_transfer.py import 文件.json [--pet murasame]
    不加子命令时默认 export。
兼容：导入时同时接受裸 {"history":[...]}（就是 pets/<id>/memory/history.json 本身）。
"""
import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SCHEMA = "aipet.memory/1"


def mem_dir(pet: str) -> Path:
    return BASE / "pets" / pet / "memory"


def _load(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def _load_strict(p: Path):
    """返回 (数据, 是否解析失败)。用于需要区分"空文件"与"坏文件"的场景。"""
    if not p.is_file():
        return None, False
    try:
        return json.loads(p.read_text(encoding="utf-8")), False
    except Exception:
        return None, True


def _hist(p: Path):
    d = _load(p, {})
    if isinstance(d, list):
        return d
    return d.get("history", []) or []


def _key(e):
    return "%s|%s|%s" % (e.get("role", ""), e.get("timestamp", ""), e.get("content", ""))


def _ts_key(e):
    """排序键：数字时间在前（按数值），字符串时间在后（按字典序）。

    为什么不能直接用 e.get("timestamp")：导入的文件可能混用 int 与 str，
    Python 3 比较 int 与 str 会抛 TypeError ⇒ 整次导入崩掉（对抗测试实测）。
    """
    ts = e.get("timestamp", "")
    if isinstance(ts, bool):          # bool 是 int 的子类，单独排掉
        return (2, str(ts))
    if isinstance(ts, (int, float)):
        return (0, float(ts))
    return (1, str(ts))


def _valid_record(e):
    """只接受"看起来像一条记忆"的 dict：必须有非空 content。

    None/字符串/数字（损坏的导出文件里很常见）一律跳过，而不是让 e.get() 抛 AttributeError ——
    崩在循环中间会让**后面**的正常记录也导不进去（对抗测试实测）。
    """
    return isinstance(e, dict) and str(e.get("content", "")).strip() != ""


def cmd_export(a):
    pet = a.pet
    d = mem_dir(pet)
    bundle = {
        "schema": SCHEMA,
        "pet": pet,
        "source": "aipet-desktop",
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "history": _hist(d / "history.json"),
        "long_history": _hist(d / "long_history.json"),
    }
    out = Path(a.out) if a.out else (BASE / "dev" / "memory_io" / (
        "memory_%s_%s.json" % (pet, datetime.now().strftime("%Y%m%d_%H%M%S"))))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    print("导出 %d 条短记忆 / %d 条长记忆 -> %s" % (
        len(bundle["history"]), len(bundle["long_history"]), out))
    return out


def cmd_import(a):
    src = Path(a.file)
    raw = json.loads(src.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        short, long_ = raw, []
        pet = a.pet
    else:
        short = raw.get("history", []) or []
        long_ = raw.get("long_history", raw.get("longHistory", [])) or []
        pet = a.pet or raw.get("pet") or "murasame"
    d = mem_dir(pet)
    d.mkdir(parents=True, exist_ok=True)
    total_added = total_dup = total_bad = 0
    for name, incoming in (("history.json", short), ("long_history.json", long_)):
        if not incoming:
            continue
        if not isinstance(incoming, list):
            print("  %s: 不是列表，已跳过（类型 %s）" % (name, type(incoming).__name__))
            continue
        f = d / name
        # 已存在但**读不出来**（截断/损坏）时必须明说，而不是静默当成空文件接着写
        existed = f.exists()
        cur = _hist(f)
        if existed and not cur and f.stat().st_size > 2:
            print("  ⚠ %s 已存在但无法解析（%d 字节）—— 会先备份再写，请检查 .bak-import"
                  % (name, f.stat().st_size))
        cur = [e for e in cur if _valid_record(e)]
        seen = {_key(e) for e in cur}
        added = dup = bad = 0
        for e in incoming:
            if not _valid_record(e):
                bad += 1
                continue
            if _key(e) in seen:
                dup += 1
            else:
                seen.add(_key(e))
                cur.append(e)
                added += 1
        # 只要文件已存在就先备份（原来只在 added>0 时备份，损坏场景下会漏）
        if existed and (added or bad):
            try:
                shutil.copy2(f, str(f) + ".bak-import")
            except Exception as _e:
                print("  ⚠ 备份失败：%s" % _e)
        cur.sort(key=_ts_key)          # 用健壮排序键，避免 int/str 混用崩掉
        payload = json.dumps({"history": cur}, ensure_ascii=False, indent=2)
        # **原子写**：先写同目录临时文件再 replace ⇒ 写到一半被杀也不会截断原文件
        tmp = f.with_name(f.name + ".tmp")
        tmp.write_text(payload, encoding="utf-8")
        os.replace(str(tmp), str(f))
        print("  %s: 新增 %d，重复 %d，跳过 %d（非法记录），现有 %d"
              % (name, added, dup, bad, len(cur)))
        total_added += added
        total_dup += dup
        total_bad += bad
    print("导入完成（角色 %s）：新增 %d，重复 %d，跳过 %d"
          % (pet, total_added, total_dup, total_bad))
    return total_added


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    e = sub.add_parser("export")
    e.add_argument("--pet", default="murasame")
    e.add_argument("--out", default=None)
    i = sub.add_parser("import")
    i.add_argument("file")
    i.add_argument("--pet", default=None)
    a = ap.parse_args()
    if a.cmd == "import":
        cmd_import(a)
    else:
        if a.cmd is None:
            a.pet, a.out = "murasame", None
        cmd_export(a)


if __name__ == "__main__":
    main()
