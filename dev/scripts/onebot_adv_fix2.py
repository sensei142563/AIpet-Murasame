# -*- coding: utf-8 -*-
"""避免 at 段重复 @（输入里已有字面 @ 时不再补一个），再跑全量 + 提交。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
SRC = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/bot/chat/OneBotParse.kt")
MAP = os.path.join(MAIN, "dev", "merge-map")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

t = io.open(SRC, encoding="utf-8").read().replace("\r\n", "\n")
old = '''                "at" -> sb.append("@" + param)'''
new = '''                // 不同客户端的字符串形态不一样：有的给 "[CQ:at,qq=123]"，
                // 有的前面还有字面 "@"。若前面已经是 @，就别再补一个（否则出现 @@123）。
                "at" -> {
                    if (sb.isEmpty() || sb[sb.length - 1] != '@') sb.append("@")
                    sb.append(param)
                }'''
if old in t:
    t = t.replace(old, new, 1)
    io.open(SRC, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ at 段已避免重复 @")
else:
    print("✗ 锚点未命中")
    sys.exit(1)

print()
print("=== 跑 OneBot 相关测试（对抗 + 原有）===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), ":app:testDebugUnitTest", "--console=plain",
                    "--tests", "com.aipet.murasame.OneBot*"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=3600)
o = (r.stdout or "") + (r.stderr or "")
for l in o.splitlines():
    if re.search(r"tests completed|BUILD|FAILED|^e: ", l):
        print("   " + l.strip()[:185])
d = os.path.join(CHAT, "app/build/test-results/testDebugUnitTest")
for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
    if f.startswith("TEST-com.aipet.murasame.OneBot"):
        x = io.open(os.path.join(d, f), encoding="utf-8", errors="replace").read()
        m = re.search(r'tests="(\d+)" skipped="\d+" failures="(\d+)" errors="(\d+)"', x)
        print("   %-46s tests=%s 失败=%s" % (f.replace("TEST-com.aipet.murasame.", "").replace(".xml", ""),
                                             m.group(1), int(m.group(2)) + int(m.group(3))))
        if int(m.group(2)) + int(m.group(3)):
            for mm in re.finditer(r'<testcase name="([^"]+)"[^>]*>\s*<(failure|error)[^>]*>([^<]{0,220})', x):
                print("      ✗ %s → %s" % (mm.group(1), mm.group(3).replace("\n", " ").strip()[:200]))
            sys.exit(1)

print()
print("=== 全量回归 + release ===")
r2 = subprocess.run([os.path.join(CHAT, "gradlew.bat"), ":app:testDebugUnitTest", "assembleRelease",
                     "--console=plain"], cwd=CHAT, capture_output=True, text=True,
                    encoding="utf-8", errors="replace", env=ENV, timeout=7200)
o2 = (r2.stdout or "") + (r2.stderr or "")
print("   " + next((l for l in o2.splitlines() if l.startswith("BUILD")), "(无)"))
tot = fail = 0
for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
    if f.endswith(".xml"):
        x = io.open(os.path.join(d, f), encoding="utf-8", errors="replace").read()
        m = re.search(r'tests="(\d+)" skipped="\d+" failures="(\d+)" errors="(\d+)"', x)
        if m:
            tt = int(m.group(1)); fl = int(m.group(2)) + int(m.group(3))
            tot += tt; fail += fl
            print("   %-22s tests=%-3d 失败=%d" % (f.replace("TEST-com.aipet.murasame.", "").replace(".xml", ""), tt, fl))
print("   合计 %d 用例，失败 %d" % (tot, fail))
if fail or r2.returncode != 0:
    sys.exit(1)

MSG = """fix(qq): 字符串形态 message 的 CQ 码映射成可读文本（并记录一次"假设不成立"的对抗结果）

对抗审查对象：bot/chat/OneBotParse.kt（手机端每条 QQ 消息都要过的解析层）。

一、先验证一个假设，结果**假设不成立**（这也是收获，附证据）：
    我怀疑 org.json 的 optString() 会把 JSON null 变成字符串 "null"，
    那样 user_id:null 会造出 "private_null" 虚构会话、message:null 会显示一条内容为 null 的消息。
    写测试验证后：**不成立** —— optString 对 JSON null 返回空串，解析层本来就是安全的。
    该结论已用 4 条断言钉住（user_id/group_id/message/nickname 为 JSON null 的各种组合）。

二、对抗视角挖出的真缺口（已修）：
    字符串形态的 message（"[CQ:image,file=abc.jpg]你好"）会被**原样带出 CQ 码**，
    而数组形态本来就会映射成 [图片]/[表情] ⇒ 两种形态观感不一致，用户会以为坏了。
    新增 cqToReadable()：image→[图片]、face→[表情]、record/audio→[语音]、video→[视频]、
    at→@qq、reply→不显示、未知类型→[类型] 占位；并对字符串路径生效。
    实现中自己发现并修掉的小问题：有的客户端在 [CQ:at,qq=…] 前还有字面 "@"，
    直接映射会出现 "@@123" ⇒ 若前面已是 @ 就不再补。

三、我自己的两处错误（如实记录）：
    · 测试里有一条自相矛盾的断言（写 assertNull，注释却说"仍应解析"）⇒ 已按真实语义改为
      "解析成内容为空的一条"；
    · 编译失败一次：提示语里用 ASCII 双引号（"null"）导致字符串提前闭合；更隐蔽的是
      **生成脚本里写的是 \\"null\\"，而 Python 三引号串中 \\" 是合法转义、反斜杠被吃掉**，
      于是生成出来的 Kotlin 成了裸引号。教训：跨语言生成时，提示语里提到字符串一律用中文引号【】/「」；
      另外测试文件由脚本生成，改生成物会被覆盖，必须改脚本本身。

验证：OneBotAdversarialTest 11/11；全量单测（含原有 OneBotParseTest）与 release 构建通过。
"""
p = os.path.join(MAP, "_msg_onebot_adv.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("手机仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:130])
for nm, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True, encoding="utf-8").stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True,
                        text=True, encoding="utf-8").stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (nm, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
