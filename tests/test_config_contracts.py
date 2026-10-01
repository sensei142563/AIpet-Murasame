# -*- coding: utf-8 -*-
"""配置契约体检：一个配置键/值在**全项目**必须只有一种理解方式。

覆盖四件（合并自 2026-09-29 的四个审计探针）：
  1. **字典字面量不许有重复键** —— `cfg = {"a": 1, "a": 2}` 里前一份被静默丢弃。
     真实案例：`qq/qq_config.py` 的 `napcat_token` 写了两次 → "从 NapCat 自动发现 token"
     从来没生效，不手填 token 时 QQ 必然连不上（retcode 1403）。
  2. **真值判断统一走 `tool.config.as_bool`** —— 抄出来的版本普遍更窄（只认小写 "true"）
     或方向写反。真实案例：`weather_enabled()` 是 `!= "false"`，于是 `0/off/no/关` 全算**开**。
  3. **配置"存在但缺键"不许 KeyError** —— `get_config()` 只在文件缺失/损坏时回退示例，
     文件存在时原样返回；而调用方大量用 `cfg["key"]` 这种下标（真实案例：本机 51 键 vs 示例
     86 键，`tool/chat.py` 那两行还在**导入期**执行）。现在缺键会给一次性可读提示，且不写文件。
  4. **枚举值读取点统一归一** —— `"Local"` / `"LOCAL "` 必须和 `"local"` 一样走本地分支
     （曾经 `api.py` 同一个文件里两处判断相反）。

用法：`python tests/test_config_contracts.py`（可从任意目录跑，仓库根由 __file__ 推出）。
"""
import ast
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.chdir(REPO)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

FAILS = []


def check(name, cond, extra=""):
    if cond:
        print("  [OK]   %s %s" % (name, extra))
    else:
        print("  [FAIL] %s %s" % (name, extra))
        FAILS.append(name)


def tracked_py():
    out = subprocess.run(["git", "ls-files", "-z", "*.py"], cwd=REPO, capture_output=True,
                         text=True, encoding="utf-8", errors="replace").stdout
    return [p for p in out.split("\0") if p.strip()]


def read(rel):
    return io.open(os.path.join(REPO, rel), encoding="utf-8", errors="replace").read()


CFG_NAMES = ("CONFIG", "cfg", "_cfg", "conf", "_conf", "_c", "d", "_d", "state")


def is_cfg_expr(node):
    if isinstance(node, ast.Name):
        return node.id in CFG_NAMES
    if isinstance(node, ast.Call):
        f = node.func
        return (isinstance(f, ast.Name) and f.id == "get_config") or \
               (isinstance(f, ast.Attribute) and f.attr == "get_config")
    return False


FILES = tracked_py()
TREES = {}
for _rel in FILES:
    try:
        TREES[_rel] = (read(_rel), ast.parse(read(_rel)))
    except Exception:
        pass

# ── 1) 重复字典键 ────────────────────────────────────────────────
print("== 1) 字典字面量里的重复键（前一份会被静默丢弃）==")
dups = []
for rel, (_src, tree) in TREES.items():
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        seen = {}
        for k in node.keys:
            if not isinstance(k, ast.Constant):
                continue
            if k.value in seen:
                dups.append("%s:%d 键 %r（首次在第 %d 行）" % (rel, k.lineno, k.value, seen[k.value]))
            else:
                seen[k.value] = k.lineno
check("全仓没有重复的字典键", not dups, " / ".join(dups[:3]))
check("扫到的文件数合理（>100）", len(FILES) > 100, "%d 个" % len(FILES))

# ── 2) 真值判断一致性 ───────────────────────────────────────────
print("== 2) 真值判断：权威实现 + 那几处窄/反向判断不该回来 ==")
from tool.config import as_bool   # noqa: E402

ON = ["1", "true", "True", "TRUE", "yes", "y", "on", "ON", "开", "开启"]
OFF = ["0", "false", "False", "no", "n", "off", "OFF", "关", "关闭", "随便什么", "是"]
check("as_bool 认这些为真", all(as_bool(v, False) is True for v in ON), str(ON))
check("as_bool 认这些为假", all(as_bool(v, False) is False for v in OFF))
check("缺省/空串 → default", as_bool(None, True) is True and as_bool("", True) is True
      and as_bool("  ", False) is False)

from tool import weather_utils as W   # noqa: E402

_real_cfg = W._read_cfg
try:
    bad = []
    for v in ("true", "1", "on", "yes", "开", "开启", ""):
        W._read_cfg = lambda v=v: {"weather_enable": v}
        if W.weather_enabled() is not True:
            bad.append(("应为开", v))
    for v in ("false", "0", "off", "no", "关", "关闭"):
        W._read_cfg = lambda v=v: {"weather_enable": v}
        if W.weather_enabled() is not False:
            bad.append(("应为关", v))
    check("weather_enabled 两个方向都对（0/off/no/关 都算关）", not bad, str(bad))
    W._read_cfg = lambda: {}
    check("weather_enable 没配 → 默认开", W.weather_enabled() is True)
finally:
    W._read_cfg = _real_cfg


def narrow_truthiness(rel):
    """`…lower() ==/!= "true"/"false"` 这类窄/反向的真值比较（AST 级，不误命中注释）"""
    _src, tree = TREES[rel]
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        vals = [c.value for c in node.comparators if isinstance(c, ast.Constant)]
        if not any(v in ("true", "false") for v in vals):
            continue
        left = ast.dump(node.left)
        if "lower" in left or "str" in left:
            out.append((node.lineno, ast.unparse(node)[:70]))
    return out


for rel in ("tool/weather_utils.py", "qq/qq_config.py", "run_wechat.py",
            "pcl_launcher/plugins_panel.py"):
    check("%-30s 窄/反向真值比较已清零" % rel, not narrow_truthiness(rel),
          str(narrow_truthiness(rel)[:1]))

# ── 3) 配置缺键：不许 KeyError + 可读提示 ───────────────────────
print("== 3) 配置「存在但缺键」==")
example = json.load(io.open(os.path.join(REPO, "config.example.json"), encoding="utf-8"))
try:
    real = json.load(io.open(os.path.join(REPO, "config.json"), encoding="utf-8"))
except Exception:
    real = {}
TOP = set(example) | set(real)
left = []
for rel, (_src, tree) in TREES.items():
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load) \
                and is_cfg_expr(node.value) and isinstance(node.slice, ast.Constant) \
                and isinstance(node.slice.value, str) and node.slice.value in TOP:
            left.append("%s:%d %s" % (rel, node.lineno, node.slice.value))
# 例外：先写后读的两处（上一行 setdefault / 同一段里先赋再读）
ALLOW = {("pcl_launcher/widgets.py", "APIKEY"), ("qq/qq_commands.py", "longtext_model_name")}
left = [x for x in left if (x.split(":")[0], x.split(" ")[-1]) not in ALLOW]
check("全仓没有「顶层配置键的读取式下标」", not left, str(left[:3]))
check("例外那两处仍是「先写后读」",
      'cfg.setdefault("APIKEY", {})' in read("pcl_launcher/widgets.py")
      and read("qq/qq_commands.py").index('cfg["longtext_model_name"] =')
      < read("qq/qq_commands.py").index("{cfg['longtext_model_name']}"))

import tool.config as C   # noqa: E402

tmp = tempfile.mkdtemp(prefix="cfgmiss_")
io.open(os.path.join(tmp, "config.example.json"), "w", encoding="utf-8").write(
    json.dumps({"model_type": "qwen", "portrait": "b", "tts_type": "local", "APIKEY": {}}))
cp = os.path.join(tmp, "config.json")
io.open(cp, "w", encoding="utf-8").write(json.dumps({"user_name": "测试用户"}))
C._missing_warned.clear()
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    got = C.get_config(cp)
check("缺键时给了一次可读提示（说清缺几个）", "4 个键" in buf.getvalue(), buf.getvalue()[:60])
check("用户的值原样返回（不合并、不覆盖）", got == {"user_name": "测试用户"}, str(got))
buf2 = io.StringIO()
with contextlib.redirect_stdout(buf2):
    C.get_config(cp)
check("第二次不重复提示（不刷屏）", buf2.getvalue().strip() == "")
io.open(cp, "w", encoding="utf-8").write(json.dumps(
    {"model_type": "qwen", "portrait": "b", "tts_type": "local", "APIKEY": {}, "user_name": "x"}))
C._missing_warned.clear()
buf3 = io.StringIO()
with contextlib.redirect_stdout(buf3):
    C.get_config(cp)
check("键齐全时不提示", buf3.getvalue().strip() == "")
C._missing_warned.clear()

# ── 4) 枚举值归一 ───────────────────────────────────────────────
print("== 4) 枚举值：读取点归一 + 不认识给提示 ==")
from tool.config import enum_of   # noqa: E402

MODEL = ("local", "qwen", "deepseek")
for raw in ("local", "Local", "LOCAL", " local ", "\tLocal\n"):
    check("%-12r → local" % raw, enum_of(raw, MODEL, "qwen", "model_type") == "local")
C._enum_warned.clear()
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    enum_of("locl", MODEL, "qwen", "mt")
    enum_of("locl", MODEL, "qwen", "mt")
msg = buf.getvalue()
check("不认识的 → 默认值 + 提示里含「值/可用取值/按什么处理」",
      "locl" in msg and "local / qwen / deepseek" in msg, msg.strip()[:80])
check("同一个错值只提示一次", msg.count("[Config]") == 1)
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    enum_of(None, MODEL, "qwen", "mt")
check("没配（None/空）→ 默认值且不提示", buf.getvalue().strip() == "")
C._enum_warned.clear()

SITES = {
    "api.py": ["enum_of(get_config(\"./config.json\").get(\"model_type\")"],
    "download.py": ["enum_of(get_config(\"./config.json\").get(\"model_type\")"],
    "classes/murasame_class.py": ["enum_of(CONFIG.get(\"model_type\")",
                                  "enum_of(CONFIG.get(\"screen_type\")"],
    "run.py": ["enum_of(cfg.get(\"tts_type\")"],
    "tool/chat.py": ["enum_of(_cfg0.get(\"tts_type\")"],
}
for rel, needles in SITES.items():
    t = read(rel)
    check("%-28s 读取点已归一" % rel, all(n in t for n in needles),
          str([n for n in needles if n not in t]))
    check("%-28s 真的导入了 enum_of" % rel,
          bool(re.search(r"from tool\.config import [^\n]*\benum_of\b", t)))

print("== 5) 端到端：配置写变体值，读出来必须归一（独立子进程）==")
tmp2 = tempfile.mkdtemp(prefix="enumcfg_")
io.open(os.path.join(tmp2, "config.json"), "w", encoding="utf-8").write(json.dumps(
    {"model_type": "Local", "tts_type": "LOCAL ", "screen_type": "True"}))
code = ("import sys; sys.path.insert(0, %r)\n"
        "sys.stdout.reconfigure(line_buffering=True)\n"
        "import tool.chat, classes.murasame_class as mc\n"
        "print('RESULT', tool.chat.tts_type, mc.model_type, mc.screen_type)\n" % REPO)
env = dict(os.environ, PYTHONIOENCODING="utf-8", QT_QPA_PLATFORM="offscreen", AIPET_NO_SPAWN="1")
r = subprocess.run([sys.executable, "-c", code], cwd=tmp2, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", env=env, timeout=240)
res = [l for l in ((r.stdout or "") + (r.stderr or "")).splitlines() if l.startswith("RESULT")]
check("子进程读到归一后的值（local / local / true）",
      bool(res) and res[0].split()[1:] == ["local", "local", "true"], str(res[:1]))
check("没有 KeyError/NameError", "KeyError" not in (r.stdout or "") + (r.stderr or "")
      and "NameError" not in (r.stdout or "") + (r.stderr or ""))

print()
if FAILS:
    print("FAILED %d 项：%s" % (len(FAILS), "、".join(FAILS)))
    sys.exit(1)
print("配置契约体检全部通过")
sys.exit(0)
