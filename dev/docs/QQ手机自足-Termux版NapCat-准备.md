# 手机自足（方案 A）：在手机里跑 NapCat，App 直连本机 OneBot11

> 用户 2026-10-11 选定方案 A。目标：**不开电脑**，手机自己收发 QQ（仅小号）。
> 结论依据见调研：NapCat 是"官方 QQ 客户端 + 注入层"，官方安装器**自带 Termux 脚本**
> （Debian + rootless NapCat + LinuxQQ arm64），协议维护交给 NapCat，我们只当 OneBot11 客户端。
> **自研协议不划算**（go-cqhttp 官方声明无力维护、mirai 停更、MiraiAndroid/Seiko 已归档）。

## 一、App 侧已经准备好的（本轮代码）

| 项 | 状态 |
|---|---|
| 本机 OneBot11 客户端 | ✅ 新增 `bot/chat/OneBotLocal.kt`，用 OkHttp WebSocket（**不加新依赖**），默认连 `ws://127.0.0.1:3001` |
| 冷启动自动尝试连接 | ✅ `MainActivity` 启动时 `OneBotLocal.start(app)`（连不上静默失败，不影响其它功能）|
| 数据源 | ✅ `QqBackend`：**本机 OneBot11 优先，电脑 api.py 兜底**；两者产出**同一套 JSON 形状**，界面无需区分 |
| 界面 | ✅ 首页「QQ chatter」卡 / QQ 面板显示「**数据源**」行；本机连上时显示"本机 NapCat(OneBot11 …)" |
| 发送 | ✅ 本机直连时**直接发**（`send_msg`）；走电脑时投递旧队列 |
| 日志 | ✅ `files/onebot_local.log`（含外置目录同名文件，adb 可 pull）——**这是最主要的验收通道** |
| 会话落盘 | ✅ 本机会话缓存到 `files/onebot_local.json`（重启不丢，每会话最多 200 条 / 最多 40 会话）|

## 二、手机侧要做的（照着走）

一键脚本：`dev/scripts/termux_napcat_setup.sh`（把步骤固化成可粘贴的片段）。

1. **装 ZeroTermux**（或 F-Droid 版 Termux；应用商店版本过旧）。
2. 跑官方安装脚本：
   ```bash
   curl -o napcat.termux.sh https://nclatest.znin.net/NapNeko/NapCat-Installer/main/script/install.termux.sh
   bash napcat.termux.sh
   ```
   （来源：<https://github.com/NapNeko/NapCat-Installer> 的 `script/install.termux.sh`）
3. 启动（每次都要）：
   ```bash
   screen -dmS napcat bash -c 'proot-distro login napcat -- bash -c "xvfb-run -a /root/Napcat/opt/QQ/qq --no-sandbox"'
   ```
4. 手机浏览器开 **`http://localhost:6099`**（NapCat WebUI，token 在容器内
   `…/napcat/config/webui.json`）→ 用**小号**登录。
   *若小号就在本机、没法同屏扫码*：**把二维码截图 → 小号 QQ 扫一扫 → 右上角相册 → 选截图**。
5. **网络配置 → 新建 WebSocket 服务器**：`host=127.0.0.1`、`port=3001`、类型=**正向 WS**、协议 OneBot11。
   对应文件 `…/napcat/config/onebot11_<QQ号>.json` 的 `network.websocketServers` —— 与桌面端
   `qq/qq_bridge.py` 里的报错提示指向同一段配置，格式一致。
6. **保活**（这是本方案唯一硬骨头，不是协议问题）：
   - 允许后台活动、关闭电池优化、把 Termux/ZeroTermux 加入"不锁屏/常驻"白名单；
   - 保持一条常驻通知别清掉；必要时用浮窗/前台运行；
   - 第三方教程的经验值：**≥2GB 运行内存、≥3GB 可用存储**（非官方，未实测）。

## 三、验收（手机侧做完后，我这边这样验）

1. `adb shell cat /sdcard/Android/data/com.aipet.murasame/files/onebot_local.log`
   应出现：`正在连接 ws://127.0.0.1:3001` → `已连上本机 NapCat` → `登录信息：<昵称>(<QQ号>)`。
2. App 首页「QQ chatter」卡：状态行应显示 **NapCat：在线 ✓**，数据源显示 **本机 NapCat(OneBot11 …)**。
3. 用小号给这个号发一条 → 卡片会话列表里出现该会话与消息。
4. 在卡片里回一条 → 小号应收到（本机直连是**立即发**，不经队列）。

## 四、风险与合规（有出处的事实）

- **不要**在同一账号上"多端 + 模块化环境"：NapCat 官方安全文档建议避免同一 IP/设备同时登录
  bot 账号与常用账号；社区（LLOneBot 维护者）明确 "bot 账号最好不要在手机登录"、
  "手机上有模块之类的也会被检测到导致全端下线"。
- 因此：**只用小号**，且**这个手机不要日常登录该小号**（本机登录是给 NapCat 用的）。
- 掉线可尝试把 `o3Hook` 设为 0（NapCat 官方安全文档提供的缓解手段）。
- 反直觉但有利的一点：手机同时是 NapCat 与扫码端 ⇒ **天然同 IP**，少一类风控。

## 五、未验证（如实标注）

1. NapCat Termux 脚本在 **Android 14/15/16** 上的兼容性与保活表现：未实测。
2. proot 内 LinuxQQ arm64 的**实际常驻内存/耗电**：只有第三方博客口径（≥2GB RAM），无实测。
3. **同一台手机**上"截图二维码→相册扫码"是否顺畅：未实测（理论可行，QQ 支持相册取码）。
4. 30 小时以上长时间挂机的稳定性（Doze 是否最终杀掉）：未实测。
5. 本机 OneBot11 客户端与 NapCat 的**全部**消息类型（图片/语音/表情）解析：当前只解析
   文本 + [图片]/[表情]/[语音] 占位，**未在真机验证**。
6. 具体 NapCat 版本（调研时最新 v4.18.37 / 2026-10-10）的配置字段是否有变动：未逐项核对。
