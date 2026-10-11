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


def _hist(p: Path):
    d = _load(p, {})
    if isinstance(d, list):
        return d
    return d.get("history", []) or []


def _key(e):
    return "%s|%s|%s" % (e.get("role", ""), e.get("timestamp", ""), e.get("content", ""))


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
    total_added = total_dup = 0
    for name, incoming in (("history.json", short), ("long_history.json", long_)):
        if not incoming:
            continue
        f = d / name
        cur = _hist(f)
        seen = {_key(e) for e in cur}
        added = dup = 0
        for e in incoming:
            if _key(e) in seen:
                dup += 1
            else:
                seen.add(_key(e))
                cur.append(e)
                added += 1
        if f.exists() and added:
            shutil.copy2(f, str(f) + ".bak-import")
        cur.sort(key=lambda e: e.get("timestamp", ""))
        f.write_text(json.dumps({"history": cur}, ensure_ascii=False, indent=2), encoding="utf-8")
        print("  %s: 新增 %d，重复 %d，现有 %d" % (name, added, dup, len(cur)))
        total_added += added
        total_dup += dup
    print("导入完成（角色 %s）：新增 %d，重复 %d" % (pet, total_added, total_dup))
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
