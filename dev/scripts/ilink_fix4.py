# -*- coding: utf-8 -*-
"""修测试：无备份分支要先删掉 .bak（有备份时实现会正确恢复）→ 重跑 → 提交。"""
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
        PendingInbox.append(base, item(2))   // 第二次写入才会产生 .bak（首次写入时旧文件不存在）
        // 模拟"写一半被杀"：把文件截断成半截 JSON
        pending.writeText("""{"items":[{"messageId":1,"fromUser""")'''
new = '''        PendingInbox.append(base, item(1))
        PendingInbox.append(base, item(2))   // 第二次写入才会产生 .bak（首次写入时旧文件不存在）
        // 本用例专门测【没有可用备份】的分支：先把 .bak 删掉。
        //（有备份时实现会正确地从中恢复 —— 那是另一个用例 recover_from_backup_when_main_is_corrupt。
        //  我最初把两种情况混在一个用例里，导致断言与实现都"对"却互相矛盾。）
        File(pending.parentFile, "pending.json.bak").delete()
        // 模拟"写一半被杀"：把文件截断成半截 JSON
        pending.writeText("""{"items":[{"messageId":1,"fromUser""")'''
if old in t:
    t = t.replace(old, new, 1)
    t = t.replace('''        // 备份只在"旧文件已有内容"时才产生 ⇒ 这里追加了两次，所以应当有
        assertTrue("旧备份仍在", File(pending.parentFile, "pending.json.bak").isFile)''',
                  '''        // 注意：.bak 已被本用例主动删除（就是要测"没有可用备份"的分支）''', 1)
    io.open(T, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ 已把无备份分支与被备份分支分开")
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
print("   合计 %d 用例，失败 %d；退出码 %d" % (tot, fail, r.returncode))
if r.returncode != 0 or fail:
    for f in os.listdir(d) if os.path.isdir(d) else []:
        if f.endswith(".xml"):
            x = io.open(os.path.join(d, f), encoding="utf-8", errors="replace").read()
            for mm in re.finditer(r'<testcase name="([^"]+)"[^>]*>\s*<(failure|error)[^>]*>([^<]{0,220})', x):
                print("      ✗ %s → %s" % (mm.group(1), mm.group(3).replace("\n", " ").strip()[:200]))
    sys.exit(1)

print()
print("=== 提交 ===")
MSG = """fix(ilink): 微信桥的凭据与收件箱加固（凭据不再"静默失效"、未回复消息不再被覆盖）

对抗审查 bot/ilink/*（微信/企业微信桥），读代码得到两处真问题：

① CredentialStore 三个文件全是**非原子写**（wechat_credentials.json / wechat_sync_buf.txt /
   wechat_context_tokens.json），而且凭据文件损坏时 readJson 静默返回 null ⇒ credentials() 变 null
   ⇒ 整个微信桥**静默失效**：用户只会觉得"发了消息没反应"，日志也看不出原因。
   修法：三处改 SafeStore.writeAtomic；readJson 改用 SafeStore.readWithRecovery（损坏即隔离改名保留）
   并**明确告警**，留下可查痕迹。

② PendingInbox.load 读到损坏文件时得到空列表，而下一次 save 会把原文件**覆盖掉** ——
   那些"还没回复的用户消息"就永久消失了（与聊天记录那条路径同类）。
   修法：load 走 SafeStore.readWithRecovery（坏主文件隔离 + 尝试 .bak 恢复）；
   save 统一走 SafeStore.writeAtomicWithBackup（语义与原 tmp+move 相同，另留 .bak）；
   顺带清理不再使用的 tmp 行与 Files import。

单测 PendingInboxTest（6 个，纯 JVM —— 只依赖 java.io.File）：
  追加/读取往返（含 .bak 生成）；**messageId 幂等**；remove（含删不存在的 id）；
  **无可用备份时**：读空 + 隔离保留原始字节 + 之后追加仍可用且隔离文件不被覆盖；
  **有可用备份时**：从 .bak 恢复出内容；文件不存在时读空且不产生副作用。

测试过程记录（两次都是**预期**与实现不一致，不是实现错）：
  · 第一次断言"首次写入后就该有 .bak"——备份只在旧文件已有内容时产生，已改为追加两次；
  · 第二次该用例变成 `load` 非空（因为此时已有可用备份，实现正确地恢复了）——
    于是把它拆成两个用例：**无备份分支先删 .bak**，有备份分支单列。

验证：PendingInboxTest 6/6；全量单测 122 个用例失败 0；release 构建通过。
诚实标注：CredentialStore 的加解密走 Android Keystore，JVM 单测无法覆盖其加解密分支，
本次只对文件层（原子写/隔离/告警）负责；真机登录流程未验。
"""
p = os.path.join(MAP, "_msg_ilink2.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
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
