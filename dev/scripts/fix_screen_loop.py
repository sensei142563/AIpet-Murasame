# -*- coding: utf-8 -*-
"""① 给「看屏幕」下三道闸，治无限自我循环：
     闸1 跳过标记：回退重答时打标，避免同一句再触发看屏幕
     闸2 冷却：短时间内不重复看屏幕
     闸3 熔断：视觉模型权限/名错（403/404 → 返回空）连续失败后**暂停看屏幕**并明确提示主人
   ② 修快捷工具行被挤爆（我上次挪按钮的副作用）：把两个预载按钮换到第二行
"""
import io
import os
import py_compile
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
P = os.path.join(ROOT, "classes", "murasame_class.py")
t = io.open(P, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")

# ============ 闸 1+2：路径A 的守卫加强 ============
OLD_G = """            if role == "user" and not t and not getattr(self, "_screen_look_busy", False):
                from tool.screen_intent import needs_screen_look
                if needs_screen_look(text):
                    self._screen_look_busy = True
                    print("[桌宠] 👀 主人让我看屏幕 → 当场抓屏识别")"""
NEW_G = """            if role == "user" and not t and not getattr(self, "_screen_look_busy", False):
                from tool.screen_intent import needs_screen_look
                # ★★ 2026-10-14 修「看屏幕无限刷屏」：这道闸原来只有 _screen_look_busy，
                #    而那个标记在 finally 里就复位了 —— 于是「看屏幕 → 没拿到内容 →
                #    把主人原话重新送回来」会**再次命中** needs_screen_look，形成自我循环，
                #    日志里就是那条「👀 主人让我看屏幕」永无止境地刷（主人 2026-10-14 实测）。
                #    这里补两道：
                #      闸1 跳过标记：回退重答时打标，这一句不再触发看屏幕；
                #      闸2 冷却：距上次看屏幕太近就不再重复看（画面没变，看了也白看）。
                _now = time.time()
                _skip_once = getattr(self, "_screen_look_skip_once", False)
                _last = float(getattr(self, "_screen_look_last", 0) or 0)
                _cd = float(os.environ.get("AIPET_SCREEN_LOOK_COOLDOWN", "20") or 20)
                _broken_until = float(getattr(self, "_screen_look_broken_until", 0) or 0)
                if _skip_once:
                    self._screen_look_skip_once = False
                    print("[桌宠] ⏭ 这句刚看过屏幕（回退重答），不再重复抓屏")
                elif _now < _broken_until:
                    print("[桌宠] ⏭ 视觉模型当前不可用（已熔断 %d 秒）→ 直接正常回答"
                          % int(_broken_until - _now))
                elif _last and (_now - _last) < _cd:
                    print("[桌宠] ⏭ 距上次看屏幕仅 %.1f 秒（冷却 %d 秒）→ 不重复抓屏"
                          % (_now - _last, int(_cd)))
                elif needs_screen_look(text):
                    self._screen_look_busy = True
                    self._screen_look_last = _now
                    print("[桌宠] 👀 主人让我看屏幕 → 当场抓屏识别")"""
if OLD_G in t:
    t = t.replace(OLD_G, NEW_G, 1)
    print("✓ 闸1+闸2 已加（跳过标记 + 冷却）")
else:
    print("✗ 闸1+2 锚点未命中")

# ============ 闸 3：回退时打标 + 熔断 ============
OLD_F = """            if not str(desc or "").strip():
                print("[桌宠] ⚠ 视觉识别没返回内容 → 退回普通回答")
                self._request_dialog.emit(user_text, "user", False)
                return"""
NEW_F = """            if not str(desc or "").strip():
                # ★ 2026-10-14：视觉模型返回空**几乎都是模型名/权限问题**（实测阿里云返回
                #   403 Access denied 或 404 Model not exist，例如 qwen-vl-plus 未开通）。
                #   这时候"把主人原话再送回去重答"会**再次命中看屏幕** → 无限循环刷屏。
                #   所以：打上"这句跳过看屏幕"的标记，并连续失败到阈值就熔断一会儿，
                #   同时明确告诉主人真正的原因（而不是让她一遍遍地说看不到）。
                self._screen_look_skip_once = True
                _fn = int(getattr(self, "_screen_look_fail_n", 0) or 0) + 1
                self._screen_look_fail_n = _fn
                if _fn >= 3:
                    self._screen_look_broken_until = time.time() + 600
                    self._screen_look_fail_n = 0
                    print("[桌宠] ⛔ 视觉模型连续 %d 次返回空 → 暂停看屏幕 10 分钟。\\n"
                          "        多半是**模型没开通/名字不对**：请到阿里云百炼控制台确认\\n"
                          "        vision_model_name（当前配置见 config.json）已开通，"
                          "或换一个可用的视觉模型名。" % _fn)
                print("[桌宠] ⚠ 视觉识别没返回内容（第 %d 次）→ 退回普通回答（这句不再重复抓屏）"
                      % _fn)
                self._request_dialog.emit(user_text, "user", False)
                return"""
if OLD_F in t:
    t = t.replace(OLD_F, NEW_F, 1)
    print("✓ 闸3 已加（熔断 + 明确报因 + 打跳过标记）")
else:
    print("✗ 闸3 锚点未命中")

# 成功一次就把失败计数清掉
OLD_OK = """            prompt = build_screen_prompt(desc, user_text, getattr(self, "pet_name", "桌宠"))"""
NEW_OK = """            self._screen_look_fail_n = 0          # 成功一次 → 失败计数清零
            self._screen_look_skip_once = True    # 带着描述重答时也别再看一次
            prompt = build_screen_prompt(desc, user_text, getattr(self, "pet_name", "桌宠"))"""
if OLD_OK in t:
    t = t.replace(OLD_OK, NEW_OK, 1)
    print("✓ 成功路径也打跳过标记并清零计数")
io.open(P, "w", encoding="utf-8", newline="\n").write(t)
try:
    py_compile.compile(P, doraise=True)
    print("✓ py_compile OK（murasame_class.py）")
except Exception as e:
    print("✗ py_compile: %s" % e)
    sys.exit(1)

# ============ ② 快捷工具：两个预载按钮换到第二行 ============
P2 = os.path.join(ROOT, "pcl_launcher", "silicon_window.py")
t2 = io.open(P2, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
OLD_T = """        # ★ 2026-10-14：两个「预载」按钮挪到这里 —— 它们本就是"提前把服务热起来"的工具，
        #   放在「快捷工具」里比挤在顶部合理。（主人："首页的两个预加载模型的模块删了，
        #   丑丑的，或者换个地方，放在下面几个板块。"）
        for _pb in (self.btn_preload, self.btn_vpreload):
            tr.addWidget(_pb)
        tr.addStretch()
        tl.addLayout(tr)"""
NEW_T = """        tr.addStretch()
        tl.addLayout(tr)
        # ★ 2026-10-14：两个「预载」按钮放在**第二行** —— 它们本就是"提前把服务热起来"的工具，
        #   放在「快捷工具」里比挤在顶部合理（主人要求挪走）。
        #   ⚠ 但**别和上面 6 个挤在同一行**：一行 8 个按钮 + 角色名后缀会被窗口裁掉，
        #     主人截图里就已经出现「…服务（丛雨△」被切掉的情况（2026-10-14）。
        tr2 = QHBoxLayout()
        for _pb in (self.btn_preload, self.btn_vpreload):
            tr2.addWidget(_pb)
        tr2.addStretch()
        tl.addLayout(tr2)"""
if OLD_T in t2:
    t2 = t2.replace(OLD_T, NEW_T, 1)
    print("✓ ② 两个预载按钮改到第二行（不再挤爆）")
else:
    print("✗ ② 锚点未命中")
# 按钮文案瘦身：角色名移到 tooltip，按钮只留短名
OLD_LBL = 'self.btn_preload = QPushButton('
io.open(P2, "w", encoding="utf-8", newline="\n").write(t2)
try:
    py_compile.compile(P2, doraise=True)
    print("✓ py_compile OK（silicon_window.py）")
except Exception as e:
    print("✗ py_compile: %s" % e)
    sys.exit(1)
