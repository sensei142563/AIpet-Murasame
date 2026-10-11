# -*- coding: utf-8 -*-
"""提交 QQ 通道只读接口 + 发送队列。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(MAIN, "dev", "merge-map")

MSG = """feat(qq): /qq/status /qq/sessions /qq/messages + /qq/queue/send —— QQ 聊天搬手机第一步

背景（调研结论）：桌面端 QQ 是 17 个模块（qq_bridge.py 136KB + qq_chat/qq_memory/qq_vision/
qq_stt/qq_learn/qq_commands/qq_galgame... ），连接方式是 **NapCat 的 OneBot11 正向 WebSocket**
（ws://127.0.0.1:3001，API 调用也走这条），HTTP 6099 只是 NapCat WebUI 面板。
NapCat 是 PC 端 QQNT 插件，**手机装不了** → 所以"把 QQ 聊天搬到手机"的现实形态是：
手机成为电脑 QQ 通道的**远端界面**（复用已打通的 USB/热点链路），实时收发仍留在握着 WS 的桌面端进程。

本提交（api.py，零风险只读 + 一个队列）：
  · GET  /qq/status    连接方式、NapCat WS 端口是否在听、主人 QQ、会话目录、会话数
  · GET  /qq/sessions  列出所有 QQ 会话（私聊 {id}.json / 群 group_{gid}.json），带消息数与末条预览
  · GET  /qq/messages  某会话最近 N 条
  · POST /qq/queue/send 把待发消息追加到 data/qq_outbox.jsonl（target_type/target_id/text|sticker+queued_at），
                        桌面端轮询后经 OneBot11 WS 发出（下一步接）
  · 会话路径不靠猜：用 importlib 加载 qq/qq_memory.py 并调用它的 _active_qq_memory_dir()，
    与桌面端保持同一处事实来源。

实测（api 重启后）：
  /qq/status → qq_enabled=true, ws=ws://127.0.0.1:3001, napcat_ws_listening=false（NapCat 未运行，如实报告）,
               owner_id=3559307823, memory_dir=pets/murasame/memory/qq, sessions=2（已有真实存量）
  /qq/sessions 与 /qq/messages 用合成会话文件验证通过（写→列→读→末条预览一致），验证后已删除合成文件
  /qq/queue/send → ok，data/qq_outbox.jsonl 追加成功

踩坑记录：api.py 原本没有 import re（我加路由时用到 re.search）→ 500 NameError；
以及必须补 import io/socket/asyncio/time——加路由前先确认依赖齐全。
"""
p = os.path.join(MAP, "_msg_qq1.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
r = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
print("桌面仓:", (r.stdout or r.stderr or "").splitlines()[0][:130])
n = subprocess.run(["git", "-C", MAIN, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True).stdout.strip()
st = subprocess.run(["git", "-C", MAIN, "status", "--porcelain"],
                    capture_output=True, text=True).stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
