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

MSG = """fix(chat): 对话主循环两处加固 + 把 SSE 行解析抽成纯函数（6 个单测）

对抗审查 bot/chat/ChatCore.kt（把记忆/模型/TTS/表情串起来的主循环）。
失败处理总体不错（API 错误、网络异常、空回复、记忆保存失败都有中文兜底），
对抗视角下还剩三处，本次修掉：

① **表情标记会泄漏到可见回复**
   parseStickers 原来只在"至少命中一个候选名"时才把 [表情:…] 从文本里删掉 ⇒
   若模型编了不在候选里的名字（或全部不在候选里），标记会**原样显示在聊天里**
   （用户看到「[表情:不存在]」）。现在无论是否命中都剥掉，未命中的只记日志。

② **SSE 行解析内联在流程里，且不容忍行首 BOM/空白**
   原来只判 `line.startsWith("data:")`，一旦行首有 BOM（某些反向代理会插）或空白就 continue
   ⇒ **整个流被跳过** ⇒ 最后显示"（什么都没说出来...）"。
   现抽出纯函数 bot/chat/ChatSse.kt：
     · parseLine —— 去行首 BOM/空白后判 data:，返回负载（非 data 行返回 null）；
     · isDone —— 识别 [DONE]（含前后空白）；
     · deltaOf —— 取 choices[0].delta.content；只有 reasoning_content 时返回空串；
       非法 JSON 返回 null（调用方跳过该事件，而不是中断整轮）。

③ stickerNames() 是调用方 lambda，**没有被兜住** ⇒ 抛异常会中断整轮对话。
   现在 runCatching 包住，异常记日志并退化为"本轮不带表情包"。

单测 ChatSseTest（6 个）：
  data: 的四种写法（有/无空格、[DONE] 有/无空格、中文）；
  **行首 BOM 与空白**；event:/id:/retry:/注释/空行等非 data 行安静跳过；
  [DONE] 判定；delta 提取（正常 / 只有 reasoning_content / 空 choices / 无 choices / 非法 JSON）；
  表情标记：命中剥除并采纳、**未命中也必须剥除**、命中+未命中混合、全角冒号与重复标记只采纳一次、无标记原样返回。

过程记录：第一次补丁没生效（我的锚点里漏了正则里的反斜杠 `\\[`），
是**新测试立刻失败**把它抓住的（失败点正是"未命中的标记仍留在回复里"）——
改成只替换那一行行为代码后通过。测试在这里起到了它该起的作用。

验证：ChatSseTest 6/6；全量单测 109 个用例失败 0；release 构建通过。
"""
p = os.path.join(MAP, "_msg_chatcore.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("手机仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:140])
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
r2 = subprocess.run(["git", "-C", MAIN, "commit", "-m",
                     "chore(scripts): 对话主循环加固脚本（SSE 纯函数化与表情标记剥除）"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
print("桌面仓:", (r2.stdout or r2.stderr or "").splitlines()[0][:140])
for nm, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True, encoding="utf-8").stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True,
                        text=True, encoding="utf-8").stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (nm, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
