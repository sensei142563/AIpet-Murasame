# -*- coding: utf-8 -*-
"""修测试预期（首次写入不产生备份），重跑 → 全量回归 → 提交。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
T = os.path.join(CHAT, "app/src/test/java/com/aipet/murasame/PendingInboxTest.kt")
MAP = os.path.join(MAIN, "dev", "merge-map")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

t = io.open(T, encoding="utf-8").read().replace("\r\n", "\n")
old = '''        PendingInbox.append(base, item(1))
        // 模拟"写一半被杀"：把文件截断成半截 JSON'''
new = '''        PendingInbox.append(base, item(1))
        PendingInbox.append(base, item(2))   // 第二次写入才会产生 .bak（首次写入时旧文件不存在）
        // 模拟"写一半被杀"：把文件截断成半截 JSON'''
if old in t:
    t = t.replace(old, new, 1)
    t = t.replace('''        assertTrue("旧备份仍在", File(pending.parentFile, "pending.json.bak").isFile)''',
                  '''        // 备份只在"旧文件已有内容"时才产生 ⇒ 这里追加了两次，所以应当有
        assertTrue("旧备份仍在", File(pending.parentFile, "pending.json.bak").isFile)''', 1)
    io.open(T, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ 已修测试（追加两次以产生备份）")
else:
    print("⚠ 锚点未命中")

print()
print("=== 全量单测 + release ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), ":app:testDebugUnitTest", "assembleRelease",
                    "--console=plain"], cwd=CHAT, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
for l in o.splitlines():
    if l.strip().startswith("BUILD") or l.startswith("e: ") or "FAILED" in l:
        print("   " + l.strip()[:200])
d = os.path.join(CHAT, "app/build/test-results/testDebugUnitTest")
tot = fail = 0
for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
    if f.endswith(".xml"):
        x = io.open(os.path.join(d, f), encoding="utf-8", errors="replace").read()
        m = re.search(r'tests="(\d+)" skipped="\d+" failures="(\d+)" errors="(\d+)"', x)
        if m:
            tt = int(m.group(1)); fl = int(m.group(2)) + int(m.group(3))
            tot += tt; fail += fl
            print("   %-24s tests=%-3d 失败=%d" % (f.replace("TEST-com.aipet.murasame.", "").replace(".xml", ""), tt, fl))
print("   合计 %d 用例，失败 %d；退出码 %d" % (tot, fail, r.returncode))
if r.returncode != 0 or fail:
    for f in os.listdir(d) if os.path.isdir(d) else []:
        if f.endswith(".xml"):
            x = io.open(os.path.join(d, f), encoding="utf-8", errors="replace").read()
            for mm in re.finditer(r'<testcase name="([^"]+)"[^>]*>\s*<(failure|error)[^>]*>([^<]{0,220})', x):
                print("      ✗ %s → %s" % (mm.group(1), mm.group(3).replace("\n", " ").strip()[:200]))
    sys.exit(1)

MSG = """fix(ilink): 微信桥的凭据与收件箱加固（凭据不再"静默失效"、未回复消息不再被覆盖）

对抗审查 bot/ilink/*（微信/企业微信桥），读代码得到两处真问题：

① CredentialStore 三个文件全是**非原子写**（wechat_credentials.json / wechat_sync_buf.txt /
   wechat_context_tokens.json），而且凭据文件损坏时 readJson 静默返回 null ⇒ credentials() 变 null
   ⇒ 整个微信桥**静默失效**：用户只会觉得"发了消息没反应"，日志里也看不出原因。
   修法：三处改 SafeStore.writeAtomic；readJson 改用 SafeStore.readWithRecovery（损坏即**隔离**
   改名保留）并**明确告警**，留下可查痕迹。

② PendingInbox.load 读到损坏文件时得到空列表，而下一次 save 会把原文件**覆盖掉** ——
   那些"还没回复的用户消息"就永久消失了（与聊天记录那条路径同类）。
   修法：load 改走 SafeStore.readWithRecovery（坏主文件隔离 + 尝试 .bak 恢复）；
   save 统一走 SafeStore.writeAtomicWithBackup（语义与原来的 tmp+move 相同，另留 .bak）。

单测 PendingInboxTest（6 个，纯 JVM —— 它只依赖 java.io.File，不碰 Android）：
  追加/读取往返（含 .bak 生成）；**messageId 幂等**（同 id 覆盖而非重复）；remove（含删不存在的 id）；
  **损坏文件被隔离且未被覆盖**（隔离文件里能看到原内容片段，之后追加仍可用）；
  主文件损坏时**从 .bak 恢复**；文件不存在时读空且不产生副作用。

我自己的一处错误（如实记录）：第一次断言"首次写入后就应有 .bak"——实际备份只在
"旧文件已有内容"时产生，是**测试**错了，已改为追加两次后再断言。

验证：PendingInboxTest 6/6；全量单测 122 个用例失败 0；release 构建通过。
诚实标注：CredentialStore 的加解密走 Android Keystore，无法在 JVM 单测里覆盖其加解密分支，
本次只对文件层（原子写/隔离/告警）负责；真机上的登录流程未验。
"""
p = os.path.join(MAP, "_msg_ilink.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("手机仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:140])
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
r2 = subprocess.run(["git", "-C", MAIN, "commit", "-m", "chore(scripts): ilink 加固脚本"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
print("桌面仓:", (r2.stdout or r2.stderr or "").splitlines()[0][:140])
for nm, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True, encoding="utf-8").stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True,
                        text=True, encoding="utf-8").stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (nm, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
