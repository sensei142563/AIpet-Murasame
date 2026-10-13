# -*- coding: utf-8 -*-
"""修 README 1430 行：api.py / main.py / run.py 三个角色标签全错位。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")
R = os.path.join(ROOT, "README.md")

t = io.open(R, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")

OLD = ("| `api.py` / `main.py` / `run.py` | 桌宠本体：启动器 / FastAPI 后端 / 主窗口 |")
NEW = ("| `run.py` / `main.py` / `api.py` | 桌宠本体三件套，**按启动顺序**："
       "`run.py` = 启动器（引导环境、拉起各服务与主窗口）→ "
       "`main.py` = 主窗口（PyQt 界面 + 本地 FastAPI 接口）→ "
       "`api.py` = 独立的 FastAPI 后端接口 |")
if OLD in t:
    t = t.replace(OLD, NEW, 1)
    io.open(R, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ 已更正 README 那个三件套的说明（原来三个标签全错位）")
else:
    print("✗ 锚点未命中；当前那一行是：")
    for i, l in enumerate(io.open(R, encoding="utf-8", errors="replace").read().split("\n"), 1):
        if "api.py" in l and "main.py" in l:
            print("   %5d| %s" % (i, l.strip()[:130]))

print()
print("=== 复核 ===")
for i, l in enumerate(io.open(R, encoding="utf-8", errors="replace").read().split("\n"), 1):
    if "run.py` / `main.py` / `api.py" in l or ("api.py" in l and "main.py" in l and "run.py" in l):
        print("   %5d| %s" % (i, l.strip()[:150]))

MSG = """docs(readme): 更正「桌宠本体三件套」的角色说明 —— 三个标签原来全错位

README 原第 1430 行：
    | `api.py` / `main.py` / `run.py` | 桌宠本体：启动器 / FastAPI 后端 / 主窗口 |
按顺序对应就是：api.py=启动器、main.py=FastAPI 后端、run.py=主窗口 —— **三个全错**。

实测（逐个文件抓特征）：
    api.py   → FastAPI/uvicorn（后端接口），840 行
    main.py  → FastAPI + PyQt 图形界面 + Qt 控件 + 拉起子进程，1451 行 ⇒ **主窗口本体**
    run.py   → 拉起子进程 + 环境安装/引导，1257 行 ⇒ **启动器**

改为按**启动顺序**写清：
    `run.py` = 启动器（引导环境、拉起各服务与主窗口）
    `main.py` = 主窗口（PyQt 界面 + 本地 FastAPI 接口）
    `api.py` = 独立的 FastAPI 后端接口

## 说明
这是今天**第三次**遇到"标签对错了对象"（前两次：测试里断言按「视觉来源」而界面用「识别来源」；
`data/tts_model.json` 里 gpt/sovits 互换）。三次都不是崩溃型 bug，
但都会让人（和脚本）**看错东西**，而且都能一路不被发现。
分不清"我改的这个标签对的是哪一项"，是这类问题的共同点。
"""
p = os.path.join(MAP, "_msg_readme_roles.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:170])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
