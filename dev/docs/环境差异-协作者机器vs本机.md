# 环境差异：协作者机器 vs 本机（2026-10-13 实测）

> 起因：用户反馈"似乎可能有一些东西在协作者电脑上可以，但咱们电脑不行，因为咱们都是全局 Python、
> 都用 GPU 加速等等的"。本文是**本机实测**结论，不是推测。
> 全部证据都在本机跑出来的（命令与输出见 `dev/scripts/` 下对应脚本）。

## 一、结论速览

| 项 | 本机实测 | 影响 | 处置 |
|---|---|---|---|
| **`comtypes` 缺失** | 项目 venv 与全局 Python **都没有**；而它写在 `requirements.txt` 里 | `tool/uia.py` 报 `[UIA] ⚠ 不可用 → 退回模拟键鼠方式`；`tool/music.py` 明确写"没装 comtypes 只能用系统媒体键"（网易云后台控制失效） | ✅ **已装**（`runtime/venv`，comtypes 1.4.17）→ 复验 `comtypes/UIA 可用: True` |
| pip 残留目录 | `~orch` / `~umpy` / `~umpy-2.1.3.dist-info` / `~umpy.libs` | 每次 pip 操作都报 `Ignoring invalid distribution -umpy` | ✅ **已移到** `dev/tmp/venv_junk/`（不删，留档）→ 告警清零 |
| numpy / opencv 版本冲突 | `pip check`：`opencv-python 4.12.0.88` 要求 `numpy>=2`，实际 `numpy 1.26.4` | 潜在运行时不一致（本机尚未观察到崩） | ⚠ **未自动改**（`requirements.txt` 明确 `numpy>=1.26.4,<2`，动 numpy 风险大，留给用户定） |
| venv 的 `python.exe` 是"转发器" | 242,920 字节；它会拉起一个 base python 子进程 | **不是 bug**：子进程里 `sys.executable` = venv 路径、`sys.prefix` = venv、`torch` 来自 venv ⇒ venv 工作正常 | 无需处理（`run.py` 的检测逻辑已正确处理） |
| 依赖是否齐 | `requirements.txt` 28 条，venv 里**只缺 comtypes** 这 1 条（已补） | — | ✅ |

## 二、实测命令与输出（可复现）

```text
# 1) 缺 comtypes（两个环境都缺）
$ runtime\venv\Scripts\python.exe -c "import comtypes"
ModuleNotFoundError: No module named 'comtypes'
$ python -c "import comtypes"          # 全局 Python 同样
ModuleNotFoundError: No module named 'comtypes'

# 2) 项目自带自检如实报告
$ runtime\venv\Scripts\python.exe tool/uia.py
[UIA] ⚠ 不可用（ModuleNotFoundError: No module named 'comtypes'）→ 退回模拟键鼠方式
comtypes/UIA 可用: False

# 3) 装上之后
$ runtime\venv\Scripts\python.exe -m pip install comtypes
Successfully installed comtypes-1.4.17
$ runtime\venv\Scripts\python.exe tool/uia.py
comtypes/UIA 可用: True
```

## 三、本机桌宠实跑记录（2026-10-13 18:5x）

- 启动：`runtime\venv\Scripts\python.exe run.py`（`启动桌宠.bat` 同款）
- **启动成功**，控制台关键行：
  - `[AIpet] MSVC 运行时无冲突`
  - `[AIpet] 读取配置: model_type = qwen`（云端对话模型）
  - `[AIpet] 自动选择 TTS 环境：自带环境（检测到可用 GPU）`
  - `[AIpet] TTS 使用角色专属模型：murasame → murasame-gpt.ckpt / murasame-sovits.pth`
  - `[AIpet] 启动 F5-TTS 服务（端口 9881）`
  - `[AIpet] 正在运行主程序 main.py` / `TTS 已预热完成`
- 进程与端口实测：`28565` 由 `main.py` 监听 ✓、`9881` 由 F5-TTS 监听 ✓、GPT-SoVITS 常驻 ✓
- 画面实测：**立绘正常渲染**（截图 `dev/shots/pet_locate.png`），她在正常走对话管线
  （`qwen-talk` / `qwen-portrait` / `qwen-emotion` / `qwen-translate` → `gpt-sovits-tts`）

## 四、没能验证的部分（如实标注）

- **右键菜单的实机截图没拿到**：用合成输入（`desktop_input` right_click）点她，
  她弹出了「【丛雨】思考中…」——说明**点击到达了她**，但被当成左键/触摸处理，
  菜单没有打开。⇒ 这一条只能由你**用真实鼠标右键**确认（我已按代码与离屏渲染验证修复正确）。
- 合成输入的坐标空间是**逻辑像素**（屏幕 1920×1080 @1.25 ⇒ 逻辑 1536×864）；
  给超出范围的 x 会被夹到边缘（实测 1775 → 1535）。

## 五、给协作者的同步建议

1. `requirements.txt` 里的 `comtypes` 在**安装流程**里要真的装上（否则 UIA 静默降级，很难发现）。
2. `opencv-python` 与 `numpy<2` 的约束需要二选一：
   要么固定 `opencv-python<4.12`，要么放开 `numpy>=2` 并回归测试。
3. 建议在启动自检里把"关键可选依赖"列出来（本项目已有 `tool/selftest.py`，把 UIA 一项显式报出即可）。
