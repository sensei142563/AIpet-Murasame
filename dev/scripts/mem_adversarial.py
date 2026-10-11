# -*- coding: utf-8 -*-
"""记忆导入导出的对抗测试（临时目录，绝不动真实记忆）。先看会暴露什么。"""
import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
sys.path.insert(0, MAIN)
from tool import memory_transfer as mt  # noqa: E402

TMP = tempfile.mkdtemp(prefix="mem_adv_")
mt.BASE = Path(TMP)          # 关键：把仓库根换到临时目录，避免碰到真实记忆
print("临时 BASE = %s" % TMP)

results = []


def note(name, ok, detail=""):
    results.append((name, ok, detail))
    print("   [%s] %-40s %s" % ("PASS" if ok else "FAIL", name, detail[:140]))


def write(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def run_import(path, pet="murasame"):
    class A:
        pass
    a = A()
    a.file = str(path)
    a.pet = pet
    try:
        n = mt.cmd_import(a)
        return ("ok", n, "")
    except Exception as e:
        return ("exc", None, "%s: %s" % (type(e).__name__, e))


def hist(pet="murasame", name="history.json"):
    p = mt.mem_dir(pet) / name
    if not p.is_file():
        return []
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    return d.get("history", []) if isinstance(d, dict) else d


BASE_PET = "murasame"

print()
print("=== ① 基本导入 + 幂等（同一份导入两次不应重复）===")
src = Path(TMP) / "b1.json"
write(src, {"schema": mt.SCHEMA, "pet": BASE_PET,
            "history": [{"role": "user", "content": "你好", "timestamp": "2026-01-01 10:00:00"},
                        {"role": "assistant", "content": "嗯", "timestamp": "2026-01-01 10:00:01"}]})
st, n, err = run_import(src)
note("首次导入成功", st == "ok" and n == 2, "added=%s %s" % (n, err))
st, n, err = run_import(src)
note("重复导入幂等（新增 0）", st == "ok" and n == 0, "added=%s %s" % (n, err))
note("记忆条数为 2", len(hist() or []) == 2, "实际 %d" % len(hist() or []))

print()
print("=== ② 截断/非法 JSON：应报错且**不改动**已有记忆 ===")
before = json.dumps(hist(), ensure_ascii=False)
bad = Path(TMP) / "bad.json"
bad.write_text('{"schema":"aipet.memory/1","history":[{"role":"user","content":"半', encoding="utf-8")
st, n, err = run_import(bad)
after = json.dumps(hist(), ensure_ascii=False)
note("非法 JSON 不静默成功", st == "exc", "结果=%s %s" % (st, err))
note("非法 JSON 未改动记忆", before == after, "前后一致" if before == after else "内容变了 ✗")

print()
print("=== ③ incoming 里混入非 dict（字符串/数字/null）===")
mix = Path(TMP) / "mix.json"
write(mix, {"pet": BASE_PET, "history": ["我是一个字符串", 42, None,
                                         {"role": "user", "content": "正常一条", "timestamp": "2026-01-02 00:00:00"}]})
st, n, err = run_import(mix)
note("混入非 dict 不应崩", st == "ok", "结果=%s %s" % (st, err))
note("非 dict 之后的正常记录仍导入", st == "ok" and any(
    (e.get("content") == "正常一条") for e in (hist() or []) if isinstance(e, dict)),
    "条数=%d" % len(hist() or []))

print()
print("=== ④ timestamp 类型混用（int 与 str）===")
ts = Path(TMP) / "ts.json"
write(ts, {"pet": BASE_PET, "history": [
    {"role": "user", "content": "整数时间", "timestamp": 1700000000},
    {"role": "user", "content": "字符串时间", "timestamp": "2026-01-03 00:00:00"}]})
st, n, err = run_import(ts)
note("时间类型混用不应崩", st == "ok", "结果=%s %s" % (st, err))

print()
print("=== ⑤ 已有文件损坏时导入：不得静默丢掉旧记忆 ===")
pet2 = "pet_corrupt"
d2 = mt.mem_dir(pet2)
d2.mkdir(parents=True, exist_ok=True)
(d2 / "history.json").write_text('{"history":[{"role":"user","content":"旧的珍",', encoding="utf-8")
src2 = Path(TMP) / "c2.json"
write(src2, {"pet": pet2, "history": [{"role": "user", "content": "新的一条", "timestamp": "2026-01-04 00:00:00"}]})
st, n, err = run_import(src2, pet=pet2)
raw_after = (d2 / "history.json").read_text(encoding="utf-8", errors="replace")
note("损坏现状被明确处理（报错或保留备份）",
     st == "exc" or (d2 / "history.json.bak-import").exists(),
     "结果=%s 有备份=%s %s" % (st, (d2 / "history.json.bak-import").exists(), err))
note("原损坏内容没有被无声覆盖",
     "旧的珍" in raw_after or (d2 / "history.json.bak-import").exists()
     and "旧的珍" in (d2 / "history.json.bak-import").read_text(encoding="utf-8", errors="replace"),
     "可见性检查")

print()
print("=== ⑥ 裸 list 文件 ===")
bl = Path(TMP) / "bare.json"
write(bl, [{"role": "user", "content": "裸列表一条", "timestamp": "2026-01-05 00:00:00"}])
st, n, err = run_import(bl, pet="pet_bare")
note("支持裸 list", st == "ok" and n == 1, "added=%s %s" % (n, err))

print()
print("=== ⑦ emoji / 超长 / 特殊字符往返 ===")
pet3 = "pet_uni"
long_text = "很长" * 5000
src3 = Path(TMP) / "u.json"
write(src3, {"pet": pet3, "history": [
    {"role": "user", "content": "😀🎉 丛雨\u200b零宽", "timestamp": "2026-01-06 00:00:00"},
    {"role": "user", "content": long_text, "timestamp": "2026-01-06 00:00:01"}]})
st, n, err = run_import(src3, pet=pet3)
ok_uni = st == "ok" and any((e.get("content") == long_text) for e in (hist(pet3) or []) if isinstance(e, dict))
note("emoji/零宽/超长内容往返完好", ok_uni, "added=%s %s" % (n, err))

print()
print("=== ⑧ 缺失字段的记录（无 role/timestamp）===")
mis = Path(TMP) / "miss.json"
write(mis, {"pet": "pet_miss", "history": [{"content": "只有内容"}, {}, {"role": "user"}]})
st, n, err = run_import(mis, pet="pet_miss")
note("缺字段记录不崩", st == "ok", "added=%s %s" % (n, err))

print()
print("=== ⑨ 写入原子性（结构检查：是否使用临时文件+replace）===")
src_body = io.open(os.path.join(MAIN, "tool", "memory_transfer.py"), encoding="utf-8").read()
atomic = ("os.replace" in src_body) or ("Path.replace" in src_body) or (".replace(" in src_body and "tmp" in src_body.lower())
note("写入使用原子替换", atomic, "使用 os.replace/临时文件" if atomic else "直接 write_text ⇒ 写入中被杀会截断")

print()
npass = sum(1 for _, ok, _ in results if ok)
print("=== 汇总：%d/%d 通过 ===" % (npass, len(results)))
for name, ok, detail in results:
    if not ok:
        print("   ✗ %s — %s" % (name, detail[:150]))
shutil.rmtree(TMP, ignore_errors=True)
print("（临时目录已清理：%s）" % TMP)
sys.exit(0 if npass == len(results) else 1)
