# -*- coding: utf-8 -*-
"""数值与显示参数边界体检：配置写坏时**不许忙循环、不许让模型看不见**，而且**真实数据一个都不许被改**。

覆盖两件（合并自 2026-09-29 的两个审计探针）：
  1. **数值型配置**（`tool.config.num` + 两个 worker 的间隔）
     真实案例：`camera_interval` / `screen_interval` 写 0 或负数 →
     `for _ in range(int(self.interval * 10))` 一次都不睡 → 摄像头满速抓帧（带 JPEG 编码）/
     截图线程满速抓屏**并且每轮写一个临时 PNG**（塞盘）；写 `"abc"` 则 `int()` 在**后台线程**里
     抛异常 → 线程静默死掉（界面上没有任何提示）。
  2. **pet.json 显示参数**（`pets/pet_registry.py::get_live2d_display`）
     真实案例：`live2d_scale: 0` → 模型缩成看不见；`head_bottom: 5` / `talk_top: -3` →
     摸头/对话交互区跑到屏幕外；`pcl_launcher/live2d_preview.py` 那处**连 try 都没有**。
     ⚠ 这一节的第 2 条断言是"**真实角色的值必须原样通过**" —— 加夹取时最容易忽略的就是它
     （我自己就把 `live2d_font_scale` 下界定成 0.40，而真实角色是 0.35，等于改了 3 个角色的显示）。

用法：`python tests/test_bounds.py`
"""
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.chdir(REPO)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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


from tool.config import num   # noqa: E402

print("== 1) num()：读不懂用默认、越界夹住、布尔不当数字 ==")
check("正常数值原样返回", num(5, 1) == 5.0 and num("7.5", 1) == 7.5 and num(3.25, 1) == 3.25)
check("读不懂 → 默认", all(num(v, 42) == 42.0 for v in (None, "", "  ", "abc", [], {}, object())))
check("全角数字按数字解析（Python float 的行为）", num("１２３", 42) == 123.0)
check("布尔不当数字", num(True, 9) == 9.0 and num(False, 9) == 9.0)
check("NaN → 默认", num(float("nan"), 7) == 7.0)
check("上下界夹取", num(0, 3, 1, 99) == 1.0 and num(-5, 3, 1, 99) == 1.0
      and num(1e9, 3, 1, 99) == 99.0)
check("不传界就不夹", num(-5, 3) == -5.0 and num(1e9, 3) == 1e9)

print("== 2) 两个 worker 的间隔：绝不允许变成忙循环 ==")
from classes.Worker_class import CameraWorker, ScreenWorker   # noqa: E402

for label, val in (("0", 0), ("负数", -30), ("字符串", "abc"), ("None", None),
                   ("超大", 10 ** 9), ("NaN", float("nan"))):
    w = CameraWorker(interval_sec=val)
    check("摄像头 interval=%s → %.1f 秒（在 [1, 86400]）" % (label, w.interval),
          1.0 <= w.interval <= 86400.0)
    check("  间隔=%s 时 sleep 循环次数 ≥1（这一条才是那个隐患的本质）" % label,
          max(1, int(w.interval * 10)) >= 1)
    s = ScreenWorker(interval_sec=val)
    check("截图 interval=%s → %.1f 秒（在 [1, 3600]）" % (label, s.interval),
          1.0 <= s.interval <= 3600.0)
check("缺省值不变（摄像头 300 / 截图 3）",
      CameraWorker().interval == 300.0 and ScreenWorker().interval == 3.0)
check("摄像头编号被夹成非负整数", CameraWorker(camera_id=-1).camera_id == 0
      and CameraWorker(camera_id="abc").camera_id == 0)

wk = open(os.path.join(REPO, "classes", "Worker_class.py"), encoding="utf-8").read()
check("两处 sleep 循环都有 max(1, ...) 兜底",
      wk.count("for _ in range(max(1, int(self.interval * 10))):") == 2,
      "%d 处" % wk.count("for _ in range(max(1, int(self.interval * 10))):"))
check("screen_index 不再用直接下标",
      'get_config("./config.json")["screen_index"]' not in wk)

print("== 3) pet.json 显示参数：敌意输入被夹、**真实角色数据原样通过** ==")
import pets.pet_registry as pr   # noqa: E402
from pets.pet_registry import get_live2d_display   # noqa: E402

BAD = {
    "model": {"live2d_scale": "abc", "live2d_offset_x": -99999, "live2d_offset_y": 1e9,
              "live2d_window_ratio": 0, "live2d_window_height_ratio": 9.9,
              "live2d_font_scale": 0},
    "interaction": {"head_top": -5, "head_bottom": 5, "talk_top": -3, "talk_bottom": 99,
                    "edge_margin_x": 99, "text_offset_x": "x", "text_offset_y": 1e9},
}
WANT = {"window_ratio": (0.2, 3.0), "window_height_ratio": (0.10, 0.95),
        "scale": (0.30, 2.00), "offset_x": (-800.0, 800.0), "offset_y": (-800.0, 800.0),
        "font_scale": (0.10, 3.00), "head_top": (0.0, 1.0), "head_bottom": (0.0, 1.0),
        "talk_top": (0.0, 1.0), "talk_bottom": (0.0, 1.0), "edge_margin_x": (0.0, 0.5),
        "text_offset_x": (-10000.0, 10000.0), "text_offset_y": (-10000.0, 10000.0)}
_real_get = pr.get_pet_config
try:
    pr.get_pet_config = lambda pid=None: BAD
    bad_out = get_live2d_display("fake_hostile")
finally:
    pr.get_pet_config = _real_get
for k, (lo, hi) in sorted(WANT.items()):
    v = bad_out.get(k)
    check("%-22s → %-10s 在 [%s, %s] 内" % (k, v, lo, hi),
          isinstance(v, float) and lo - 1e-9 <= v <= hi + 1e-9)
check("离谱值夹到边界本身（而不是只回默认）",
      bad_out["offset_x"] == -800.0 and bad_out["head_bottom"] == 1.0
      and bad_out["window_ratio"] == 0.2)
check("读不懂的 → 默认值", bad_out["scale"] == 1.0 and bad_out["text_offset_x"] == 0.0)

pd = os.path.join(REPO, "pets")
n_pet = 0
for name in sorted(os.listdir(pd)):
    pj = os.path.join(pd, name, "pet.json")
    if not os.path.isfile(pj):
        continue
    try:
        cfg = json.load(open(pj, encoding="utf-8"))
    except Exception:
        continue
    m, i = cfg.get("model") or {}, cfg.get("interaction") or {}
    got = get_live2d_display(name)
    pairs = [("window_ratio", m.get("live2d_window_ratio")),
             ("window_height_ratio", m.get("live2d_window_height_ratio")),
             ("scale", m.get("live2d_scale")), ("offset_x", m.get("live2d_offset_x")),
             ("offset_y", m.get("live2d_offset_y")), ("font_scale", m.get("live2d_font_scale")),
             ("head_top", i.get("head_top")), ("head_bottom", i.get("head_bottom")),
             ("talk_top", i.get("talk_top")), ("talk_bottom", i.get("talk_bottom")),
             ("edge_margin_x", i.get("edge_margin_x")), ("text_offset_x", i.get("text_offset_x")),
             ("text_offset_y", i.get("text_offset_y"))]
    diffs = [(k, raw, got[k]) for k, raw in pairs
             if raw is not None and abs(float(raw) - got[k]) > 1e-9]
    n_pet += 1
    check("%-10s 13 个显示参数原样通过" % name, not diffs, str(diffs[:2]))
check("确实扫到了多个角色（别因为找不到文件而「通过」）", n_pet >= 4, "%d 个" % n_pet)

real_vals = {}
for name in sorted(os.listdir(pd)):
    pj = os.path.join(pd, name, "pet.json")
    if not os.path.isfile(pj):
        continue
    try:
        cfg = json.load(open(pj, encoding="utf-8"))
    except Exception:
        continue
    for sec in (cfg.get("model") or {}, cfg.get("interaction") or {}):
        for k, v in sec.items():
            try:
                real_vals.setdefault(k, []).append(float(v))
            except (TypeError, ValueError):
                pass
for k, (lo, hi) in sorted(WANT.items()):
    real = real_vals.get("live2d_" + k) or real_vals.get(k)
    if not real:
        continue
    check("%-22s 真实 [%s, %s] 落在夹取范围 [%s, %s] 内"
          % (k, min(real), max(real), lo, hi), min(real) >= lo - 1e-9 and max(real) <= hi + 1e-9)

print("== 4) 绕过 registry 的直接读取点也要夹（源码守卫）==")
GUARDS = [
    ("pcl_launcher/live2d_preview.py", ['num(disp.get("scale"), 1.0, 0.30, 2.00)',
                                        'num(disp.get("offset_x"), 0.0, -800.0, 800.0)']),
    ("pcl_launcher/pet_wizard.py", ['num(values.get("height_ratio"), 0.45, 0.10, 0.95)']),
    ("classes/murasame_class.py", ['num(_pet_cfg.get("model", {}).get("live2d_font_scale"), 1.0, 0.10, 3.00)',
                                   'num(_pet_cfg.get("interaction", {}).get("text_offset_x"), 0, -10000, 10000)',
                                   'num(_pet_cfg.get("model", {}).get("portrait_height_ratio")']),
]
for rel, needles in GUARDS:
    t = open(os.path.join(REPO, rel), encoding="utf-8").read()
    check("%-34s 都走 num()" % rel, all(n in t for n in needles),
          str([n for n in needles if n not in t]))
check("这些文件都真的导入了 num",
      all(re.search(r"from tool\.config import [^\n]*\bnum\b",
                    open(os.path.join(REPO, r), encoding="utf-8").read())
          for r in ("pcl_launcher/live2d_preview.py", "pcl_launcher/pet_wizard.py",
                    "classes/murasame_class.py", "pets/pet_registry.py")))

print()
if FAILS:
    print("FAILED %d 项：%s" % (len(FAILS), "、".join(FAILS)))
    sys.exit(1)
print("边界体检全部通过")
sys.exit(0)
