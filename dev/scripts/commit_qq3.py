# -*- coding: utf-8 -*-
"""清掉测试写入的队列文件，提交手机 QQ 页（手机仓）与验收脚本（桌面仓）。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
CHAT = r"E:\university\order\python\pet\chatter"
MAP = os.path.join(MAIN, "dev", "merge-map")

print("=== 清理测试写入的队列 ===")
for n in ("qq_outbox.jsonl", "qq_outbox.offset", "qq_outbox_ack.jsonl"):
    p = os.path.join(MAIN, "data", n)
    if os.path.isfile(p):
        sz = os.path.getsize(p)
        os.unlink(p)
        print("   删 %-22s %d B" % (n, sz))
print("   （队列是运行期数据，不入库；测试条目已清）")

MSG1 = """feat(qq): 手机端 QQ 通道页（状态 / 队列 / 发送 / 会话消息）—— 第 3 步

用户质疑过"你说搬手机了，我在前端没见啊"——确实：此前只做了电脑端接口，手机端一行都没有。
本次补上手机端界面，QQ 这条线才真正"两头都有"。

新增 ui/QqScreen.kt（挂在聊天页 ☰ 抽屉 →「💬 QQ 通道」，不挤底部导航）：
  · 电脑端 QQ 状态：napcat_ws / **NapCat 是否在线** / 主人 QQ / 会话数 / 会话目录；
  · 发送队列：pending_bytes、最近已发送记录（✓/✗ 与时间）；
  · 发一条到 QQ：私聊·群聊切换 + 目标号 + 内容 → POST /qq/queue/send（投递后提示"已投递到队列"）；
  · 会话列表：点开看消息（/qq/messages，含 role/content）。
设计：地址**复用「Jev 电脑地址」**（同一个 api.py），不新增设置项；网络全在 Dispatchers.IO；
OkHttp 超时与"绝不抛异常"照抄 JevClient 的既有约束。

验收（手机没连线时的替代方案，dev/scripts/verify_qq_screen_offline.py）：
  · APK 取证：4 个 dex 里含 QqScreen 与「QQ 通道 / 发送到队列 / NapCat / 待发送字节」全部文案 ✓
  · 契约重放：/qq/status、/qq/sessions（真实会话 1851959578，8 条）、/qq/messages、
    /qq/outbox（pending=116）、/qq/queue/send（ok=true，pending 116→237，队尾即该条）✓
  · 期间发现并修正：/qq/outbox 404 —— 上一轮加了接口但没重启 api，重启后正常。
未完成：真机点击验收（手机当前未连线）与真·端到端（需用户在本机启动 NapCat 并登录）。
"""
p1 = os.path.join(MAP, "_msg_qq3.txt")
io.open(p1, "w", encoding="utf-8", newline="\n").write(MSG1)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r1 = subprocess.run(["git", "-C", CHAT, "commit", "-F", p1], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("手机仓:", (r1.stdout or r1.stderr or "").splitlines()[0][:130])

MSG2 = """chore(qq): 手机 QQ 页的验收脚本（APK dex 取证 + 五接口契约重放）

手机未连线时的替代验收手段，可复跑：
  · verify_qq_screen.py          真机点击验收（需连线：聊天→☰→QQ 通道→看数据→点发送→查 pending）
  · verify_qq_screen_offline.py  APK dex 字符串取证 + 在电脑上原样重放手机页会发的 5 个请求
  · qq_screen_1.py / qq_screen_2.py  建页面 / 重启 api 加载新路由

经验：给 api.py 加路由后**必须重启 api 进程**，否则手机端会看到 404（本次踩到 /qq/outbox）。
"""
p2 = os.path.join(MAP, "_msg_qq4.txt")
io.open(p2, "w", encoding="utf-8", newline="\n").write(MSG2)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
r2 = subprocess.run(["git", "-C", MAIN, "commit", "-F", p2], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("桌面仓:", (r2.stdout or r2.stderr or "").splitlines()[0][:130])

for name, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True).stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"],
                        capture_output=True, text=True).stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (name, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
