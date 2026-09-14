# -*- coding: utf-8 -*-
"""最终验收：静默安装到临时目录 + 校验（运行环境/说明书/快捷方式/启动器可启动）"""
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(ROOT)          # tmp/ → 项目根
EXE = os.path.join(ROOT, "AIpet-Murasame-安装包.exe")
TEST = r"D:\AIpet-安装测试"
SHORTCUT = os.path.join(r"D:\桌面图标", "AIpet 丛雨桌宠.lnk")   # 本机桌面被重定向到 D:\桌面图标

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
