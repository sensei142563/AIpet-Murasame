# -*- coding: utf-8 -*-
"""① 修 widgets.py 里另外 2 处 `vision_source or "local"`（881 载入控件状态 / 1028 状态探测）
   ② 修 358-360 那段过时注释（"默认就是 local"）
   ③ 收窄测试断言：只查 **vision_source** 的那次 _add_choice，不要把 TTS 的 tts_type 误伤
      （我上一版把模式写成 ["local","cloud"], "local"，结果命中 tts_type —— 误报）
      并补一条"全仓不得再有 vision_source … or local"的守卫。
"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
WG = os.path.join(ROOT, "pcl_launcher", "widgets.py")
TF = os.path.join(ROOT, "tests", "test_vision_interface.py")

# ---------- ①② widgets.py ----------
w = io.open(WG, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
n = 0
for old, new, tag in [
    ('self._set_slider("vision_source", str(cfg.get("vision_source") or "local"))',
     'self._set_slider("vision_source", str(cfg.get("vision_source") or "cloud"))',
     "881 载入控件状态"),
    ('if str(cfg.get("vision_source") or "local").strip().lower() != "local":',
     'if str(cfg.get("vision_source") or "cloud").strip().lower() != "local":',
     "1028 状态探测"),
    ('#   （tool/vision_service.py + tool/chat.describe_image），默认就是 local。',
     '#   （tool/vision_service.py + tool/chat.describe_image）。\n'
     '#   ⚠ 注意：那是**上游**那套的语义（上游默认 local）；本工程的实现默认是 **cloud**，',
     "358 注释更正"),
]:
    if old in w:
        w = w.replace(old, new, 1)
        n += 1
        print("✓ widgets.py 修了", tag)
    else:
        print("✗ widgets.py 锚点未命中:", tag)
io.open(WG, "w", encoding="utf-8", newline="\n").write(w)
print("   widgets.py 共修 %d 处" % n)

# ---------- ③ 收窄断言 ----------
t = io.open(TF, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
OLD = '''# ② 防回归：不允许出现"默认选 local"的写法（无论标签叫什么）
check("设置页**没有**把 vision_source 默认写成 local（防回归）",
      '["local", "cloud"], "local"' not in w)'''
NEW = '''# ② 防回归：vision_source 那一次 _add_choice 的默认值必须是 cloud。
#    ⚠ 上一版把模式写成 `["local", "cloud"], "local"` —— 结果命中的是 **TTS** 的
#      `_add_choice("tts_type", "TTS 语音合成", ["local", "cloud"], "local")`（合理配置），
#      属于**误报**。所以这里必须带上键名，只盯 vision_source 这一处。
check("设置页 vision_source 默认不是 local（防回归，只盯这一处）",
      '_add_choice("vision_source", "识别来源", ["local", "cloud"], "local"' not in w)'''
if OLD in t:
    t = t.replace(OLD, NEW, 1)
    print("✓ 测试：已收窄断言（只盯 vision_source 的 _add_choice，不误伤 tts_type）")
else:
    print("✗ 测试锚点未命中（断言 ②）")

OLD2 = '''# ④ 启动器侧同样不得把"没配"当成 local（2026-10-13 修过的 bug：首页会写"本地视觉模型（本地部署）"）
sw = io.open(os.path.join(REPO, "pcl_launcher", "silicon_window.py"), encoding="utf-8").read()
check("启动器不再把 vision_source 缺省当 local（防回归）",
      'cfg.get("vision_source") or "local"' not in sw
      and '_vcfg.get("vision_source") or "local"' not in sw)'''
NEW2 = '''# ④ 全仓守卫：任何地方都不得再写 `vision_source … or "local"`（缺省必须是 cloud）。
#    2026-10-13 修过的 bug：启动器首页会因此写"本地视觉模型（本地部署）"，
#    而 set_slider 载入状态、设置页状态探测两处也有同样写法 —— 一并由本条守住。
_bad = []
for _rel in ("pcl_launcher/silicon_window.py", "pcl_launcher/widgets.py",
             "pcl_launcher/plugins_panel.py"):
    _p = os.path.join(REPO, _rel)
    if os.path.isfile(_p):
        _s = io.open(_p, encoding="utf-8").read()
        if 'vision_source") or "local"' in _s:
            _bad.append(_rel)
check("没有任何文件把 vision_source 缺省当 local（防回归）",
      not _bad, "命中：" + ", ".join(_bad))'''
if OLD2 in t:
    t = t.replace(OLD2, NEW2, 1)
    print("✓ 测试：已把断言 ④ 扩成全仓守卫")
else:
    print("✗ 测试锚点未命中（断言 ④）")

io.open(TF, "w", encoding="utf-8", newline="\n").write(t)

print()
print("=== 复核 widgets.py 残留 ===")
for i, l in enumerate(io.open(WG, encoding="utf-8", errors="replace").read().split("\n"), 1):
    if 'vision_source' in l and 'or "local"' in l:
        print("   ✗ 仍有: 第 %d 行 %s" % (i, l.strip()[:104]))
print("   （无输出 = 干净 ✓）")

print()
print("=== 单跑测试 ===")
import subprocess  # noqa: E402
r = subprocess.run([os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe"),
                    os.path.join(ROOT, "tests", "test_vision_interface.py")],
                   capture_output=True, text=True, encoding="utf-8", errors="replace",
                   timeout=600, cwd=ROOT)
out = (r.stdout or "") + (r.stderr or "")
for l in out.split("\n")[-6:]:
    print("   " + l.strip()[:130])
