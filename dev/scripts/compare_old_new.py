# -*- coding: utf-8 -*-
"""新旧版对照：新版到底多了什么（能力 / 资源管理），快不快、显存省不省要看哪些开关。
   原则：只列**能指出来**的东西；速度/显存**没有实测就不下结论**。
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OLD = r"E:\university\order\python\pet\AIpet-Murasame-main_V1.17.2\AIpet-Murasame-main"
NEW = r"E:\university\order\python\pet\AIpet-Murasame-main"

# ① 顶层目录对照
print("=== ① 顶层目录对照（新版有、旧版没有 的用 + 标）===")
def tops(root):
    try:
        return {d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))}
    except Exception as e:
        return set()
o, n = tops(OLD), tops(NEW)
print("   新版独有:", "、".join(sorted(n - o)) or "（无）")
print("   旧版独有:", "、".join(sorted(o - n)) or "（无）")

# ② 关键文件/模块是否存在
KEYS = {
    "3D / VRM 形象": ["assets/vrm/index.html"],
    "启动器（PCL 风格）": ["pcl_launcher/silicon_window.py"],
    "立绘工坊": ["pcl_launcher/portrait_studio.py"],
    "状态页数据": ["tool/status_snapshot.py"],
    "关系值下限": ["tool/state.py"],
    "自学/归纳": ["tool/self_learn.py"],
    "语音服务管家（预载/换模型）": ["tool/tts_service.py"],
    "本地视觉服务": ["tool/vision_service.py"],
    "本地视觉开关": ["tool/vision_local.py"],
    "主动开口（注意力）": ["tool/attention.py"],
    "微信 ClawBot": ["qq/qq_wechat.py"],
    "手机端（同一后端协议）": ["docs/手机端-后端协议.md"],
    "打包/安装器": ["tool/pack/build_installer.py"],
}
print()
print("=== ② 关键能力对照（文件存在性）===")
print("   %-30s %-10s %-10s" % ("能力", "旧版", "当前版"))
for name, rels in KEYS.items():
    def y(root):
        return "有" if any(os.path.exists(os.path.join(root, r)) for r in rels) else "—"
    print("   %-30s %-10s %-10s" % (name, y(OLD), y(NEW)))

# ③ 资源管理相关的开关（真正影响速度/显存的东西）
print()
print("=== ③ 影响速度/显存的开关（有就是有，没有就是没有）===")
KNOBS = ["vision_idle_unload", "quiet_mode", "short_tts_gpu", "BELOW_NORMAL_PRIORITY_CLASS",
         "longtext_enabled", "voice_synthesis_enable", "is_half", "expandable_segments",
         "PYTORCH_HIP_ALLOC_CONF", "_tts_use_gpu", "preload", "tts_service"]
for tag, root in (("旧版", OLD), ("当前版", NEW)):
    found = []
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in
                 {"GPT-SoVITS", "runtime", ".venv", "site-packages", ".git",
                  "_import_tmp", "dev", "docs", "NapCat.Shell.Windows.OneKey", "__pycache__"}]
        for f in fn:
            if not f.endswith(".py"):
                continue
            try:
                src = io.open(os.path.join(dp, f), encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            for k in KNOBS:
                if k in src and k not in found:
                    found.append(k)
    print("   %-6s %s" % (tag, "、".join(sorted(found)) or "（无）"))
