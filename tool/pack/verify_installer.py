# -*- coding: utf-8 -*-
"""最终验收：静默安装到临时目录 + 校验（运行环境/说明书/快捷方式/启动器可启动）"""

try:  # 控制台被重定向（管道/日志）时 Windows 会用 GBK 编码 stdout，
    # 打印 emoji 会 UnicodeEncodeError 直接打断进程 → 统一降级成替换字符
    import sys as _sys
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(ROOT)          # tmp/ → 项目根
EXE = os.path.join(ROOT, "AIpet-Murasame-安装包.exe")
import tempfile
TEST = os.path.join(tempfile.gettempdir(), "AIpet-安装测试")   # 用临时目录，避免硬编码他人盘符
SHORTCUT = os.path.join(os.path.expanduser("~"), "Desktop", "AIpet 丛雨桌宠.lnk")

print("安装包:", EXE, os.path.getsize(EXE) / 1e9, "GB")
shutil.rmtree(TEST, ignore_errors=True)
try:
    os.remove(SHORTCUT)
except Exception:
    pass

print("启动安装器…")
p = subprocess.Popen([EXE, "/S", "/D=" + TEST], shell=False,
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
log = os.path.join(TEST, "安装日志.txt")
for i in range(120):
    if os.path.exists(log):
        break
    rc = p.poll()
    if rc is not None and not os.path.exists(log):
        print(f"❌ 安装器提前退出，返回码 {rc}")
        sys.exit(2)
    time.sleep(4)
else:
    print("❌ 超时：未见安装日志")
    sys.exit(3)

print("=== 安装日志 ===")
print(open(log, encoding="utf-8").read())

def chk(rel):
    return os.path.exists(os.path.join(TEST, rel))

checks = [
    ("启动器 exe", "AIpet-Murasame.exe"),
    ("启动器 _internal（含 cv2.pyd）", r"_internal\cv2\cv2.pyd"),
    ("源码 run.py", "run.py"),
    ("运行环境 python.exe", r"runtime\venv\Scripts\python.exe"),
    ("运行环境 venv 配置", r"runtime\venv\pyvenv.cfg"),
    ("便携解释器", r"python\python.exe"),
    ("立绘工坊模块", r"pcl_launcher\portrait_studio.py"),
    ("装扮模块", r"tool\portrait_outfit.py"),
    ("场景素材图", r"场景素材\IMG_6321.JPG"),
    ("QQ 桥接", "run_qq.py"),
    ("NapCat", r"NapCat.Shell.Windows.OneKey"),
    ("说明书 txt", "使用教程说明书.txt"),
    ("说明书 html", "使用教程说明书.html"),
    ("生成的 config.json", "config.json"),
]
print("=== 关键文件 ===")
bad = [n for n, r in checks if not chk(r)]
for n, r in checks:
    print(("  ✅ " if chk(r) else "  ❌ ") + n)

print("=== NapCat / QQ 版本（应等于根目录 NAPCAT_VERSION.txt 的锁定值）===")
try:
    import re as _re
    _anchor = {}
    _ap = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                       "NAPCAT_VERSION.txt")
    if os.path.isfile(_ap):
        for _ln in open(_ap, encoding="utf-8"):
            _ln = _ln.split("#")[0].strip()
            if "=" in _ln:
                _k, _v = _ln.split("=", 1)
                _anchor[_k.strip()] = _v.strip()
    _mjs = os.path.join(TEST, "NapCat.Shell.Windows.OneKey", "NapCat", "napcat.mjs")
    _got = ""
    if os.path.isfile(_mjs):
        with open(_mjs, encoding="utf-8", errors="replace") as _f:
            _m = _re.search(r'&&\s*"(\d+\.\d+\.\d+)"', _f.read(4_000_000))
        _got = _m.group(1) if _m else ""
    _want = _anchor.get("napcat", "")
    print("  NapCat: 实际 %s / 锁定 %s → %s"
          % (_got or "未读到", _want or "未读到",
             "一致"if (_got and _got == _want) else "不一致（打包机上的 NapCat 被更新过？）"))
    _vj = os.path.join(TEST, "NapCat.Shell.Windows.OneKey", "bootmain", "versions", "config.json")
    if os.path.isfile(_vj):
        import json as _json
        _d = _json.load(open(_vj, encoding="utf-8"))
        _cur = str(_d.get("curVersion") or _d.get("baseVersion") or "")
        _max = _anchor.get("qq_max_supported", "")
        print("  QQ: 实际 %s / 支持上限 %s → %s"
              % (_cur or "未知", _max or "未知",
                 "在支持范围内"if (not _max or _cur <= _max)
                 else "超出支持表（NapCat 会报「不支持当前QQ版本架构」）"))
except Exception as _e:
    print("  版本校验失败（不影响其它检查）: %s" % _e)

print("=== pyvenv.cfg ===")
cfg = os.path.join(TEST, "runtime", "venv", "pyvenv.cfg")
print(open(cfg, encoding="utf-8").read().strip() if os.path.exists(cfg) else "(缺失)")

print("=== 桌面快捷方式 ===")
print("  存在:", os.path.exists(SHORTCUT), "|", SHORTCUT)

print("=== 运行环境自检（按 main.py 的顺序：先 torch 再其它）===")
py = os.path.join(TEST, "runtime", "venv", "Scripts", "python.exe")
probe = (
    "import os, sys, site\n"
    "tp = os.path.join(site.getsitepackages()[0], 'torch', 'lib')\n"
    "if os.path.exists(tp):\n"
    "    os.add_dll_directory(tp); os.environ['PATH'] = tp + os.pathsep + os.environ.get('PATH','')\n"
    "import torch; print('torch', torch.__version__)\n"
    "import numpy, cv2, PyQt5, requests, soundfile\n"
    "print('cv2', cv2.__version__, '| numpy', numpy.__version__)\n"
    "sys.path.insert(0, r'" + TEST + "')\n"
    "from tool.portrait_outfit import CLOTHES_BY_SET\n"
    "from pcl_launcher.portrait_studio import PortraitStudio\n"
    "print('立绘工坊/装扮模块导入 OK')\n"
)
r = subprocess.run([py, "-c", probe], cwd=TEST, capture_output=True,
                   text=True, encoding="utf-8", errors="replace",
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
print(r.stdout.strip() or r.stderr.strip()[-500:])

print("=== 安装副本启动器能否运行 ===")
p2 = subprocess.Popen([os.path.join(TEST, "AIpet-Murasame.exe")], cwd=TEST,
                      creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
time.sleep(12)
alive = p2.poll() is None
print("  启动器存活:", alive)
if not alive:
    out = p2.stdout.read().decode("utf-8", "replace") if p2.stdout else ""
    print("  输出:", out[-800:])
else:
    subprocess.run(["taskkill", "/PID", str(p2.pid), "/T", "/F"],
                   capture_output=True)
print("=== 结论 ===")
print("关键文件缺失:", bad if bad else "无")
print("启动器可启动:", alive)
