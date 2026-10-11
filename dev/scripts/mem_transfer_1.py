# -*- coding: utf-8 -*-
"""④ 记忆互通第一步：手机端 MemoryStore 加导出/导入 + 冷启动自动导出/导入；桌面端加 CLI 导出/导入。
   （纯逻辑改动，不改 UI；导入/导出走可 pull 的 externalFilesDir，便于全自动验收。）
"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
MS = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/bot/chat/MemoryStore.kt")
ACT = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/MainActivity.kt")
CLI = os.path.join(MAIN, "tool/memory_transfer.py")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
PKG = "com.aipet.murasame"
MAP = os.path.join(MAIN, "dev/merge-map")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")
ok = True


def note(m, c):
    global ok
    print(("✓ " if c else "✗ ") + m)
    if not c:
        ok = False


# ---------- ① MemoryStore：加导出/导入 ----------
src = io.open(MS, encoding="utf-8").read().replace("\r\n", "\n")
if "fun exportBundle(" in src:
    note("MemoryStore 已有导出/导入", True)
else:
    anchor = "    private fun now(): String ="
    note("定位 now() 锚点", anchor in src)
    add = '''    // ================= 记忆导出 / 导入（④ 记忆互通，协议见 docs/plan/03 ADR-001/009）=================
    // 导出格式 = {"schema":"aipet.memory/1","pet":..,"exported_at":..,"history":[..],"long_history":[..]}
    // 导入同时兼容：本 schema、桌面端裸文件 {"history":[..]}、以及只有数组的 [..]。

    private fun memoryDirOf(pet: String): File =
        File(File(File(baseDir, "pets"), pet.ifBlank { "murasame" }), "memory")

    /** 导出当前角色的记忆（可被桌面端 / 另一台手机导入）。 */
    fun exportBundle(pet: String? = null): String {
        val p = (pet ?: activePet()).ifBlank { "murasame" }
        val dir = memoryDirOf(p)
        return JSONObject()
            .put("schema", "aipet.memory/1")
            .put("pet", p)
            .put("source", "chatter-android")
            .put("exported_at", now())
            .put("history", JSONArray(readHistory(File(dir, "history.json"))))
            .put("long_history", JSONArray(readHistory(File(dir, "long_history.json"))))
            .toString(2)
    }

    /** 导入结果：新增/重复/总条数，便于界面与验收脚本判断。 */
    data class ImportResult(val added: Int, val dup: Int, val total: Int, val pet: String)

    private fun keyOf(o: JSONObject): String =
        (o.optString("role") + "|" + o.optString("timestamp") + "|" + o.optString("content"))

    /** 合并一段 JSON：兼容三种形状；按 role|timestamp|content 去重；按 timestamp 排序后落盘。 */
    fun importBundle(text: String, pet: String? = null): ImportResult {
        val p = (pet ?: activePet()).ifBlank { "murasame" }
        val root = runCatching { JSONObject(text) }.getOrNull()
        var shortIn: List<JSONObject> = emptyList()
        var longIn: List<JSONObject> = emptyList()
        var petIn = p
        if (root != null) {
            root.optString("pet").takeIf { it.isNotBlank() }?.let { petIn = it }
            shortIn = arr(root.optJSONArray("history"))
            longIn = arr(root.optJSONArray("long_history"))
            if (shortIn.isEmpty() && longIn.isEmpty()) {
                // 桌面端驼峰变体：longHistory / longHistoryJson
                longIn = arr(root.optJSONArray("longHistory"))
            }
        } else {
            val a = runCatching { JSONArray(text) }.getOrNull()
            if (a != null) shortIn = arr(a)
        }
        val target = if (pet.isNullOrBlank()) petIn else p
        val dir = memoryDirOf(target)
        dir.mkdirs()
        var added = 0
        var dup = 0
        listOf("history" to shortIn, "long_history" to longIn).forEach { (name, incoming) ->
            if (incoming.isEmpty()) return@forEach
            val f = File(dir, if (name == "history") "history.json" else "long_history.json")
            val cur = readHistory(f)
            val seen = HashSet(cur.map { keyOf(it) })
            incoming.forEach { o ->
                if (keyOf(o) in seen) dup++ else {
                    seen.add(keyOf(o)); cur.add(o); added++
                }
            }
            val sorted = cur.sortedBy { it.optString("timestamp") }
            writeHistory(f, sorted)
        }
        return ImportResult(added, dup, (readHistory(File(dir, "history.json")).size), target)
    }

    private fun arr(a: JSONArray?): List<JSONObject> {
        if (a == null) return emptyList()
        val out = mutableListOf<JSONObject>()
        for (i in 0 until a.length()) a.optJSONObject(i)?.let { out.add(it) }
        return out
    }

    /** 外部目录（可 adb pull / 用户手动拷贝）：export/ 放快照，import/ 里放要合并的文件。 */
    fun externalIoDir(kind: String): File = File(baseDir, "memory_io/$kind")

    /** 冷启动：导出一份快照到 externalFilesDir/memory_io/export/（便于取证与备份）。 */
    fun exportSnapshot(): File? = runCatching {
        val pet = activePet().ifBlank { "murasame" }
        val dir = externalIoDir("export").apply { mkdirs() }
        val f = File(dir, "memory_" + pet + "_" + SimpleDateFormat("yyyyMMdd_HHmmss", Locale.CHINA)
            .format(Date()) + ".json")
        f.writeText(exportBundle(pet))
        f
    }.getOrNull()

    /** 冷启动：合并 externalFilesDir/memory_io/import/ 下的所有 .json，成功后归档到 imported/。 */
    fun autoImport(): ImportResult? {
        val dir = externalIoDir("import")
        if (!dir.isDirectory) return null
        val files = dir.listFiles { f -> f.isFile && f.name.endsWith(".json") } ?: return null
        if (files.isEmpty()) return null
        var added = 0
        var dup = 0
        var total = 0
        var pet = activePet().ifBlank { "murasame" }
        val done = externalIoDir("imported").apply { mkdirs() }
        files.forEach { f ->
            val r = runCatching { importBundle(f.readText()) }.getOrNull()
            if (r != null) {
                added += r.added; dup += r.dup; total = r.total; pet = r.pet
                runCatching { f.renameTo(File(done, f.name)) }
            }
        }
        println("[Memory] 自动导入 $added 条（重复 $dup，当前 $total 条，角色 $pet）")
        return ImportResult(added, dup, total, pet)
    }

'''
    src = src.replace(anchor, add + anchor, 1)
    io.open(MS, "w", encoding="utf-8", newline="\n").write(src)
    note("MemoryStore 加导出/导入/自动导入", "fun autoImport(" in io.open(MS, encoding="utf-8").read())

# ---------- ② MainActivity：冷启动调用（导出快照 + 自动导入） ----------
a = io.open(ACT, encoding="utf-8").read().replace("\r\n", "\n")
if "memoryStore.autoImport" in a or "autoImportMemory" in a:
    note("MainActivity 已接线", True)
else:
    a2 = a.replace('''                Store.init(app)
                BotRepo.init(app.filesDir)''',
                   '''                Store.init(app)
                BotRepo.init(app.filesDir)
                // ④ 记忆互通：冷启动写一份导出快照，并合并 memory_io/import/ 里等待导入的文件
                runCatching { BotRepo.memoryStore.exportSnapshot() }
                runCatching { BotRepo.memoryStore.autoImport() }''', 1)
    note("MainActivity 接线（若 memoryStore 对外不可见，编译会报错，下轮加公开访问器）", a2 != a)
    io.open(ACT, "w", encoding="utf-8", newline="\n").write(a2)

# ---------- ③ 桌面端 CLI ----------
io.open(CLI, "w", encoding="utf-8", newline="\n").write('''# -*- coding: utf-8 -*-
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
''')
note("桌面端 tool/memory_transfer.py 已创建", os.path.isfile(CLI))

# ---------- ④ BotRepo 暴露 memoryStore（若还没有） ----------
BR = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/bot/BotRepo.kt")
b = io.open(BR, encoding="utf-8").read()
print()
print("=== BotRepo 里 memoryStore 的可见性（供接线判断）===")
for l in b.replace("\r\n", "\n").split("\n"):
    if "memoryStore" in l or "MemoryStore(" in l:
        print("   " + l.strip()[:130])

if not ok:
    print("✗ 有步骤失败 —— 回滚 Kotlin 两个文件")
    subprocess.run(["git", "-C", CHAT, "checkout", "--",
                    "app/src/main/java/com/aipet/murasame/bot/chat/MemoryStore.kt",
                    "app/src/main/java/com/aipet/murasame/MainActivity.kt"], capture_output=True)
    sys.exit(1)
print()
print("=== 编译 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o.splitlines() if x.startswith("e: ")][:10]:
    print("   " + y[:230])
print("rc =", r.returncode)
