# -*- coding: utf-8 -*-
"""收尾：修 widgets.py 的加载默认值（886-896）与下拉框选项，然后编译 + 自检。"""
import io
import os
import py_compile
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
P = os.path.join(ROOT, "pcl_launcher", "widgets.py")
t = io.open(P, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")

PAIRS = [
    # 载入配置时的默认值：本地视觉两项 → 空；模型名默认 → qwen3-vl-plus
    ('''            self._set_if("vision_local_model_dir",
                         cfg.get("vision_local_model_dir",
                                 r"D:\\下载\\AI桌宠\\vision\\Qwen2-VL-2B-Instruct"))''',
     '''            # ⚠ 2026-10-14：默认值从"一个不存在的示例路径"改成空串
            #   （本地视觉既定不使用，界面上别显示一个机器上根本没有的目录）
            self._set_if("vision_local_model_dir",
                         cfg.get("vision_local_model_dir", ""))'''),
    ('''            self._set_if("vision_service_url",
                         (cfg.get("local_api") or {}).get(
                             "vision", "http://127.0.0.1:28460/describe"))''',
     '''            self._set_if("vision_service_url",
                         (cfg.get("local_api") or {}).get("vision", ""))'''),
    ('''            self._set_if("vision_model_name", cfg.get("vision_model_name", "deepseek-flash"))''',
     '''            # 视觉模型默认名：qwen3-vl-plus（旧名 qwen-vl-plus / qwen-vl-max 已下线）
            self._set_if("vision_model_name", cfg.get("vision_model_name", "qwen3-vl-plus"))'''),
    # 下拉框：去掉实测不存在的 qwen3-vl-flash，保留可用的 qwen3-vl-plus
    ('"qwen3-vl-plus", "qwen3-vl-flash"],', '"qwen3-vl-plus"],'),
]
n = 0
for old, new in PAIRS:
    if old in t:
        t = t.replace(old, new, 1)
        n += 1
    else:
        print("   · 未命中：%s…" % old.strip().split("\n")[0][:70])
io.open(P, "w", encoding="utf-8", newline="\n").write(t)
print("✓ widgets.py 改了 %d 处" % n)

try:
    py_compile.compile(P, doraise=True)
    print("✓ py_compile OK（widgets.py 已恢复健康）")
except Exception as e:
    print("✗ py_compile: %s" % e)
    sys.exit(1)

print()
print("=== 复核剩下的旧值/空值 ===")
ls = io.open(P, encoding="utf-8", errors="replace").read().split("\n")
for i, l in enumerate(ls, 1):
    if re.search(r"28460|Qwen2-VL|qwen3-vl|vision_service_url|vision_local_model_dir|"
                 r"vision_model_name", l):
        print("   %5d| %s" % (i, l.strip()[:104]))

print()
print("=== 全量自检 ===")
import subprocess  # noqa: E402
r = subprocess.run([os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe"),
                    os.path.join(ROOT, "tests", "run_all.py")],
                   cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=1800)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n")[-4:]:
    print("   " + l.strip()[:120])
