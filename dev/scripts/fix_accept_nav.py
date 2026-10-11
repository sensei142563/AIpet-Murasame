# -*- coding: utf-8 -*-
"""修 accept_all.py 的导航与判据：
  ① 用前台 Activity（mResumedActivity）判断 App 是否真的起来了，替代"dump 里有某段文字"（会假通过）
  ② open_app() 检查 am start 输出并轮询等待前台，最长 ~45s
  ③ 每个阶段开始前 ensure_foreground()，不再依赖"之前按过 BACK 之后还在"
  ④ 返回键检查改为"前台是否仍是本应用"，而不是 pidof（进程活着不代表 Activity 还在）
  ⑤ ⑧2 资产种子：内部目录 adb 读不到（release 包 run-as 不可用）⇒ 改为 UI 判据（主页能看到角色名+抽屉能列出角色）
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
A = os.path.join(MAIN, "dev", "scripts", "accept_all.py")

t = io.open(A, encoding="utf-8").read().replace("\r\n", "\n")

# ---------- ①/② 前台判断 + open_app 重写 ----------
old_app = '''def app_running():
    if DRY:
        return True
    out = adb("shell", "pidof", PKG)
    return bool(out.strip())


def open_app():
    adb("shell", "input", "keyevent", "KEYCODE_WAKEUP")
    adb("shell", "am", "force-stop", PKG)
    time.sleep(2)
    adb("shell", "am", "start", "-n", "%s/.MainActivity" % PKG)
    time.sleep(14)'''
new_app = '''def app_running():
    """进程是否存活（注意：进程活着 ≠ Activity 还在前台）。"""
    if DRY:
        return True
    out = adb("shell", "pidof", PKG)
    return bool(out.strip())


def resumed_activity():
    """当前前台 Activity 的全名（失败返回空串）。这是判断"App 真的起来了吗"的唯一可靠判据。"""
    if DRY:
        return PKG + "/.MainActivity"
    out = adb("shell", "dumpsys", "activity", "activities")
    for line in (out or "").splitlines():
        if "mResumedActivity" in line:
            m = re.search(r"([\\w.]+)/([\\w.$]+)", line)
            if m:
                return m.group(1) + "/" + m.group(2)
    return ""


def foreground_is_app():
    return resumed_activity().startswith(PKG)


def open_app(timeout_s=45):
    """启动并**确认**到了前台。别的应用（如应用市场正在安装）会抢前台，所以必须验证而不是睡够时间。"""
    adb("shell", "input", "keyevent", "KEYCODE_WAKEUP")
    adb("shell", "am", "force-stop", PKG)
    time.sleep(2)
    out = adb("shell", "am", "start", "-n", "%s/.MainActivity" % PKG)
    if out and ("Error" in out or "does not exist" in out):
        print("   ⚠ am start 输出异常：%s" % out.strip()[:140])
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if foreground_is_app():
            time.sleep(3)          # 让首屏与资产种子跑完
            return True
        time.sleep(2)
    # 再拉一次（有些机型第一次启动会被别的应用抢走前台）
    adb("shell", "am", "start", "-n", "%s/.MainActivity" % PKG)
    for _ in range(10):
        time.sleep(2)
        if foreground_is_app():
            time.sleep(3)
            return True
    return False


def ensure_foreground(label=""):
    """进某个阶段前确保 App 在前台（否则后续 dump 全是在别人界面上空打）。"""
    if DRY:
        return True
    if foreground_is_app():
        return True
    print("   … App 不在前台，重新拉起（%s）" % label)
    return open_app()'''
if old_app in t:
    t = t.replace(old_app, new_app, 1)
    print("✓ open_app/前台判断 已重写")
else:
    print("✗ open_app 锚点未命中")
    sys.exit(1)

# ---------- ① 启动检查改用前台 Activity ----------
old_chk = '''    open_app()
    x = dump("a1")
    record("App 启动", verdict(DRY or "chatter" in x or "丛雨" in x),
           ("dump %d 字节" % len(x)) if x else "(dry-run)")'''
new_chk = '''    ok_start = open_app()
    x = dump("a1")
    # 判据必须是"前台是不是本应用"——原来用 dump 里有没有某段文字，结果被应用市场搜索框里的
    # "chatter" 假通过了一次（诊断包里的 a1.xml 就是应用市场的安装页）。
    record("App 启动（前台确认）", verdict(ok_start if not DRY else True),
           "前台=%s · dump %d 字节" % (resumed_activity() or "?", len(x)))'''
if old_chk in t:
    t = t.replace(old_chk, new_chk, 1)
    print("✓ 启动检查已改为前台 Activity")
else:
    print("⚠ 启动检查锚点未命中")

# ---------- ③ 每个阶段前 ensure_foreground（并在关键处去掉多余 BACK）----------
t = t.replace('''    # ① 3D 页（VRM 演示）
    tap_text_any(dump("a2"), ["聊天"])''',
              '''    # ① 3D 页（VRM 演示）
    ensure_foreground("① 3D 页")
    tap_text_any(dump("a2"), ["聊天"])''', 1)
t = t.replace('''    # ② 3D AR（相机 + 透明 VRM + 音量键拍照）
    tap_text_any(dump("a5"), ["聊天"])''',
              '''    # ② 3D AR（相机 + 透明 VRM + 音量键拍照）
    ensure_foreground("② 3D AR")
    tap_text_any(dump("a5"), ["聊天"])''', 1)
t = t.replace('''    # ③ 首页 QQ chatter 卡
    tap_text_any(dump("a11"), ["首页"])''',
              '''    # ③ 首页 QQ chatter 卡
    ensure_foreground("③ 首页 QQ 卡")
    tap_text_any(dump("a11"), ["首页"])''', 1)
t = t.replace('''    # ⑤/⑥ 设置页：离线 TTS 自检 + Silero + 只回应呼唤开关
    open_app()''',
              '''    # ⑤/⑥ 设置页：离线 TTS 自检 + Silero + 只回应呼唤开关
    open_app()   # 这一阶段本来就重新开，保留''', 1)
print("✓ 已插入 ensure_foreground（① ② ③ 前）")

# ---------- ④ 返回键：改用前台 Activity ----------
old_back = '''    # ④ 返回键：第一次不该退出
    adb("shell", "input", "keyevent", "KEYCODE_BACK")
    time.sleep(1.5)
    alive1 = app_running()
    adb("shell", "input", "keyevent", "KEYCODE_BACK")
    time.sleep(3)
    alive2 = app_running()
    record("④ 返回键两次退出", verdict((alive1 and not alive2)),
           "第一次存活=%s 第二次存活=%s" % (alive1, alive2))'''
new_back = '''    # ④ 返回键：第一次不该退出（判据是**前台 Activity**，不是进程存活 ——
    #     进程活着但 Activity 已经退到桌面，用 pidof 会必然误判成"还在"）
    ensure_foreground("④ 返回键")
    adb("shell", "input", "keyevent", "KEYCODE_BACK")
    time.sleep(2)
    fg1 = foreground_is_app()
    adb("shell", "input", "keyevent", "KEYCODE_BACK")
    time.sleep(3)
    fg2 = foreground_is_app()
    record("④ 返回键两次退出", verdict((fg1 and not fg2)),
           "第一次前台=%s 第二次前台=%s（期望 True → False）" % (fg1, fg2))'''
if old_back in t:
    t = t.replace(old_back, new_back, 1)
    print("✓ 返回键检查已改为前台 Activity")
else:
    print("⚠ 返回键锚点未命中")

# ---------- ⑤ ⑧2 资产种子：改为 UI 判据（内部目录 adb 读不到）----------
old_asset = '''    # ⑧-2 资产种子完整性：注册表在、每个角色的 pet.json 非空、且没有残留 .part
    ls = adb("shell", "ls", "-l", EXT + "/pets/")
    ls2 = adb("shell", "ls", EXT + "/pets/*/pet.json")
    parts = adb("shell", "find", EXT + "/pets", "-name", "*.part")
    has_reg = "pet_list.json" in (ls or "")
    has_pet = "pet.json" in (ls2 or "") and "No such file" not in (ls2 or "")
    part_cnt = len([x for x in (parts or "").splitlines() if x.strip() and "No such file" not in x])
    record("⑧2 资产种子完整性", verdict(has_reg and has_pet and part_cnt == 0),
           "注册表=%s pet.json=%s 残留.part=%d" % (has_reg, has_pet, part_cnt))'''
new_asset = '''    # ⑧-2 资产种子完整性：角色包在**内部** filesDir/pets（release 包 run-as 不可用 ⇒ adb 读不到），
    #       所以改用 UI 判据：主页能看到角色（名字/立绘），说明种子铺成功、注册表也读得到。
    ensure_foreground("⑧2 资产种子")
    home = dump("c1")
    names = [n for n in ("丛雨", "诺瓦", "Murasame", "murasame") if n in home]
    tap_text_any(dump("c2"), ["☰"])
    drawer = dump("c3")
    has_pet_entry = any(n in drawer for n in ("丛雨", "诺瓦", "murasame", "Murasame"))
    record("⑧2 资产种子（UI 判据）", verdict(bool(names)),
           "主页可见角色=%s；抽屉含角色=%s（内部 pets/ 目录 adb 读不到，故以 UI 为准）"
           % (names or "无", has_pet_entry))
    # 补充：残留 .part 检查仍在**外部**目录做（能读到的部分）
    parts = adb("shell", "find", EXT, "-name", "*.part")
    part_cnt = len([x for x in (parts or "").splitlines() if x.strip() and "No such file" not in x])
    record("⑧2b 无残留 .part（外部目录）", verdict(part_cnt == 0), "残留=%d" % part_cnt)'''
if old_asset in t:
    t = t.replace(old_asset, new_asset, 1)
    print("✓ ⑧2 已改为 UI 判据（+ 新增 ⑧2b 残留检查）")
else:
    print("⚠ ⑧2 锚点未命中")

# ---------- ⑧3 Silero：没有 vad.log 时给出更明确的原因（需要先触发一次识别）----------
t = t.replace('''    record("⑧3 Silero 真机阈值", verdict(bool(rdy)),
           (rdy[-1].strip()[:150] if rdy else "(vad.log 里没有『Silero VAD ready』—— 说明 Silero 没初始化成功)"))''',
              '''    record("⑧3 Silero 真机阈值", verdict(bool(rdy)),
           (rdy[-1].strip()[:150] if rdy else
            "(vad.log 里没有『Silero VAD ready』—— Silero 只在**首次识别**时初始化，"
            "请先在聊天页长按说话一次，再重跑本项)"))''', 1)

# ---------- ⑧4 onGiveUp：日志为旧文件时不能算通过 ----------
t = t.replace('''    record("⑧4 onGiveUp 已接线", verdict(not warn and bool((voicelog or "").strip())),
           ("出现过 %d 次回退事件；未提供回调告警 %d 次" % (len(fell), len(warn)))
           + ("" if not warn else " ⚠ 有告警说明调用点没接上"))''',
              '''    fresh = bool((voicelog or "").strip())
    if not fresh:
        record("⑧4 onGiveUp 已接线", "SKIP", "还没有本次安装后的 voice.log（需先让她出声一次）")
    else:
        record("⑧4 onGiveUp 已接线", verdict(not warn),
               ("回退事件 %d 次；未提供回调告警 %d 次" % (len(fell), len(warn)))
               + ("" if not warn else " ⚠ 有告警说明调用点没接上"))''', 1)

io.open(A, "w", encoding="utf-8", newline="\n").write(t)

print()
print("=== 语法检查 ===")
r = subprocess.run([sys.executable, "-c",
                    "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % A],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print("   " + ("OK" if r.returncode == 0 else "FAIL\n" + (r.stderr or "")[:500]))
if r.returncode != 0:
    sys.exit(1)

print()
print("=== dry-run 自检（不应谎报 PASS）===")
r2 = subprocess.run([sys.executable, "-u", A, "--dry-run"], capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=900,
                    env=dict(os.environ, PYTHONIOENCODING="utf-8"))
out = (r2.stdout or "") + (r2.stderr or "")
j = out.find("=== 汇总 ===")
print(out[j:] if j > 0 else out[-800:])
print("   退出码:", r2.returncode)
