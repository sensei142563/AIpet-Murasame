# -*- coding: utf-8 -*-
"""跑全量测试并提交本轮修复。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")
MAP = os.path.join(ROOT, "dev", "merge-map")

print("=== 全量测试 ===")
r = subprocess.run([VENV, os.path.join("tests", "run_all.py")], cwd=ROOT, capture_output=True,
                   text=True, encoding="utf-8", errors="replace", timeout=1800)
out = (r.stdout or "") + (r.stderr or "")
for l in out.split("\n"):
    if re.match(r"\s*test_\w+\.py\s+-?\d", l) or "总计" in l or "有失败" in l:
        print("   " + l.strip()[:140])

MSG = """fix(config): 修好配置契约 3 项 —— 重复字典键 / 窄真值比较 / 读取式下标

这一批与协作者"健壮性"提交（1d86ec9）面对的是**同一组问题**，但那份提交不在本分支，
所以这里**自己实现**（不拉取、不合并），并逐条验证。

一、tool/jp_names.py：重复字典键（前者会被 Python 静默丢弃）
  · 第 43 行的 `"納得": "接受"` 与第 67 行重复；第 63 行的
    `"目を見開き驚く1"/"目を見開き驚く2"` 与第 76 行重复。
  · 两处**值完全相同** ⇒ 删掉**前一份**，运行时行为不变，只是不再"看着像两份、实际只剩一份"。

二、qq/qq_config.py：窄真值比较
  · `str(cfg.get("qq_private_enable", "true")).lower() == "true"` 这类写法只认字符串 "true"，
    既漏（"1"/"on"/"开" 都算假）又绕（自己造一套规则）。
  · 改为项目自带的 `as_bool(cfg.get(...), True/False)`（同一份文件里 3 处），
    与 `tool/config.py` 的既有语义统一（as_bool 认 1/true/yes/y/on/开/开启 为真）。

三、顶层配置的读取式下标（缺键会直接 KeyError 崩）
  · `chat.py`：`get_config("./config.json")["local_api"]["ollama"]` 等 3 处 + `["tts_type"]`
    → 改为 `.get("local_api") or {}` 后逐键 `.get(..., "")`。
  · `tool/stt.py:128`：`get_config("./config.json")["stt_model"]` → `.get("stt_model", "")`。
  · 说明：这类"读取式下标"在缺键时会抛 KeyError 直接崩，而配置本来就可能缺键
    （`config.json` 与 `config.example.json` 常有差异）。

验证：
  · `tests/test_config_contracts.py` → **"配置契约体检全部通过"，退出码 0**（修前 34 OK / 3 FAIL）。
  · 三个改动文件均通过 py_compile。
"""
p = os.path.join(MAP, "_msg_cfg.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:160])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
