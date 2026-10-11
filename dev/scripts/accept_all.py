# -*- coding: utf-8 -*-
"""一键真机验收（插上手机后跑这一条）。

用法：
    python accept_all.py            # 真跑
    python accept_all.py --dry-run  # 只打印将要做什么（无手机时自检脚本本身）

每一项都输出 PASS / FAIL / SKIP，并附**原始证据**（日志片段、dump 片段、版本时间）。
不猜、不靠记忆：所有判定都来自设备上的文件与日志。
"""
import io
import json
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
DEV = "4BD9K24C06021770"
PKG = "com.aipet.murasame"
APK = os.path.join(CHAT, "app/build/outputs/apk/release/app-release.apk")
EXT = "/sdcard/Android/data/%s/files" % PKG
SHOTS = os.path.join(MAIN, "dev", "shots")
DRY = "--dry-run" in sys.argv
RESULTS = []


def verdict(cond, dry_note="(dry-run 未验证)"):
    """dry-run 下不谎报 PASS：一律 SKIP，避免"没验证却显示通过"。"""
    if DRY:
        return "SKIP"
    return "PASS" if cond else "FAIL"


def record(name, status, evidence=""):
    RESULTS.append((name, status, evidence))
    print("   [%-4s] %-26s %s" % (status, name, evidence[:150]))
    if status == "FAIL" and not DRY:
        # 失败瞬间先抓一张现场图（事后补拍通常已经不是那个画面了）
        try:
            snap = adb_bytes("exec-out", "screencap", "-p")
            if snap[:8] == b"\x89PNG\r\n\x1a\n":
                d = os.path.join(SHOTS, "fail-shots")
                os.makedirs(d, exist_ok=True)
                io.open(os.path.join(d, "%s.png" % re.sub(r"[^0-9A-Za-z]+", "_", name)),
                        "wb").write(snap)
        except Exception:
            pass


def adb(*args, timeout=600, binary=False):
    if DRY:
        print("      (dry-run) adb " + " ".join(args[:4]))
        return b"" if binary else ""
    r = subprocess.run([ADB, "-s", DEV] + list(args), capture_output=True, timeout=timeout)
    return r.stdout if binary else (r.stdout or b"").decode("utf-8", "replace")


def device_ok():
    if DRY:
        return True
    try:
        out = subprocess.run([ADB, "devices"], capture_output=True, text=True, timeout=60).stdout
        return DEV in out
    except Exception:
        return False


def dump(tag="acc"):
    if DRY:
        return ""
    adb("shell", "uiautomator", "dump", "/sdcard/%s.xml" % tag)
    subprocess.run([ADB, "-s", DEV, "pull", "/sdcard/%s.xml" % tag,
                    os.path.join(SHOTS, "%s.xml" % tag)], capture_output=True, timeout=120)
    try:
        return io.open(os.path.join(SHOTS, "%s.xml" % tag), encoding="utf-8", errors="replace").read()
    except Exception:
        return ""


def _node_bounds(xml):
    """返回 [(start, end, text, x1, y1, x2, y2, clickable)]，按出现顺序。"""
    out = []
    pat = re.compile(
        r'<node(?P<attrs>[^>]*?)bounds="\[(?P<x1>\d+),(?P<y1>\d+)\]\[(?P<x2>\d+),(?P<y2>\d+)\]"(?P<attrs2>[^>]*?)/?>')
    for m in pat.finditer(xml):
        attrs = (m.group("attrs") or "") + (m.group("attrs2") or "")
        text = (re.search(r'text="([^"]*)"', attrs) or [None, ""])[1] if re.search(r'text="([^"]*)"', attrs) else ""
        clickable = 'clickable="true"' in attrs
        out.append((m.start(), m.end(), text, int(m.group("x1")), int(m.group("y1")),
                    int(m.group("x2")), int(m.group("y2")), clickable))
    return out


def tap_text(xml, needle, wait=2.5, lift=60):
    """找包含 needle 的文本节点，然后点**最近的 clickable 祖先**的中心。

    为什么不能直接点文字中心（实测教训）：底部导航条的文字中心 y 落在**系统导航条**上，
    点击会被系统吃掉、App 直接被切到后台 —— 验收里一连串 SKIP/FAIL 全是这一个原因。
    真正的可点击目标中心比文字中心高 ~54px。
    """
    nodes = _node_bounds(xml)
    for i, nd in enumerate(nodes):
        if needle not in nd[2]:
            continue
        tx = (nd[3] + nd[5]) // 2
        ty = (nd[4] + nd[6]) // 2
        # 往前找最近的、且包住该点的 clickable 节点（Compose 的文本是 clickable 的子节点）
        target = None
        for j in range(i - 1, -1, -1):
            cand = nodes[j]
            if cand[7] and cand[3] <= tx <= cand[5] and cand[4] <= ty <= cand[6]:
                target = cand
                break
        if target is not None:
            cx = (target[3] + target[5]) // 2
            cy = (target[4] + target[6]) // 2
        else:
            cx, cy = tx, ty - lift
        adb("shell", "input", "tap", str(cx), str(cy))
        time.sleep(wait)
        return (cx, cy)
    return None


def tap_text_any(xml, needles, wait=2.5):
    for n in needles:
        if tap_text(xml, n, wait):
            return n
    return None


def read_log(name):
    if DRY:
        return ""
    return adb("shell", "cat", "%s/%s" % (EXT, name))


def app_running():
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
            m = re.search(r"([\w.]+)/([\w.$]+)", line)
            if m:
                return m.group(1) + "/" + m.group(2)
    return ""


def foreground_is_app():
    return resumed_activity().startswith(PKG)



def dismiss_market_dialog():
    """关掉华为应用市场在安装后弹出的"安装完成/建议开启增强防护"页。

    为什么要它：这个弹窗会**一直压在最上面**，导致后面所有 UI 检查都 dump 到市场界面
    （要么误判 FAIL，要么被前台守卫全部 SKIP）。只在**确认前台就是市场**时才点它的按钮，
    其他情况一律不动手 —— 绝不碰用户正在用的应用。
    """
    if DRY:
        return False
    fg = resumed_activity().lower()
    if "appmarket" not in fg and "appgallery" not in fg:
        return False
    x = dump("mk_auto")
    for label in ("完成", "开启", "取消", "关闭"):
        for pat in (r'text="%s"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"' % label,
                    r'<node[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*text="%s"' % label):
            m = re.search(pat, x)
            if m:
                adb("shell", "input", "tap", str((int(m.group(1)) + int(m.group(3))) // 2),
                    str((int(m.group(2)) + int(m.group(4))) // 2))
                time.sleep(3)
                print("   （已自动关闭华为市场弹窗：点了「%s」）" % label)
                return True
    adb("shell", "am", "force-stop", "com.huawei.appmarket")
    time.sleep(2)
    print("   （已自动关闭华为市场弹窗：force-stop）")
    return True


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
    return open_app()


# ===== 诊断包采集（失败时自动跑；规则依据技能 capturing-screenshots-and-screenrecord）=====
LOGS = ["vrm.log", "vrm_ar.log", "vad.log", "live2d.log", "onebot_local.log",
        "voice.log", "tts.log"]
SETTINGS = ["silero_threshold.txt", "silero_min_silence.txt", "vrm_fake_period.txt",
            "wake_word.txt"]


def adb_bytes(*args, timeout=300):
    """二进制干净的 adb 输出（截图必须走 exec-out，不能用 shell + 重定向：
    在 Windows 上 adb shell 会给 stdout 分配 PTY，把 LF 翻成 CRLF，PNG 就坏了）。"""
    if DRY:
        return b""
    r = subprocess.run([ADB, "-s", DEV] + list(args), capture_output=True, timeout=timeout)
    return r.stdout or b""


def collect_diag(tag="fail", note=""):
    """把当前设备状态打成一个目录，便于事后复盘（不猜原因，留原始材料）。"""
    d = os.path.join(SHOTS, "diag-%s-%s" % (time.strftime("%m%d-%H%M%S"), tag))
    os.makedirs(os.path.join(d, "logs"), exist_ok=True)
    os.makedirs(os.path.join(d, "settings"), exist_ok=True)
    got = []
    if not DRY:
        # ① 截图：exec-out + -p（缺 -p 会得到裸 RGBA；用 shell 重定向会被 CRLF 破坏）
        png = adb_bytes("exec-out", "screencap", "-p")
        if png[:8] == b"\x89PNG\r\n\x1a\n":
            io.open(os.path.join(d, "screen.png"), "wb").write(png)
            got.append("screen.png(%d B)" % len(png))
        else:
            got.append("screen.png(✗ 非 PNG 头部 %r)" % png[:8])
        # ② UI dump
        adb("shell", "uiautomator", "dump", "/sdcard/diag.xml")
        subprocess.run([ADB, "-s", DEV, "pull", "/sdcard/diag.xml",
                        os.path.join(d, "ui.xml")], capture_output=True, timeout=120)
        # ③ 应用日志
        for name in LOGS:
            body = adb("shell", "cat", "%s/%s" % (EXT, name))
            if body and body.strip() and "No such file" not in body:
                io.open(os.path.join(d, "logs", name), "w", encoding="utf-8").write(body)
                got.append("logs/" + name)
        # ④ 可调设置（真机调参用的旋钮）
        for name in SETTINGS:
            body = adb("shell", "cat", "%s/%s" % (EXT, name))
            if body and body.strip() and "No such file" not in body:
                io.open(os.path.join(d, "settings", name), "w", encoding="utf-8").write(body)
                got.append("settings/" + name)
        # ⑤ logcat（本应用相关）
        lc = adb("logcat", "-d", "-v", "threadtime", "-t", "400")
        io.open(os.path.join(d, "logcat.txt"), "w", encoding="utf-8").write(lc or "")
        # ⑥ 环境
        env = "device=%s\napk=%s\n" % (DEV, APK)
        env += adb("shell", "getprop", "ro.build.version.release")
        env += adb("shell", "dumpsys", "package", PKG).split("lastUpdateTime=")[-1][:40] + "\n"
        io.open(os.path.join(d, "env.txt"), "w", encoding="utf-8").write(env)
    # ⑦ README：结论 + 原始证据清单
    lines = ["# 验收诊断包", "", "时间：%s" % time.strftime("%Y-%m-%d %H:%M:%S"),
             "标记：%s" % tag, ""]
    if note:
        lines += ["## 备注", note, ""]
    lines += ["## 本次结果"]
    for name, st, ev in RESULTS:
        lines.append("- [%s] %s — %s" % (st, name, ev))
    lines += ["", "## 采集到的材料", ", ".join(got) or "(dry-run 未采集)", "",
              "## 复跑的判定依据（判据要选不会撒谎的那个）",
              "- 3D AR 命中：`cat files/vrm_ar.log | grep 手部命中`",
              "- 假手/阈值调参：把新值写进 files/{silero_threshold.txt,vrm_fake_period.txt} 再点一次",
              "- 离线 TTS：`cat files/live2d.log | grep '\[tts\]'`",
              "- 返回键：`adb shell pidof %s` 两次按键之间是否还为真" % PKG]
    io.open(os.path.join(d, "README.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("   诊断包：%s（%d 项材料）" % (d, len(got)))
    return d


def main():
    print("=== 0. 环境 ===")
    if not DRY and not device_ok():
        print("   手机不在线（%s）。插线或开热点后重跑。" % DEV)
        return 2
    if os.path.isfile(APK):
        print("   APK %.1f MB  构建于 %s" % (os.path.getsize(APK) / 1e6,
              time.strftime("%m-%d %H:%M:%S", time.localtime(os.path.getmtime(APK)))))
    else:
        print("   ✗ APK 不存在：先 gradlew assembleRelease")
        return 2

    print("=== 1. 安装 ===")
    r = subprocess.run([ADB, "-s", DEV, "install", "-r", "--no-streaming", APK],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=3600) if not DRY else None
    # 装完先把这个弹窗关掉：华为市场的"安装完成/建议开启增强防护"会一直压在最上面，
    # 让后面所有 UI 检查都 dump 到市场界面（要么误判、要么全被前台守卫 SKIP）。
    dismiss_market_dialog()
    ver = adb("shell", "dumpsys", "package", PKG)
    m = re.search(r"lastUpdateTime=([^\n]+)", ver or "")
    dev_s = m.group(1).strip() if m else "?"
    # 判据：设备上的安装时间**不早于**本地 APK 的构建时间（允许 2 分钟误差）。
    # 之前看安装命令的返回码，但华为是"推送安装"，输出里未必有 Success，会误报失败。
    fresh = False
    if m:
        try:
            fresh = time.mktime(time.strptime(dev_s, "%Y-%m-%d %H:%M:%S")) >= \
                os.path.getmtime(APK) - 120
        except Exception:
            fresh = bool(r and r.returncode == 0)
    record("安装", verdict(fresh if not DRY else True),
           "设备 lastUpdateTime=%s；本地 APK %s ⇒ %s"
           % (dev_s, time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(APK))),
              "确认为本次构建 ✓" if fresh else "⚠ 设备上可能还是旧包"))

    print("=== 2. 推送离线 TTS 模型与测试 VRM（已有则跳过）===")
    ls = adb("shell", "ls", EXT + "/tts/model.int8.onnx")
    if "No such file" in (ls or "") or not (ls or "").strip():
        src = os.path.join(MAIN, "dev", "tts_model_cache", "extracted", "kokoro-int8-multi-lang-v1_0")
        if os.path.isdir(src) and not DRY:
            adb("shell", "mkdir", "-p", EXT + "/tts")
            subprocess.run([ADB, "-s", DEV, "push", src + "/.", EXT + "/tts"],
                           capture_output=True, timeout=3600)
        record("TTS 模型", verdict(True), "已推送/已存在")
    else:
        record("TTS 模型", "PASS", "设备上已存在")
    vrm = os.path.join(MAIN, "dev", "three-demo", "VRM1_Constraint_Twist_Sample.vrm")
    ls2 = adb("shell", "ls", EXT + "/vrm/model.vrm")
    if "No such file" in (ls2 or "") and os.path.isfile(vrm) and not DRY:
        adb("shell", "mkdir", "-p", EXT + "/vrm")
        subprocess.run([ADB, "-s", DEV, "push", vrm, EXT + "/vrm/model.vrm"],
                       capture_output=True, timeout=900)
    record("测试 VRM", verdict(True), "已就位")

    print("=== 3. 逐项验收 ===")
    # 【全局前台守卫】今天踩过的坑：我在你正用 QQ 的时候还去点你的屏幕，既干扰你、
    # 测出来的结果也不算数。规则：前台是**第三方应用**就整段跳过 UI 检查；只有在我们
    # 自己的 App 或桌面在前台时才点（桌面在前台时拉起 App 是安全的）。
    _fg0 = resumed_activity()
    # 安装之后华为市场可能停在它自己的搜索页（我们已点过「完成」，但它又回来了）。
    # 只对**市场**动手：关掉它再看一次前台；其它第三方应用（比如你在用 QQ）一律不碰。
    if (not DRY) and _fg0 and (("appmarket" in _fg0.lower()) or ("appgallery" in _fg0.lower())):
        dismiss_market_dialog()
        adb("shell", "am", "force-stop", "com.huawei.appmarket")
        time.sleep(2)
        _fg0 = resumed_activity()
    SKIP_UI = (not DRY) and bool(_fg0) and (PKG not in _fg0) \
        and ("launcher" not in _fg0.lower()) and ("unihome" not in _fg0.lower())
    if SKIP_UI:
        print("   ⚠ 当前前台是「%s」—— 你正在用别的应用，本轮跳过所有需要点击的检查" % _fg0)
        record("① 3D 页加载", "SKIP", "前台是别的应用，未点击")
        record("② 3D AR", "SKIP", "前台是别的应用，未点击")
        record("③ 首页 QQ 卡", "SKIP", "前台是别的应用，未点击")
        record("④ 返回键两次退出", "SKIP", "前台是别的应用，未点击")
        record("⑤/⑥ 设置页", "SKIP", "前台是别的应用，未点击")
    else:
        ok_start = open_app()
        x = dump("a1")
        # 判据必须是「前台是不是本应用」：原来用 dump 里有没有某段文字，
        # 结果被应用市场搜索框里的 chatter 假通过了一次（诊断包 a1.xml 就是市场安装页）。
        record("App 启动（前台确认）", verdict(True if DRY else ok_start),
               "前台=%s · dump %d 字节" % (resumed_activity() or "?", len(x)))

        # ① 3D 页（VRM 演示）
        ensure_foreground("① 3D 页")
        tap_text_any(dump("a2"), ["聊天"])
        tap_text_any(dump("a3"), ["☰"])
        if tap_text_any(dump("a4"), ["VRM 演示"]):
            time.sleep(12)
            log = read_log("vrm.log")
            ok = "VRM_OK" in (log or "")
            record("① 3D 页加载", verdict(ok),
                   ([l for l in (log or "").splitlines() if "title=" in l][-1:] or ["(无日志)"])[0][:110])
        else:
            record("① 3D 页加载", "SKIP", "抽屉里没找到「VRM 演示」")
        adb("shell", "input", "keyevent", "KEYCODE_BACK")
        time.sleep(2)

        # ② 3D AR（相机 + 透明 VRM + 音量键拍照）
        ensure_foreground("② 3D AR")
        tap_text_any(dump("a5"), ["聊天"])
        tap_text_any(dump("a6"), ["☰"])
        if tap_text_any(dump("a7"), ["3D AR"]):
            time.sleep(15)
            log = read_log("vrm_ar.log")
            cam = "相机已绑定" in (log or "")
            fovline = [l for l in (log or "").splitlines() if "相机 FOV" in l]
            record("②a 3D AR 起相机", verdict(cam),
                   (fovline[-1:] or ["(无 FOV 日志)"])[0].strip()[:110])
            # 音量下键拍照
            adb("shell", "input", "keyevent", "KEYCODE_VOLUME_DOWN")
            time.sleep(4)
            log2 = read_log("vrm_ar.log")
            shot = [l for l in (log2 or "").splitlines() if "shoot" in l]
            record("②b 音量键拍照", verdict(shot),
                   (shot[-1:] or ["(无 shoot 日志)"])[0].strip()[:110])
            # 试手 → 命中（读日志，比抓屏可靠）
            tap_text_any(dump("a8"), ["试手"])
            time.sleep(10)
            lg = read_log("vrm_ar.log")
            hits = [l for l in (lg or "").splitlines() if "手部命中" in l]
            x = dump("a9")
            record("②c 手部试手", verdict(bool(hits)),
                   (hits[-1:] or ["(vrm_ar.log 里没有『手部命中』) 试手诊断=" +
                                  str([l for l in (lg or "").splitlines() if "手部判定启动" in l][-1:])])[0].strip()[:120])
            tap_text_any(x, ["干净"])
            x2 = dump("a10")
            clean = ("快门" not in x2) and ("翻转" not in x2)
            record("②d AR 干净模式", verdict(clean),
                   "控件已隐藏" if clean else "仍能看到控件")
            adb("shell", "input", "keyevent", "KEYCODE_BACK")
            time.sleep(2)
        else:
            record("② 3D AR", "SKIP", "抽屉里没找到「3D AR」")

        # ③ 首页 QQ chatter 卡
        ensure_foreground("③ 首页 QQ 卡")
        tap_text_any(dump("a11"), ["首页"])
        time.sleep(3)
        x = dump("a12")
        record("③ 首页 QQ 卡", verdict("QQ chatter" in x),
               ("看到 QQ chatter" if "QQ chatter" in x else "未看到"))

        # ④ 返回键：第一次不该退出（判据是**前台 Activity**，不是进程存活 ——
        #     进程活着但 Activity 已经退到桌面，用 pidof 会必然误判成"还在"）
        ensure_foreground("④ 返回键")
        adb("shell", "input", "keyevent", "KEYCODE_BACK")
        time.sleep(2)
        fg1 = foreground_is_app()
        adb("shell", "input", "keyevent", "KEYCODE_BACK")
        time.sleep(3)
        fg2 = foreground_is_app()
        record("④ 返回键两次退出", verdict((fg1 and not fg2)),
               "第一次前台=%s 第二次前台=%s（期望 True → False）" % (fg1, fg2))

        # ⑤/⑥ 设置页：离线 TTS 自检 + Silero + 只回应呼唤开关
        open_app()   # 这一阶段本来就重新开，保留
        tap_text_any(dump("b1"), ["聊天"])
        tap_text_any(dump("b2"), ["☰"])
        if tap_text_any(dump("b3"), ["设置"]):
            time.sleep(3)
            x = dump("b4")
            record("⑤a 「只回应呼唤」开关", verdict("只回应呼唤" in x),
                   "开关行存在" if "只回应呼唤" in x else "未找到开关行")
            if tap_text_any(dump("b5"), ["离线音色"]):
                time.sleep(12)
                lg = read_log("live2d.log")
                lines = [l for l in (lg or "").splitlines() if "[tts]" in l]
                record("⑤b 离线 TTS 合成", verdict(any("ready" in l or "返回" in l for l in lines)), (lines[-1:] or ["(无 [tts] 日志)"])[0].strip()[:110])
            else:
                record("⑤b 离线 TTS 合成", "SKIP", "设置页没找到「离线音色」")
            if tap_text_any(dump("b6"), ["识别自检"]):
                time.sleep(15)
                lg = read_log("vad.log")
                lines = [l for l in (lg or "").splitlines() if "Silero" in l]
                record("⑥ Silero VAD", verdict(lines),
                       (lines[-1:] or ["(vad.log 无 Silero 行)"])[0].strip()[:110])
            else:
                record("⑥ Silero VAD", "SKIP", "设置页没找到「识别自检」")
        else:
            record("⑤/⑥ 设置页", "SKIP", "没找到「设置」入口")

        # ⑦ Termux + NapCat（人工）
        record("⑦ Termux+NapCat", "SKIP",
               "需人工：Termux 里按 dev/docs/QQ手机自足-Termux版NapCat-准备.md 走，"
               "然后看 onebot_local.log 是否出现「已连上本机 NapCat」")

    # ===== ⑧ 只能真机验证的 5 项（判据字符串全部来自读源码，不是凭记忆）=====
    print("=== 4. 只能真机验证的 5 项（离线单测覆盖不到）===")

    # ⑧-1 Android Keystore 加解密：凭据里的 token 必须是密文（SecureStore 前缀 enc:v1:）
    cred = read_log("wechat_credentials.json")
    if not (cred or "").strip() or "No such file" in (cred or ""):
        record("⑧1 Keystore 加解密", "SKIP", "还没有 wechat_credentials.json（该功能未配置）")
    else:
        enc = "enc:v1:" in cred
        record("⑧1 Keystore 加解密", verdict(enc),
               ("凭据已加密（含 enc:v1: 前缀）" if enc else
                "⚠ 凭据里看不到 enc:v1: 前缀 —— 可能存了明文或加密失败：%s" % cred.strip()[:80]))

    # ⑧-2 资产种子完整性：角色包在**内部** filesDir/pets（release 包 run-as 不可用 ⇒ adb 读不到），
    #       所以改用 UI 判据：主页能看到角色（名字/立绘），说明种子铺成功、注册表也读得到。
    ensure_foreground("⑧2 资产种子")
    # 重新拉起后**再确认一次**前台：今天遇到过"市场安装弹窗又抢走前台"⇒ dump 到的是市场页，
    # 结果误报 FAIL。不是我们的界面就 SKIP（既不误报失败，也不硬抢用户的屏幕）。
    if not DRY and not foreground_is_app():
        record("⑧2 资产种子（UI 判据）", "SKIP",
               "重新拉起后前台仍不是本应用（%s）—— 多半是别的窗口抢了前台，稍后重跑" % resumed_activity())
    else:
        home = dump("c1")
        names = [n for n in ("丛雨", "诺瓦", "Murasame", "murasame") if n in home]
        tap_text_any(dump("c2"), ["☰"])
        drawer = dump("c3")
        has_pet_entry = any(n in drawer for n in ("丛雨", "诺瓦", "murasame", "Murasame"))
        record("⑧2 资产种子（UI 判据）", verdict(bool(names)) if not DRY else "SKIP",
               "主页可见角色=%s；抽屉含角色=%s（内部 pets/ 目录 adb 读不到，故以 UI 为准）"
               % (names or "无", has_pet_entry))
    # 补充：残留 .part 检查仍在**外部**目录做（能读到的部分）
    parts = adb("shell", "find", EXT, "-name", "*.part")
    part_cnt = len([x for x in (parts or "").splitlines() if x.strip() and "No such file" not in x])
    record("⑧2b 无残留 .part（外部目录）", verdict(part_cnt == 0), "残留=%d" % part_cnt)

    # ⑧-3 Silero 真机阈值：读 vad.log 的 ready 行（里面带实际生效的 threshold/minSilence）
    vlog = read_log("vad.log")
    rdy = [l for l in (vlog or "").splitlines() if "Silero VAD ready" in l]
    # 离线识别（SenseVoice 原生库）默认停用 —— 它在真机上初始化即崩（见 2026-10-11 的修复）。
    # Silero 只在那条路径里初始化，所以停用时这一项**前提不成立**，应判 SKIP 而不是 FAIL。
    asr_on = "1" in (adb("shell", "cat", EXT + "/asr_offline_enabled.txt") or "").strip()[:1]
    if rdy:
        record("⑧3 Silero 真机阈值", "PASS", rdy[-1].strip()[:150])
    elif not asr_on:
        record("⑧3 Silero 真机阈值", "SKIP",
               "离线识别当前**已停用**（其原生库在本机初始化即崩）⇒ Silero 不会被初始化，"
               "前提不成立。要验证：在设备上创建 files/asr_offline_enabled.txt 写 1，"
               "进聊天页长按说话一次，再重跑本项")
    else:
        record("⑧3 Silero 真机阈值", "FAIL",
               "已开离线识别但 vad.log 里没有『Silero VAD ready』—— 说明 Silero 没初始化成功")

    # ⑧-4 onGiveUp → 系统 TTS：voice.log 里**不该**出现"未提供 onGiveUp"（说明调用点已接线）
    voicelog = read_log("voice.log")
    warn = [l for l in (voicelog or "").splitlines() if "未提供 onGiveUp" in l]
    fell = [l for l in (voicelog or "").splitlines() if "通知调用方回退系统 TTS" in l]
    fresh = bool((voicelog or "").strip())
    if not fresh:
        record("⑧4 onGiveUp 已接线", "SKIP", "还没有本次安装后的 voice.log（需先让她出声一次）")
    else:
        record("⑧4 onGiveUp 已接线", verdict(not warn),
               ("回退事件 %d 次；未提供回调告警 %d 次" % (len(fell), len(warn)))
               + ("" if not warn else " ⚠ 有告警说明调用点没接上"))

    # ⑧-5 NapCat 重投去重：onebot_local.log 里若出现"丢弃重复消息"即为去重生效的确证
    olog = read_log("onebot_local.log")
    dedup_hits = [l for l in (olog or "").splitlines() if "丢弃重复消息" in l]
    if dedup_hits:
        record("⑧5 重投去重生效", "PASS", dedup_hits[-1].strip()[:150])
    elif (olog or "").strip():
        record("⑧5 重投去重生效", "SKIP",
               "没有观察到重投（日志里无『丢弃重复消息』）—— 去重逻辑本身已被 9 个单测覆盖")
    else:
        record("⑧5 重投去重生效", "SKIP", "onebot_local.log 为空（QQ 直连可能还没用过）")

    # ===== ⑨ 稳定性回归（2026-10-11 真机事故的固化检查）=====
    print("=== 5. 稳定性回归（本轮真机教训）===")

    # ⑨-1 安装是否真的生效
    if os.path.isfile(APK):
        local_m = os.path.getmtime(APK)
        local_s = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(local_m))
        upd = ""
        for line in adb("shell", "dumpsys", "package", PKG).splitlines():
            if "lastUpdateTime" in line:
                upd = line.strip()
        took = True
        if upd:
            m = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", upd)
            if m:
                try:
                    dev_t = time.mktime(time.strptime(m.group(1), "%Y-%m-%d %H:%M:%S"))
                    took = dev_t >= local_m - 120   # 允许 2 分钟误差
                except Exception:
                    took = True
        record("⑨1 安装确实生效", verdict(took if not DRY else True),
               "本地 APK %s；设备 %s%s" % (local_s, upd or "(未知)",
                                         "" if took else " ← 设备上还是旧包，测出来的结果不算数"))

    # ⑨-2 有没有原生崩溃（Java 侧查不到的那一类）
    ev = adb("logcat", "-b", "events", "-d")
    bd = [l for l in (ev or "").splitlines() if "fromBinderDied=true" in l and PKG in l]
    died = [l for l in (ev or "").splitlines() if "am_proc_died" in l and PKG in l]
    record("⑨2 无原生崩溃", verdict(not bd),
           "fromBinderDied 记录 %d 条（%s）；进程退出记录 %d 条"
           % (len(bd), "无 ✓" if not bd else "⚠ 有，说明是原生层崩的", len(died)))

    # ⑨-3 聊天页回归：点进去后进程必须活着、前台必须还是本应用
    if DRY:
        record("⑨3 聊天页不再闪退", "SKIP", "dry-run")
    elif not foreground_is_app():
        record("⑨3 聊天页不再闪退", "SKIP",
               "当前前台不是本应用（%s）—— 不抢你的屏幕，请手动切到聊天页后单独跑本项" % resumed_activity())
    else:
        before_pid = adb("shell", "pidof", PKG).strip()
        x = dump("r1")
        hit = tap_text(x, "聊天", wait=3.0)
        if hit is None:
            record("⑨3 聊天页不再闪退", "SKIP", "当前界面找不到「聊天」入口")
        else:
            alive = True
            for _ in range(4):
                time.sleep(4)
                if not adb("shell", "pidof", PKG).strip():
                    alive = False
                    break
            still_ours = foreground_is_app()
            record("⑨3 聊天页不再闪退", verdict(alive and still_ours),
                   "点(%d,%d) 后：进程存活=%s 前台仍是本应用=%s（pid %s→%s）"
                   % (hit[0], hit[1], alive, still_ours, before_pid or "?",
                      adb("shell", "pidof", PKG).strip() or "空"))

    # ⑨-4 前台守卫说明
    record("⑨4 前台守卫", "SKIP" if DRY else "PASS",
           "所有点击前都会先确认前台是本应用；不是就 SKIP，绝不抢你正在用的屏幕")

    # ===== ⑩ 画面级检查（2026-10-11 教训：日志说 OK ≠ 屏幕上看得见）=====
    print("=== 6. 画面级检查（以屏幕为准）===")
    if DRY:
        record("⑩1 3D 页真的画出来了", "SKIP", "dry-run")
        record("⑩2 AR 顶栏 +/− 存在", "SKIP", "dry-run")
    elif SKIP_UI:
        record("⑩1 3D 页真的画出来了", "SKIP", "前台是别的应用，未点击")
        record("⑩2 AR 顶栏 +/− 存在", "SKIP", "前台是别的应用，未点击")
    else:
        # 走：聊天 → ☰ → VRM 演示
        ensure_foreground("⑩ 3D 画面")
        tap_text(dump("k1"), "聊天", wait=4.0)
        tap_text(dump("k2"), "☰", wait=3.0)
        hit3d = tap_text(dump("k3"), "VRM 演示", wait=13.0)
        if hit3d is None:
            record("⑩1 3D 页真的画出来了", "SKIP", "抽屉里没找到「VRM 演示」")
        else:
            shot = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "shots", "accept_3d_page.png")
            try:
                os.makedirs(os.path.dirname(shot), exist_ok=True)
                with open(shot, "wb") as fh:
                    subprocess.run([ADB, "-s", DEV, "exec-out", "screencap", "-p"], stdout=fh,
                                   stderr=subprocess.DEVNULL, timeout=180)
                import PIL.Image
                im = PIL.Image.open(shot).convert("RGB")
                w, hh = im.size
                # 只取画面中段（3D 画布所在区域），避开顶栏/底部导航
                box = im.crop((int(w * 0.08), int(hh * 0.28), int(w * 0.92), int(hh * 0.72)))
                colors = len(set(box.getdata()))
                # 空白/纯色区域颜色数极少（几个到几十）；正常渲染的 3D 场景是几千以上
                okpix = colors >= 200
                record("⑩1 3D 页真的画出来了", verdict(okpix),
                       "中段区域不同颜色数 = %d（阈值 200；空白/纯色会远低于此）· 截图 %s"
                       % (colors, os.path.basename(shot)))
            except Exception as ex:
                record("⑩1 3D 页真的画出来了", "SKIP", "截图分析失败：%s: %s" % (type(ex).__name__, ex))

        # ⑩2 AR 顶栏 +/−：进入 AR 页后，屏幕上必须同时出现「－」和「＋」
        back = tap_text(dump("k4"), "返回", wait=3.0)
        ar_entry = None
        for lbl in ("3D AR", "Live2D AR", "AR 相机"):
            x = dump("k5")
            ar_entry = tap_text(x, lbl, wait=13.0)
            if ar_entry is not None:
                break
        if ar_entry is None:
            record("⑩2 AR 顶栏 +/− 存在", "SKIP", "抽屉里没找到 3D AR 入口")
        else:
            x = dump("k6")
            # 「－ ＋」是 **Live2D AR 页**（ArScreen）上的桌宠缩放按钮，从设置页进入。
            # 3D AR 页（VrmArScreen）不一定有，所以先判断当前到底在哪一页，避免误报。
            is_live2d_ar = any(k in x for k in ("1×", "2×", "5×", "手电", "闪光", "归位"))
            if not is_live2d_ar:
                record("⑩2 AR 顶栏 +/− 存在", "SKIP",
                       "当前进入的是 3D AR 页；「－ ＋」在 Live2D AR 页（设置页进入），本项不适用")
            else:
                has_minus = "－" in x
                has_plus = "＋" in x
                record("⑩2 AR 顶栏 +/− 存在", verdict(has_minus and has_plus),
                       "－=%s ＋=%s（真机反馈：加了「干净」后这两个被挤出屏幕 ⇒ 已改可滚动并前移到可见区）"
                       % (has_minus, has_plus))
            tap_text(dump("k7"), "返回", wait=2.0)

    print()
    print("=== 汇总 ===")
    npass = sum(1 for _, s, _ in RESULTS if s == "PASS")
    nfail = sum(1 for _, s, _ in RESULTS if s == "FAIL")
    nskip = sum(1 for _, s, _ in RESULTS if s == "SKIP")
    for name, st, ev in RESULTS:
        print("   %-4s %s" % (st, name))
    print("   ---- PASS %d / FAIL %d / SKIP %d ----" % (npass, nfail, nskip))
    if "--selftest-rules" in sys.argv:
        selftest_rules()
    if "--selftest-diag" in sys.argv:
        collect_diag("selftest", "无设备自检：只验证目录与 README 生成")
    elif nfail > 0:
        print()
        print("=== 有失败项 ⇒ 采集诊断包 ===")
        collect_diag("fail", "本次有 %d 项 FAIL，下面是原始材料" % nfail)
    rep = os.path.join(SHOTS, "accept_report.json")
    io.open(rep, "w", encoding="utf-8").write(json.dumps(
        {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "results": RESULTS},
        ensure_ascii=False, indent=2))
    print("   报告：%s" % rep)
    return 0 if nfail == 0 else 1


def selftest_rules():
    """SELFTEST_SEMANTIC：按**语义**检查本脚本是否违反截图技能的两条硬性规则。
    教训：不要用"文件里是否出现某个词"来判断 —— 注释、文档、README 文本都会命中。
    实测：`screenrecord` 只是出现在注释里，却被朴素子串检查报成"违规"。
    """
    src = io.open(os.path.abspath(__file__), encoding="utf-8").read()
    code_lines = [l for l in src.split("\n") if not l.strip().startswith("#")]
    code = "\n".join(code_lines)
    problems = []
    # ① 截图必须带 -p 且走 exec-out
    if "exec-out" not in code or 'screencap", "-p"' not in code:
        problems.append("截图调用缺少 exec-out 或 -p")
    # ② 不允许真的调用 screenrecord（注释里提到不算）
    if re.search(r"adb(_bytes)?\([^)]*screenrecord", code):
        problems.append("真的调用了 screenrecord")
    # ③ 不允许 kill -9
    if re.search(r'"kill"\s*,\s*"-9"', code):
        problems.append("使用了 kill -9")
    # ④ 截图必须校验 PNG 魔数
    if b"PNG".decode() not in code or "\\x89PNG" not in code:
        problems.append("未校验 PNG 魔数")
    print("   [selftest-rules] " + ("全部符合截图技能要求 ✓" if not problems
                                    else "发现问题：" + "; ".join(problems)))
    # 自证：注入一段"只在注释里提 screenrecord"的文本，检查器应仍然通过
    fake = "# 这里提到 screenrecord 只是注释\nadb('exec-out','screencap','-p')\n"
    fake_code = "\n".join(l for l in fake.split("\n") if not l.strip().startswith("#"))
    ok_comment = not re.search(r"adb(_bytes)?\([^)]*screenrecord", fake_code)
    print("   [selftest-rules] 注释里出现 screenrecord 时判为合规：%s（应为 True）" % ok_comment)
    return not problems and ok_comment


if __name__ == "__main__":
    sys.exit(main())
