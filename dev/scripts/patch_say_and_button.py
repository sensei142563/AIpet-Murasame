# -*- coding: utf-8 -*-
"""三处补齐：
  ① tool/chat.py：合成前把"要说的话"打印出来，并追加写进 data/tts_say.log（给语音窗口看）
  ② run.py：外壳配置里加 say_log / port
  ③ pcl_launcher/silicon_window.py：预载语音按钮显示"当前角色"，点了也打印是谁
"""
import io
import os
import py_compile
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"


def patch(rel, pairs, must_all=True):
    p = os.path.join(ROOT, rel)
    t = io.open(p, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
    ok = True
    for old, new, tag in pairs:
        if old in t:
            t = t.replace(old, new, 1)
            print("   ✓ %s：%s" % (rel, tag))
        else:
            print("   ✗ %s：锚点未命中 → %s" % (rel, tag))
            ok = False
    if ok or not must_all:
        io.open(p, "w", encoding="utf-8", newline="\n").write(t)
    try:
        py_compile.compile(p, doraise=True)
        print("   ✓ %s py_compile OK" % rel)
    except Exception as e:
        print("   ✗ %s py_compile: %s" % (rel, e))
        ok = False
    return ok


print("=== ① tool/chat.py：打印要说的话 + 写桥文件 ===")
A1 = """    import time as _t
    t0 = _t.time()
    _gsv_ensure_pet_model()                  # 确保是她的微调权重"""
B1 = """    import time as _t
    t0 = _t.time()
    # ★ 2026-10-14：把"这一句要说的话"打出来，并写进 data/tts_say.log。
    #   后者是给**语音服务那个控制台窗口**看的 —— 它只看得见 HTTP 请求，
    #   看不见 POST 正文里的文字；所以这里用一个解耦的小文件把话"递"过去，
    #   那个窗口会显示成  [00:12:01] 说：「…」。
    try:
        _say_txt = str(text or "").strip()
        if _say_txt:
            print(f"[{now_time()}] [gpt-sovits-tts] 说：{_say_txt}")
            import os as _os_say
            _say_dir = "data"
            _os_say.makedirs(_say_dir, exist_ok=True)
            with open(_os_say.path.join(_say_dir, "tts_say.log"), "a",
                      encoding="utf-8") as _f_say:
                _f_say.write("%.3f\\t%s\\n" % (t0, _say_txt.replace("\\n", " ")[:200]))
    except Exception:
        pass
    _gsv_ensure_pet_model()                  # 确保是她的微调权重"""
patch("tool/chat.py", [(A1, B1, "合成前打印+写 tts_say.log")])

print()
print("=== ② run.py：外壳配置加 say_log / port ===")
A2 = '''                        "log": os.path.abspath(os.path.join("data", "tts_service.log")),'''
B2 = '''                        "log": os.path.abspath(os.path.join("data", "tts_service.log")),
                        "say_log": os.path.abspath(os.path.join("data", "tts_say.log")),
                        "port": "9880",'''
patch("run.py", [(A2, B2, "加 say_log / port")])

print()
print("=== ③ silicon_window.py：按钮显示当前角色 ===")
A3 = '''        self.btn_preload = QPushButton("  预载语音服务")
        self.btn_preload.setStyleSheet(_ghost_btn_qss())
        self.btn_preload.setMinimumHeight(46)
        self.btn_preload.setToolTip(
            "提前启动并预热语音服务（GPT-SoVITS）：\\n"
            "首次加载模型要 1~2 分钟，预热后桌宠开口几乎不用等。\\n"
            "预载完成后按钮显示「预载完成」。")'''
B3 = '''        # ★ 2026-10-14（主人反馈）：这里必须写清"会预载**哪个角色**" ——
        #   原来的按钮只写"预载语音服务"，而它用的是配置里的当前角色，
        #   主人根本没选过，看着像"它自己决定了"。
        _ap_now = self._active_pet_name()
        self.btn_preload = QPushButton(
            "  预载语音服务" + (f"（{_ap_now}）" if _ap_now else "（当前角色）"))
        self.btn_preload.setStyleSheet(_ghost_btn_qss())
        self.btn_preload.setMinimumHeight(46)
        self.btn_preload.setToolTip(
            "提前启动并预热语音服务（GPT-SoVITS）：\\n"
            "首次加载模型要 1~2 分钟，预热后桌宠开口几乎不用等。\\n"
            f"将使用**当前角色**：{_ap_now or '（未选定）'}\\n"
            "预载完成后按钮显示「预载完成」。")'''
patch("pcl_launcher/silicon_window.py", [(A3, B3, "按钮显示角色名 + tooltip")])

print()
print("=== ④ preload_tts 里点下去也打印是谁 ===")
A4 = '''        self.btn_preload.setEnabled(False)
        self.btn_preload.setText("  预载中…")'''
B4 = '''        _ap_click = self._active_pet_name()
        print(f"[NewUI] 预载语音服务 → 当前角色：{_ap_click or '（未选定）'}"
              f"（脚本 {os.path.basename(script)}）")
        self.btn_preload.setEnabled(False)
        self.btn_preload.setText("  预载中…" + (f"（{_ap_click}）" if _ap_click else ""))'''
patch("pcl_launcher/silicon_window.py", [(A4, B4, "点击时打印角色")])

print()
print("=== 复核 ===")
for rel, keys in (("tool/chat.py", ("tts_say.log", "说：")),
                  ("run.py", ("say_log",)),
                  ("pcl_launcher/silicon_window.py", ("_active_pet_name", "预载中…"))):
    print("   --- %s ---" % rel)
    for i, l in enumerate(io.open(os.path.join(ROOT, rel), encoding="utf-8",
                                 errors="replace").read().split("\n"), 1):
        if any(k in l for k in keys):
            print("      %5d| %s" % (i, l.strip()[:104]))
