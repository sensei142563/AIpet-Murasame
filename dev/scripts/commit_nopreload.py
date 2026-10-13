# -*- coding: utf-8 -*-
"""提交：自动预载语音服务改为默认关闭；并跑全量自检。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

MSG = """fix(launcher): 启动器不再"一开就自动预载语音" —— 主人还没选桌宠呢

## 主人的原话
"这个，应该是打开桌宠以后再运行啊，我都没确定打开哪个桌宠。"

## 现场查到的（不是猜）
```
PID 24720 run_launcher.py (venv)
  └ 34688 run_launcher.py            ← 启动器本体（窗口："AIpet 丛雨桌宠 · 启动器"）
      └ 30244 tool/tts_service.py    ← 启动 4 秒后**自动**拉起
          └ 18224 tool/tts_service.py preload
⇒ 触发点：pcl_launcher/silicon_window.py:1024
      QTimer.singleShot(2500, self._auto_preload_tts)   # 开启动器 2.5 秒后自动预载
   注释自述"和点『预载语音服务』走同一条路，只是不用手动点" ⇒ 是**有意**的自动行为。
   但它用的是配置里的**当前角色**（这里是丛雨）—— 主人并未选过。
```

## 改成什么
- `_auto_preload_tts()` 开头加开关：**默认不自动预载**
  （`config.json` 写 `"auto_preload_tts": "true"` 可恢复原行为；不写就是关）。
- 保留手动按钮「预载语音服务」不变。
- 启动桌宠时（`run.py`）本来就会拉起语音服务 —— 这才是主人期望的时机。
- 排定时那句注释同步改掉，写明"默认关闭 / 怎么恢复 / 为什么"。

## 验证
```
py_compile silicon_window.py ✓
现场清理：杀掉在飞的预载链（18224/30244），只留启动器 34688 ✓
9880 / 9881 均空闲 ✓
全量自检见下（改了启动器文件，必须回归）
```

## 附注（顺带解释主人为什么会注意到）
今天刚给语音服务加了"控制台外壳"（有标题、只打横幅），**窗口变得显眼了**，
所以这个一直存在的自动预载行为才被看见 —— 换句话说，是这次改动把它**暴露**出来的，
不是这次改动**引入**的。现在连行为一起修正。
"""
p = os.path.join(MAP, "_msg_nopreload.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:170])

print()
print("=== 全量自检 ===")
r = subprocess.run([os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe"),
                    os.path.join(ROOT, "tests", "run_all.py")],
                   cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                   errors="replace", timeout=1800)
for l in ((r.stdout or "") + (r.stderr or "")).split("\n")[-4:]:
    print("   " + l.strip()[:120])

n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print()
print("未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
