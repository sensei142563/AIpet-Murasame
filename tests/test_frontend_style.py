# -*- coding: utf-8 -*-
"""前端一致性体检：**同类控件口径统一**（尤其滑块方向）与**字号跟随缩放**。

用户提的问题（2026-09-30）："新功能的前端是否清晰、风格是否一致，像滑块啥的是否样式方向统一"。
这一份把"能机器判的那部分"固定下来：

1. **两态滑块方向**：一律 `["false", "true"]`（左=假/关，右=真/开）。
   非布尔的多元选项没有"天然方向"，所以必须进**白名单**逐个人工确认 ——
   新加一个控件就会报出来要人拍板（这正是用户说的"方向统一"能被守住的方式）。
2. **同一个键不许同时用两种控件描述**（会互相覆盖，设置页存了也没用）。
3. **字号跟随缩放**：会缩放的页面里不许写死 `font-size: Npx`（应当 `int(N*S)`）——
   真实案例：状态页原来写死 12px/11px，而插件页全是 `int(12*S)`，用户改缩放时状态页不跟随。
   `silicon_window.py`（外壳）目前仍是固定字号：**已知例外**，这里钉住它的数量不许增长。
4. **颜色不写死**：新面板不许出现 hex/rgb 字面量当文字色；
   `color: white` 必须与 `fill_for_text(...)` 成对（那是仓库里"填色+白字"的官方配对，
   colors.py 里专门解释了对比度计算），否则算硬编码。

用法：`python tests/test_frontend_style.py`
"""
import glob
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


def read(rel):
    return open(os.path.join(REPO, rel), encoding="utf-8").read()


W = read("pcl_launcher/widgets.py")

print("== 1) 两态滑块方向：左=假 / 右=真 ==")
PAT = re.compile(r'_add_slider\(\s*"([A-Za-z_][\w]*)"\s*,\s*"([^"]*)"\s*,\s*\[([^\]]*)\]')
BOOLISH = {"true", "false", "on", "off", "yes", "no", "1", "0"}
# 非布尔的多元选项：**必须逐个人工确认方向**（加新控件时会报出来）
ALLOW_OTHER = {
    ("portrait", ("a", "b")),                       # 立绘类型：a/b 不是布尔
    ("model_type", ("local", "deepseek", "qwen")),  # 本地→云端→另一家云
    ("reasoning_level", ("off", "low", "high", "max")),   # 思考强度递增
    ("tts_type", ("local", "cloud")),               # 离线→在线
    ("vision_source", ("local", "cloud")),          # 与 tts_type 同一根轴（离线→在线）
    ("longtext_model", ("qwen", "deepseek")),
}
bad_dir, unknown = [], []
n_bool = 0
for m in PAT.finditer(W):
    key, label, opts = m.group(1), m.group(2), re.findall(r'"([^"]*)"', m.group(3))
    tup = tuple(opts)
    if all(v.lower() in BOOLISH for v in opts):
        n_bool += 1
        if tup != ("false", "true"):
            bad_dir.append("%s %s（应为 ['false','true']）" % (key, list(tup)))
    elif (key, tup) not in ALLOW_OTHER:
        unknown.append("%s %s" % (key, list(tup)))
check("布尔滑块全部是 左=假/右=真（%d 个）" % n_bool, not bad_dir, str(bad_dir[:3]))
check("非布尔滑块的顺序都经过人工确认（新控件必须来登记）", not unknown, str(unknown[:3]))
check("vision_source 与 tts_type 同一方向（离线在左）",
      '_add_choice("vision_source", "视觉来源", ["local", "cloud"], "cloud"' in W)

print("== 2) 同一个键不许同时用两种控件描述 ==")
sl = set(re.findall(r'_add_slider\(\s*"([A-Za-z_][\w]*)"', W))
ch = set(re.findall(r'_add_choice\(\s*"([A-Za-z_][\w]*)"', W))
both = sorted(sl & ch)
check("没有既是滑块又是选择器的键", not both, str(both))

print("== 3) 字号跟随缩放（写死 px 只在已知例外里）==")
FONTSIZE = re.compile(r"font-size:\s*\d+px")
SCALED = re.compile(r"int\(\s*\d+\s*\*\s*S\s*\)")
SHOULD_SCALE = ["pcl_launcher/plugins_panel.py", "pcl_launcher/status_panel.py",
                "pcl_launcher/widgets.py", "pcl_launcher/themes_panel.py",
                "pcl_launcher/pet_slots.py"]
for rel in SHOULD_SCALE:
    src = read(rel)
    hard = [(i, ln.strip()[:66]) for i, ln in enumerate(src.splitlines(), 1)
            if FONTSIZE.search(ln) and "int(" not in ln]
    check("%-34s 没有写死字号（%d 处跟随缩放）" % (rel, len(SCALED.findall(src))), not hard,
          str(hard[:2]))
shell = read("pcl_launcher/silicon_window.py")
n_shell = len([1 for ln in shell.splitlines() if FONTSIZE.search(ln) and "int(" not in ln])
check("外壳 silicon_window.py 的固定字号数量没增长（已知例外，当前 %d 处）" % n_shell,
      n_shell <= 16, "%d 处" % n_shell)

print("== 4) 颜色不写死（新面板）==")
HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
for rel in ("pcl_launcher/plugins_panel.py", "pcl_launcher/status_panel.py"):
    src = read(rel)
    hits = [(i, ln.strip()[:70]) for i, ln in enumerate(src.splitlines(), 1)
            if HEX.search(ln) and "readable_on" not in ln and not ln.strip().startswith("#")]
    check("%-34s 没有裸 hex 颜色（走主题变量）" % rel, not hits, str(hits[:2]))
for rel in ("pcl_launcher/plugins_panel.py", "pcl_launcher/status_panel.py",
            "pcl_launcher/widgets.py"):
    src = read(rel)
    # 变量形式的底色：只要它在**同一文件里**是用 fill_for_text / readable_on 算出来的就放行
    safe_vars = set()
    for ln in src.splitlines():
        m = re.match(r"\s*([A-Za-z_]\w*)\s*=", ln)
        if m and ("fill_for_text(" in ln or "readable_on(" in ln
                  or "accent_hex()" in ln):
            safe_vars.add(m.group(1))
    safe_vars |= {"_btn_style"}          # 参数化助手：对比度由调用方负责（调用点已单独验）
    bad = []
    for i, ln in enumerate(src.splitlines(), 1):
        if not re.search(r"color:\s*white\b", ln):
            continue
        if "fill_for_text" in ln:
            continue
        # ⚠ 别要求 `{name}` 后面紧跟 `}`：实际写法多是 `{_fill.name()}` / `{bg}` 混用
        m = re.search(r"background:\s*\{([A-Za-z_]\w*)", ln)
        if m and (m.group(1) in safe_vars or m.group(1) in ("bg", "_badge_bg")):
            continue
        bad.append((i, ln.strip()[:66]))
    check("%-34s color:white 的底色都调过对比度" % rel, not bad, str(bad[:2]))

print("== 5) 侧边栏图标：主题有图标就必须**每个**导航项都有（新加栏目最容易漏）==")
SW = read("pcl_launcher/silicon_window.py")
nav_block = re.search(r"^NAV = \[(.*?)^\]", SW, re.S | re.M)
nav_keys = re.findall(r'\(\s*"([a-z_]+)"\s*,', nav_block.group(1)) if nav_block else []
check("能从 silicon_window.py 解析出 NAV 列表", len(nav_keys) >= 6, str(nav_keys))
# 总览复用 model 图标（源码里写死的映射）；改成别的写法时这里要跟着改，所以直接读源码判断
home_uses_model = '"model" if key == "home"' in SW
want_keys = {(("model" if home_uses_model else "home") if k == "home" else k) for k in nav_keys}
want_keys |= set(re.findall(r'icon_key="([a-z_]+)"', SW))      # 如设置按钮 icon_key="settings"
check("需要的图标键集合（含总览复用 model / 设置按钮）", len(want_keys) >= 8, str(sorted(want_keys)))

for tp in sorted(glob.glob(os.path.join(REPO, "pcl_launcher", "themes", "*", "theme.json"))):
    tdir = os.path.dirname(tp)
    cfg = json.load(open(tp, encoding="utf-8"))
    ni = cfg.get("nav_icons") or {}
    tname = os.path.basename(tdir)
    if not ni:
        print("  [--]   %-20s 没声明 nav_icons → 全部用 emoji（纯符号主题，正常）" % tname)
        continue
    got = set(ni)
    missing = sorted(want_keys - got)
    extra = sorted(got - want_keys)
    check("%-20s 图标键齐全（%d 个）" % (tname, len(got)), not missing, "缺：%s" % missing)
    check("%-20s 没有没人用的死键" % tname, not extra, "多余：%s" % extra)
    bad = [k for k, v in ni.items() if not os.path.isfile(os.path.join(tdir, v))]
    check("%-20s 图标文件都在（%d 张）" % (tname, len(ni)), not bad, "缺文件：%s" % bad)

print()
print("== 6) 真加载：切到千恋万花主题后，每个导航键都能取到图 ==")
from PyQt5.QtGui import QPixmap   # noqa: E402
from PyQt5.QtWidgets import QApplication   # noqa: E402
app = QApplication(sys.argv[:1])
import pcl_launcher.colors as C   # noqa: E402
_old = getattr(C, "_ACTIVE_THEME_ID", "")
try:
    C._ACTIVE_THEME_ID = "senrenbanka"
    from pcl_launcher.colors import nav_icon_path   # noqa: E402
    for k in sorted(want_keys):
        p = nav_icon_path(k)
        ok = bool(p) and os.path.isfile(p)
        pm = QPixmap(p) if ok else QPixmap()
        check("%-10s 有图且能解码（最宽缩到 40px 仍非空）" % k,
              ok and not pm.isNull() and not pm.scaled(40, pm.height() or 40).isNull(),
              os.path.basename(p) if p else "（空 → 会退回 emoji）")
finally:
    C._ACTIVE_THEME_ID = _old

print()
if FAILS:
    print("FAILED %d 项：%s" % (len(FAILS), "、".join(FAILS)))
    sys.exit(1)
print("前端一致性体检全部通过")
sys.exit(0)
