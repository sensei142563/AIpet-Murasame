# -*- coding: utf-8 -*-
"""全量回归 + release + 提交（手机仓 & 桌面仓）。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
MAP = os.path.join(MAIN, "dev", "merge-map")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

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
    sys.exit(1)

MSG = """fix(qq): 手机端直连 NapCat 的"去重"其实是空的 —— 补上真去重（9 个单测）

对抗审查 bot/chat/OneBotLocal.kt（手机端直连本机 NapCat 的连接/缓存层），
读代码得到的结论与我原本的假设**不同**，而且更直接：

  · handle() 每收到一条解析成功的消息就**无条件 append** 到会话列表；
  · lastLine / lastAt 这两个字段**只被写入、以及从缓存恢复时赋值，
    从来没有被读过做比较** ⇒ 字段名与注释暗示的"去重"根本不存在；
  · 后果：WebSocket 断线重连后 NapCat 重投的同一条消息会被收两次 ⇒ 她很可能会**回两遍**。

修复（新增 bot/chat/OneBotDedup.kt，纯逻辑、可单测）：
  ① **优先按 messageId 判重**；
  ② messageId 为空/空白时才回落到"同一会话、与上一条内容相同"的启发式
     —— 这样 lastLine 才真正名实相符；
  ③ id 集合按**条数**上限（默认 800）而不是时间窗：重连后的重投可能隔很久才来，
     用时间窗会漏判；而"同一句话连说两次"是不同 id，不会被误杀。
  接进 OneBotLocal：解析后先过去重，重复则记日志丢弃（不再进入会话列表，
  因此后续的自动回复也不会重复触发）。
  另两处顺手修：
  · 缓存写入改**原子写**（复用上一轮的 SafeStore；缓存是可重建数据，坏文件直接覆盖，
    不需要像聊天记录那样隔离保留）；
  · 会话淘汰从"按插入顺序"改为**按最近活跃**（原来与 UI 按 lastAt 排序的口径不一致，
    可能把正在聊的会话挤掉、却留着很久没动的）；淘汰时一并清理去重状态。
  从缓存恢复时把最后一条内容喂给去重器，保持重启前后启发式连续。

单测 OneBotDedupTest（9 个）：
  同一 messageId 第二次⇒拒绝（重投现场）；**不同 id、相同内容⇒必须通过**（正常连发不能误杀）；
  无 id 时回落到上一条内容；回落是**按会话**的（另一个会话相同内容不误判）；
  隔很久的重投仍拒绝（条数上限而非时间窗）；id 集合有上界（并明确记录其代价）；
  forget 清理；seed 后同内容拒绝；空白 id 视同没有 id。

验证：OneBotDedupTest 9/9；全量单测 103 个用例失败 0；release 构建通过。
诚实标注：断线重连的真实重投行为需上机确认（NapCat 侧策略），但去重本身是确定性逻辑。
"""
p = os.path.join(MAP, "_msg_onebotlocal.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("手机仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:140])
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
r2 = subprocess.run(["git", "-C", MAIN, "commit", "-m",
                     "chore(scripts): OneBotLocal 去重审查与修复脚本"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
print("桌面仓:", (r2.stdout or r2.stderr or "").splitlines()[0][:140])
for nm, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True, encoding="utf-8").stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True,
                        text=True, encoding="utf-8").stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (nm, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
