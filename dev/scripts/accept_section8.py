# -*- coding: utf-8 -*-
"""给 accept_all.py 增加第 ⑧ 节：5 条"只能真机验证"的精确判据（字符串全部来自读源码）。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
A = os.path.join(MAIN, "dev", "scripts", "accept_all.py")

t = io.open(A, encoding="utf-8").read().replace("\r\n", "\n")
if "只能真机验证" in t:
    print("· 已有第 ⑧ 节")
else:
    block = '''    # ===== ⑧ 只能真机验证的 5 项（判据字符串全部来自读源码，不是凭记忆）=====
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

    # ⑧-2 资产种子完整性：注册表在、每个角色的 pet.json 非空、且没有残留 .part
    ls = adb("shell", "ls", "-l", EXT + "/pets/")
    ls2 = adb("shell", "ls", EXT + "/pets/*/pet.json")
    parts = adb("shell", "find", EXT + "/pets", "-name", "*.part")
    has_reg = "pet_list.json" in (ls or "")
    has_pet = "pet.json" in (ls2 or "") and "No such file" not in (ls2 or "")
    part_cnt = len([x for x in (parts or "").splitlines() if x.strip() and "No such file" not in x])
    record("⑧2 资产种子完整性", verdict(has_reg and has_pet and part_cnt == 0),
           "注册表=%s pet.json=%s 残留.part=%d" % (has_reg, has_pet, part_cnt))

    # ⑧-3 Silero 真机阈值：读 vad.log 的 ready 行（里面带实际生效的 threshold/minSilence）
    vlog = read_log("vad.log")
    rdy = [l for l in (vlog or "").splitlines() if "Silero VAD ready" in l]
    record("⑧3 Silero 真机阈值", verdict(bool(rdy)),
           (rdy[-1].strip()[:150] if rdy else "(vad.log 里没有『Silero VAD ready』—— 说明 Silero 没初始化成功)"))

    # ⑧-4 onGiveUp → 系统 TTS：voice.log 里**不该**出现"未提供 onGiveUp"（说明调用点已接线）
    voicelog = read_log("voice.log")
    warn = [l for l in (voicelog or "").splitlines() if "未提供 onGiveUp" in l]
    fell = [l for l in (voicelog or "").splitlines() if "通知调用方回退系统 TTS" in l]
    record("⑧4 onGiveUp 已接线", verdict(not warn and bool((voicelog or "").strip())),
           ("出现过 %d 次回退事件；未提供回调告警 %d 次" % (len(fell), len(warn)))
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

'''
    anchor = '''    print()
    print("=== 汇总 ===")'''
    if anchor in t:
        t = t.replace(anchor, block + anchor, 1)
        io.open(A, "w", encoding="utf-8", newline="\n").write(t)
        print("✓ 已插入第 ⑧ 节（5 项）")
    else:
        print("✗ 未找到汇总锚点")
        sys.exit(1)

print()
print("=== 语法 + dry-run ===")
r = subprocess.run([sys.executable, "-c",
                    "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % A],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print("   语法:", "OK" if r.returncode == 0 else "FAIL\n" + (r.stderr or "")[:400])
if r.returncode != 0:
    sys.exit(1)
r2 = subprocess.run([sys.executable, "-u", A, "--dry-run"], capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=900,
                    env=dict(os.environ, PYTHONIOENCODING="utf-8"))
out = (r2.stdout or "") + (r2.stderr or "")
i = out.find("=== 4. 只能真机验证")
j = out.find("=== 汇总")
print(out[i:j] if i > 0 else "(未找到第 ⑧ 节输出)")
print(out[j:] if j > 0 else out[-400:])
print("   退出码:", r2.returncode)
