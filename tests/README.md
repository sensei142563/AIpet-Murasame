# tests/ —— 仓库自带的离线体检

这些是从 2026-09-29/30 的审计里挑出来的**通用体检**：每一条都对应一个**真实撞到过的缺陷**，
不是"为了覆盖率"写的。目标是把"同一个坑不许再踩第二次"变成机器能判的事。

## 怎么跑

```bash
python tests/run_all.py              # 全部（约 20 秒）
python tests/run_all.py bounds       # 只跑名字含 bounds 的
python tests/test_config_contracts.py   # 单个文件也能直接跑
```

跑之前不需要任何配置：仓库根由 `__file__` 推出，Qt 走 `offscreen`，且**不会真的启动**
桌宠 / QQ / 微信（`AIPET_NO_SPAWN=1`）。
另外 `python -m tool.selftest` 是更快的"体检中的体检"（模块/语法/接线/历史坑），CI 式跑法建议两个都跑。

## 各文件覆盖什么（以及它们防的那个真实案例）

| 文件 | 防的坑（真实案例） |
|---|---|
| `test_config_contracts.py` | **字典重复键**（`qq_config.py` 的 `napcat_token` 写两次 → "自动发现 token"从来没生效，不手填就必然连不上 QQ）；**真值判断**（`weather_enabled()` 是 `!= "false"` → `0/off/no/关` 全算开）；**配置缺键不许 KeyError**（本机 51 键 vs 示例 86 键，`tool/chat.py` 还在导入期下标）；**枚举归一**（`"Local"` 曾让 `api.py` 同文件两处判断相反） |
| `test_bounds.py` | **数值配置**（`screen_interval: 0` → 抓屏线程忙循环 + 不停写临时 PNG；`"abc"` → 后台线程静默死掉）；**pet.json 显示参数**（`scale: 0` → 模型看不见、`head_bottom: 5` → 交互区跑到屏幕外）。其中"**真实角色的值必须原样通过**"这条最容易被忽略 —— 加夹取时我就曾把 `live2d_font_scale` 下界写成 0.40，而真实角色是 0.35 |
| `test_plugin_markup.py` | **插件标记吃台词**：`'【插件:系统信息】内存用了 8.5G。'` 被清成空串、`'前半句【插件:x】后半句'` 只剩"前半句"。同时钉住"解析仍按契约抓同行参数"（别为了保守把参数丢掉） |
| `test_qt_lifecycle.py` | **线程停不掉**（`_agent_worker` 没人能停 → 关掉桌宠后 agent 还能操作电脑最多 600 秒；光 `requestInterruption()` 没用）；**启动秒退没人说**（用户原话"点启动微信秒卡退"：控制台一闪就关、界面一个字都没有） |

## 写新体检的约定

1. **路径无关**：`REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))`，不写死盘符。
2. **可独立运行**：`if __name__` 之外直接跑完就 `sys.exit(0/1)`，输出用 `[OK]/[FAIL]`。
3. **不许有副作用**：不真启动桌宠/QQ/微信、不写用户的 `config.json`（要写就写临时目录）。
4. **断言要有"真实数据不变"那一面**：改夹取/改默认值时，除了"敌意输入被挡住"，
   必须同时断言"**已有的真实数据一个都没被改动**"。
5. **同类修补按出现次数断言**：例如"两处 sleep 循环都要有 `max(1, ...)`"要数 == 2，
   只判"有没有"会漏掉一半（我漏过一次）。
