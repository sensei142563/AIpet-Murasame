# -*- coding: utf-8 -*-
"""把"启动器一起来就自动预载语音服务"改成**默认关闭**（可用 config 开关恢复）。
   主人的原话：'这个，应该是打开桌宠以后再运行啊，我都没确定打开哪个桌宠'。
"""
import io
import os
import py_compile
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
P = os.path.join(ROOT, "pcl_launcher", "silicon_window.py")

t = io.open(P, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")

# ---------- ① 排定时的那句注释与调用：说明改为需显式开启 ----------
OLD1 = """        # ── 启动器一起来就自动预热语音服务（合并保留的功能）────────────────
        # 首次加载 GPT-SoVITS 模型要 1~2 分钟；提前热好，桌宠开口第一句几乎不用等。
        # 和点「预载语音服务」走同一条路（preload_tts），只是不用手动点；
        # 云端语音 / 关掉短语音时不预热（判断见 _auto_preload_tts）。
        try:"""
NEW1 = """        # ── 自动预热语音服务（**默认关闭**，见 _auto_preload_tts 里的开关）──
        # 首次加载 GPT-SoVITS 模型要 1~2 分钟；提前热好，桌宠开口第一句几乎不用等。
        # 但★ 2026-10-14 主人反馈：**还没选要开哪只桌宠**，启动器就自己预载并弹出控制台，
        #   这不对。所以现在默认不自动预载；启动桌宠时（run.py）才会把语音服务拉起来。
        #   想恢复"开启动器就预热"：config.json 里写 "auto_preload_tts": "true"。
        try:"""
if OLD1 in t:
    t = t.replace(OLD1, NEW1, 1)
    print("✓ ① 注释与语义已更新（默认不自动预载）")
else:
    print("✗ ① 锚点未命中")

# ---------- ② 在 _auto_preload_tts 开头加开关判断 ----------
OLD2 = '''    def _auto_preload_tts(self):
        """启动器启动后自动预热本地语音服务（只用本地 TTS 且开着短语音时才做）。"""
        try:
            if getattr(self.shell, "_tts_proc", None) is not None:'''
NEW2 = '''    def _auto_preload_tts(self):
        """启动器启动后自动预热本地语音服务（**默认关闭**；只用本地 TTS 且开着短语音时才做）。"""
        try:
            # ★ 2026-10-14（主人反馈）：启动器一起来就预载语音是**不合适的** ——
            #   主人还没选要开哪只桌宠，它就已经把某个角色的语音服务拉起来、还弹出控制台。
            #   现在默认**不**自动预载；想恢复：config.json 写 "auto_preload_tts": "true"。
            #   手动按钮「预载语音服务」一直都在；启动桌宠时 run.py 也会自动拉起服务。
            from tool.config import get_config as _gc_auto
            _cfg_auto = _gc_auto("./config.json") or {}
            if str(_cfg_auto.get("auto_preload_tts", "false")).strip().lower() not in (
                    "true", "1", "yes", "on", "开"):
                print("[NewUI] 自动预载语音已关闭（config: auto_preload_tts）→ 不预热；"
                      "启动桌宠时才会拉起语音服务（要恢复就把它设为 true）")
                return
            if getattr(self.shell, "_tts_proc", None) is not None:'''
if OLD2 in t:
    t = t.replace(OLD2, NEW2, 1)
    print("✓ ② 已加开关判断（默认 false = 不自动预载）")
else:
    print("✗ ② 锚点未命中")

io.open(P, "w", encoding="utf-8", newline="\n").write(t)

try:
    py_compile.compile(P, doraise=True)
    print("✓ py_compile OK")
except Exception as e:
    print("✗ py_compile:", e)
    sys.exit(1)

print()
print("=== 复核 ===")
for i, l in enumerate(io.open(P, encoding="utf-8", errors="replace").read().split("\n"), 1):
    if "auto_preload_tts" in l or "自动预载" in l:
        print("   %5d| %s" % (i, l.strip()[:110]))
