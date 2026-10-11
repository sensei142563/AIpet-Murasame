# -*- coding: utf-8 -*-
"""提交 ④ 记忆互通成果：手机仓 + 桌面仓（各自 git commit -F，绝不上推）；并把 dev/memory_io 加进 .gitignore 防隐私入库。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
CHAT = r"E:\university\order\python\pet\chatter"
MAP = os.path.join(MAIN, "dev", "merge-map")

# ① 桌面 .gitignore：别把她的记忆导出物提交上去
gi = os.path.join(MAIN, ".gitignore")
add = "\n# 记忆导出/导入的实体文件（含她的真实对话，绝不入库）\ndev/memory_io/\n"
s = io.open(gi, encoding="utf-8").read() if os.path.isfile(gi) else ""
if "dev/memory_io/" not in s:
    io.open(gi, "w", encoding="utf-8", newline="\n").write(s.rstrip("\n") + "\n" + add)
    print("✓ 已把 dev/memory_io/ 加入 .gitignore")
else:
    print("· .gitignore 已含 dev/memory_io/")

# ② 手机仓提交
MSG1 = """feat(memory): 记忆导出/导入（④ 记忆互通第一步，ADR-001/009 的"导出格式"）

契约：{"schema":"aipet.memory/1","pet":..,"source":..,"exported_at":..,
       "history":[{role,content,timestamp}],"long_history":[...]}
与桌面端 pets/<id>/memory/{history,long_history}.json 同构；导入兼容三种形状
（本 schema / 桌面裸文件 / 纯数组），按 role|timestamp|content 去重后按时间排序落盘。

MemoryStore：
  · exportBundle(pet?)  导出当前角色记忆
  · importBundle(text)  合并并返回 ImportResult(added/dup/total/pet)
MainActivity（冷启动）：
  · 先扫 getExternalFilesDir()/memory_io/import/*.json 合并，成功后归档到 imported/
  · 再写一份导出快照到 memory_io/export/（顺序必须"先导入后导出"，否则快照是旧状态）
  · 日志标签 MemoryIO，便于 adb logcat 取证

真机验收（dev/scripts/verify_memory_roundtrip2.py，可复跑）：
  · 桌面导出 148 短 + 24 长 = 172 条 → 推入 import/ → App 日志"新增 172"，再推同文件"新增 0 重复 172"；
  · 探针 4 条导入后，手机自己写出的快照里能查到（history 243 / long_history 52）；
  · 反向：手机快照用桌面 CLI 导入临时角色成功（之后已清理）。
"""
p1 = os.path.join(MAP, "_msg_mem1.txt")
io.open(p1, "w", encoding="utf-8", newline="\n").write(MSG1)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
r1 = subprocess.run(["git", "-C", CHAT, "commit", "-F", p1], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("手机仓:", (r1.stdout or r1.stderr or "").splitlines()[0][:110])

# ③ 桌面仓提交
MSG2 = """feat(memory): 桌面端记忆导出/导入 CLI + ④ 记忆互通验收脚本

tool/memory_transfer.py：
  export --pet <id> [--out 路径]  导出为 aipet.memory/1（事件日志的导出格式）
  import <文件.json> [--pet <id>] 合并（兼容裸 {"history":[...]}），去重 + 排序 + 备份 .bak-import
并按手机端同一 key（role|timestamp|content）去重，保证两端可互换。

dev/scripts/：
  mem_transfer_1.py / mem_transfer_2.py  手机端改造与接线（含一次目录用错的修正）
  fix_memio_order.py                    把冷启动顺序改为"先导入、后导出"
  verify_memory_roundtrip.py            首版验收（暴露了"未探测当前角色"的脚本缺陷）
  verify_memory_roundtrip2.py           修正版验收（每轮唯一探针，可重复跑，全绿）

.gitignore 增加 dev/memory_io/：导出物含她的真实对话，绝不入库。
"""
p2 = os.path.join(MAP, "_msg_mem2.txt")
io.open(p2, "w", encoding="utf-8", newline="\n").write(MSG2)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
r2 = subprocess.run(["git", "-C", MAIN, "commit", "-F", p2], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("桌面仓:", (r2.stdout or r2.stderr or "").splitlines()[0][:110])

for name, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True).stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"],
                        capture_output=True, text=True).stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (name, n, "干净 ✓" if not st else "%d 项未提交" % len(st.splitlines())))
