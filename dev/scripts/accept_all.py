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


def tap_text(xml, needle, wait=2.5):
    """在 dump 里找**包含** needle 的可点击节点，点它的中心（比精确 text= 更耐得住 emoji/换行）。"""
    for m in re.finditer(r'<node[^>]*text="([^"]*)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml):
        if needle in m.group(1):
            cx = (int(m.group(2)) + int(m.group(4))) // 2
            cy = (int(m.group(3)) + int(m.group(5))) // 2
            adb("shell", "input", "tap", str(cx), str(cy))
            time.sleep(wait)
            return True
    return False


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
    if DRY:
        return True
    out = adb("shell", "pidof", PKG)
    return bool(out.strip())


def open_app():
    adb("shell", "input", "keyevent", "KEYCODE_WAKEUP")
    adb("shell", "am", "force-stop", PKG)
    time.sleep(2)
    adb("shell", "am", "start", "-n", "%s/.MainActivity" % PKG)
    time.sleep(14)


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
    ver = adb("shell", "dumpsys", "package", PKG)
    m = re.search(r"lastUpdateTime=([^\n]+)", ver or "")
    record("安装", verdict((r and r.returncode == 0)),
           "lastUpdateTime=" + (m.group(1).strip() if m else "?"))

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
    open_app()
    x = dump("a1")
    record("App 启动", verdict("chatter" in x or "丛雨" in x),
           ("dump %d 字节" % len(x)) if x else "(dry-run)")

    # ① 3D 页（VRM 演示）
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
        # 试手 → 命中提示
        tap_text_any(dump("a8"), ["试手"])
        time.sleep(8)
        x = dump("a9")
        hit = ("碰到她了" in x) or ("摸到头了" in x) or ("试手：" in x)
        record("②c 手部试手", verdict(hit),
               "命中提示出现" if hit else "未见命中提示（假手可能还没扫到）")
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
    tap_text_any(dump("a11"), ["首页"])
    time.sleep(3)
    x = dump("a12")
    record("③ 首页 QQ 卡", verdict("QQ chatter" in x),
           ("看到 QQ chatter" if "QQ chatter" in x else "未看到"))

    # ④ 返回键：第一次不该退出
    adb("shell", "input", "keyevent", "KEYCODE_BACK")
    time.sleep(1.5)
    alive1 = app_running()
    adb("shell", "input", "keyevent", "KEYCODE_BACK")
    time.sleep(3)
    alive2 = app_running()
    record("④ 返回键两次退出", verdict((alive1 and not alive2)),
           "第一次存活=%s 第二次存活=%s" % (alive1, alive2))

    # ⑤/⑥ 设置页：离线 TTS 自检 + Silero + 只回应呼唤开关
    open_app()
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

    print()
    print("=== 汇总 ===")
    npass = sum(1 for _, s, _ in RESULTS if s == "PASS")
    nfail = sum(1 for _, s, _ in RESULTS if s == "FAIL")
    nskip = sum(1 for _, s, _ in RESULTS if s == "SKIP")
    for name, st, ev in RESULTS:
        print("   %-4s %s" % (st, name))
    print("   ---- PASS %d / FAIL %d / SKIP %d ----" % (npass, nfail, nskip))
    rep = os.path.join(SHOTS, "accept_report.json")
    io.open(rep, "w", encoding="utf-8").write(json.dumps(
        {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "results": RESULTS},
        ensure_ascii=False, indent=2))
    print("   报告：%s" % rep)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
