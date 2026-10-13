# -*- coding: utf-8 -*-
"""停掉桌宠 + 提交"真实启动路径"的验收证据。"""
import io
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

# ① 停掉桌宠相关进程
print("=== 停掉桌宠 ===")
r = subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_Process -Filter \"Name like '%python%'\" | "
                    "Select-Object ProcessId,CommandLine | ConvertTo-Csv -NoTypeInformation"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
killed = 0
for line in (r.stdout or "").splitlines()[1:]:
    f = [x.strip('"') for x in line.split('","')]
    if len(f) >= 2 and any(k in f[1] for k in ("run.py", "main.py", "f5tts_server", "GPT-SoVITS")):
        try:
            subprocess.run(["taskkill", "/PID", f[0], "/F"], capture_output=True, timeout=60)
            killed += 1
        except Exception:
            pass
time.sleep(2)
print("   已停 %d 个进程" % killed)

# ② 写验收记录
D = os.path.join(ROOT, "dev", "docs", "桌宠真实启动验收-2026-10-13.md")
io.open(D, "w", encoding="utf-8", newline="\n").write("""# 桌宠真实启动验收（2026-10-13，全部改动落地后）

> 目的：测试全绿只是"没人报警"，还要**真把它跑起来**看一眼。
> 本机实测：`runtime\\venv\\Scripts\\python.exe run.py`，截图 `dev/shots/pet_after_all_fixes.png`。

## 一、进程与服务（都在）
```
run.py（venv）→ 拉起 base python run.py → GPT-SoVITS runtime python → f5tts_server → main.py
```
与之前验证过一次的进程树一致；F5-TTS 与 GPT-SoVITS 都正常常驻。

## 二、控制台证据（这一串恰好覆盖本轮改过的每一处）
| 日志 | 对应本轮哪处改动 | 结论 |
|---|---|---|
| `[插件] ✅ 已加载：系统信息（看看电脑的 CPU/内存/磁盘/开机多久）` | **恢复 tool/plugins.py 超集版** | 插件系统真的在跑（不是只有测试过） |
| `[插件] ⚠ 跳过 _模板例子：plugin.json 里标了 enabled=false` | 同上（尊重 enabled=false） | 行为正确 |
| `[PC] 键鼠规则未注入：菜单里的「允许操控电脑（键鼠）」没开 → 她只会嘴上答应` | **菜单开关的门控** | 关着就真的不注入，不会偷偷操作电脑 |
| `[AIpet] 开机问候：等语音服务就绪…（第 5 次探测，最多等 300 秒）` → `已让角色打招呼` | **开机问候三档 + voice/chat 逻辑** | 等就绪再开口，没有硬失败 |
| `[qwen-talk] Reply:「主人～本座等你好久啦！」「今天想吃芭菲，还是布丁？」` | 对话链路 | 她在正常说话 |
| `[qwen-portrait] Reply: [[1950,1951,1964,1958,1273], …]` | **立绘/装扮层解析** | 图层号解析正常（与换装排查结论一致） |
| `[qwen-translate]` → `ご主人～！吾輩は…` | 翻译链路 | 日文输出正常 |
| `[gpt-sovits-tts]` | 角色专属语音 | 她自己的声线 |
| 立绘在屏幕右侧正常渲染 | **状态窗/颜色/主题那批改动** | 没有把界面改坏 |

## 三、结论
- **没有 Traceback / 异常**（日志里唯一像"错误"的字样来自我自己的命令回显，不是程序输出）；
- 本轮改动（插件系统、菜单门控、开机问候、配色/主题、状态窗样式）**在真实启动路径上都没问题**；
- 桌面宠物可以在修完这一大批问题后**正常对外演示**（这也正是"没办法端出去给别人看"要解决的）。

> 备注：截图里能看到 DSH 窗口与终端；真要拿去讲 PPT，按
> `dev/docs/PPT录屏截图操作单-2026-10-13.md` 重录一张干净的即可。
""")
print("✓ 已写验收记录 dev/docs/桌宠真实启动验收-2026-10-13.md")

MSG = """docs: 桌宠真实启动验收 —— 全部改动落地后实测跑通（含截图与控制台证据）

测试全绿只说明"没人报警"，所以又**真把它跑起来**验证了一遍（用户原话：可以实际打开操作）。
截图：dev/shots/pet_after_all_fixes.png；记录：dev/docs/桌宠真实启动验收-2026-10-13.md。

进程树正常：run.py(venv) → base python run.py → GPT-SoVITS runtime → f5tts_server → main.py

控制台证据**恰好覆盖本轮改过的每一处**：
  · [插件] ✅ 已加载：系统信息…        ← 恢复的 tool/plugins.py 超集版**真在跑**（不只是测试过）
  · [插件] ⚠ 跳过 _模板例子（enabled=false） ← 尊重开关
  · [PC] 键鼠规则未注入：菜单里的「允许操控电脑」没开 → 她只会嘴上答应 ← 菜单门控生效
  · [AIpet] 开机问候：等语音服务就绪… → 已让角色打招呼        ← 开机问候三档逻辑正常
  · [qwen-talk] Reply:「主人～本座等你好久啦！」…            ← 对话链路
  · [qwen-portrait] Reply: [[1950,1951,1964,1958,1273], …]  ← 立绘图层解析（与换装排查一致）
  · [qwen-translate] → ご主人～！… / [gpt-sovits-tts]         ← 翻译 + 角色专属声线
  · 立绘在屏幕右侧正常渲染                                   ← 颜色/主题/状态窗那批改动没改坏界面

结论：**无 Traceback / 无异常**；本轮改动在真实启动路径上都没问题；
      桌面宠物在修完这一大批问题后**可以正常对外演示**了。
验证完已把桌宠进程停掉（不占 GPU）。
"""
p = os.path.join(MAP, "_msg_runtime.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:160])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
