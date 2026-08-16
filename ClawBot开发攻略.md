# 微信 ClawBot（iLink 协议）开发攻略

> 本文基于 2026-08 的实际开发经历整理：从信息核验、协议逆向阅读、Rust 落地到真机联调。
> 覆盖：协议真相、接口细节、实测坑点、技术选型、从零跑通 checklist、合规边界。

---

## 一、30 秒结论

1. **ClawBot 是微信官方功能**（2026-03-22 发布），本质是微信侧的"开关 + 联系人"，
   底层是腾讯官方的 **iLink 协议**（HTTP/JSON，域名 `ilinkai.weixin.qq.com`）。
2. **不依赖 OpenClaw**。OpenClaw 只是腾讯顺手给出的参考网关；
   任何语言只要实现 iLink 的 HTTP 接口，都能收发微信消息。
3. 个人使用前置条件：微信实名 + 更新到支持 ClawBot 的版本（8.0.70+，
   在「我-设置-插件」里开启）+ 一台常开的机器。
4. **已有凭据重启 = 直接复用原接口**：`bot_token` 和 `base_url` 保存在本地，
   下次启动直接用它长轮询，不需要重新扫码；token 约 24 小时过期。

---

## 二、信息核验结论（哪些是真的，哪些是 AI 编的）

网上（尤其是 AI 生成的）攻略大量混入了幻觉内容。以下是实测核验结果：

| 说法 / 项目 | 结论 | 实际情况 |
|---|---|---|
| iLink 协议、ClawBot 插件 | ✅ 真 | 腾讯官方 2026-03 发布，新闻有 IT之家/光明网/澎湃；域名、端点与官方插件源码一致 |
| OpenClaw | ✅ 真 | 独立开源项目（约 38.7 万 star），**不是腾讯的**；腾讯只写了微信渠道插件 `@tencent-weixin/openclaw-weixin` |
| `openclaw-cn` | ✅ 真但易误解 | 是社区中文版（mf-yang/openclaw-cn），不是腾讯官方安装包 |
| `rustedclaw`（Nitin-100） | ⚠️ 存在但被吹歪 | 真实的通用 AI agent runtime，**和微信毫无关系**；网上说它"内置微信 ClawBot 通道"是编的 |
| ZeroClaw | ⚠️ 存在但被吹歪 | 真实 Rust 项目（约 3.2 万 star），但 README 没有任何微信支持；说它"内置微信通道"是编的 |
| `openclaw-rs`（neul-labs） | ⚠️ 存在但被夸大 | OpenClaw 的社区 Rust 复刻，渠道是 Telegram 等，**没有微信通道**，且 UI 需 Node |
| `weixin-agent`（SpenserCai/weixin-agent-sdk-rs） | ✅ 真 | 纯 iLink 协议 Rust SDK，基于官方插件 2.4.x 移植，crate 名 `weixin-agent`（0.3.x） |
| `wechat-ilink`（tuchg） | ✅ 真 | Rust iLink 客户端，README 自认"非官方、实验性 0.x" |
| `ilink-hub`（jeffkit） | ✅ 真 | iLink 多路复用 Hub，一个微信号接多个 AI 后端 |
| NapCat | ❌ 张冠李戴 | 它是 **QQ（NTQQ）** 协议框架，不是微信方案 |
| `cc-weixin` / `chatgpt-on-wechat` | ✅ 真 | 微信 ↔ Claude Code 桥接器 / 老牌微信机器人框架 |

**教训**：AI 生成的攻略喜欢把"真实存在的项目名"和"微信 ClawBot"缝合在一起。
凡是声称"XX 项目内置微信通道"的地方，都要去仓库 README 里核实。

---

## 三、协议速览

### 3.1 固定请求头

```http
Content-Type: application/json
AuthorizationType: ilink_bot_token
X-WECHAT-UIN: base64(random_uint32)   # 每次请求都变，防重放
Authorization: Bearer <bot_token>     # 登录后才需要
iLink-App-Id: bot
iLink-App-ClientVersion: <channel_version 编码值>
```

登录接口（拿二维码/查状态）**不需要** Authorization 头。

### 3.2 端点清单（官方插件源码核对）

| 端点 | 方法 | 作用 |
|---|---|---|
| `/ilink/bot/get_bot_qrcode?bot_type=3` | GET | 获取登录二维码 |
| `/ilink/bot/get_qrcode_status?qrcode=xxx` | GET | 轮询扫码状态，确认后返回 `bot_token` |
| `/ilink/bot/getupdates` | POST | 长轮询收消息（服务端 hold 约 35s） |
| `/ilink/bot/sendmessage` | POST | 发送文字/图片/文件等 |
| `/ilink/bot/getuploadurl` | POST | 获取 CDN 上传地址（媒体） |
| `/ilink/bot/getconfig` | POST | 获取"正在输入"ticket |
| `/ilink/bot/sendtyping` | POST | 发送"正在输入"状态 |
| `/ilink/bot/msg/notifystart` / `notifystop` | POST | 连接生命周期通知 |

**没有**设置昵称/头像、拉历史消息、群聊管理的端点。

### 3.3 登录流程

```text
get_bot_qrcode → { qrcode, qrcode_img_content }
    ↓ 用户扫码
get_qrcode_status?qrcode=xxx （轮询）
    → status=confirmed 时返回 bot_token / baseurl / ilink_bot_id / ilink_user_id
    → 之后所有请求带 Authorization: Bearer bot_token
```

`qrcode_img_content` **是一段 URL**（形如 `https://liteapp.weixin.qq.com/q/...`），
不是图片数据！需要拿这个 URL 自己生成二维码（`qrcode` crate / 任意二维码库），
直接下载/当图片保存会得到 HTML，导致"图片格式不支持"。

### 3.4 收消息（长轮询）

```json
POST /ilink/bot/getupdates
{
  "get_updates_buf": "<上次返回的游标，首次为空>",
  "base_info": { "channel_version": "2.4.6" }
}
```

返回：

```json
{
  "ret": 0,
  "msgs": [ ... ],
  "get_updates_buf": "<新游标，必须保存，否则重复收消息>",
  "longpolling_timeout_ms": 35000
}
```

消息核心字段：`from_user_id`（`xxx@im.wechat`）、`to_user_id`（`xxx@im.bot`）、
`message_type`（1=用户，2=机器人）、`context_token`、`item_list[]`。

`item_list[].type`：1 文本 / 2 图片 / 3 语音 / 4 文件 / 5 视频
（11/12 为工具进度预留，实测服务端接受但不渲染）。

### 3.5 发消息

```json
POST /ilink/bot/sendmessage
{
  "msg": {
    "from_user_id": "",
    "to_user_id": "<用户的 @im.wechat id>",
    "client_id": "<每次唯一，重复会导致客户端不显示>",
    "message_type": 2,
    "message_state": 2,
    "context_token": "<必须原样回传入站消息的 token>",
    "item_list": [ { "type": 1, "text_item": { "text": "回复内容" } } ]
  },
  "base_info": { "channel_version": "2.4.6" }
}
```

**两个最容易踩的坑**：`context_token` 漏带/复用旧 token → 消息发不出去或串会话；
`client_id` 复用 → 服务端接受但客户端不显示。

### 3.6 媒体文件

全部媒体走 CDN + **AES-128-ECB** 加密：随机生成 key → 加密文件 →
`getuploadurl` 拿预签名地址 → PUT → 发消息时带上 `aes_key`（base64）和 CDN 引用。

---

## 四、实测经验与坑（本项目的血泪）

### 4.1 凭据持久化与"重启监听原接口"

- 扫码确认后，`bot_token` + `base_url` 存到本地文件（本项目：`data/wechat_credentials.json`）。
- **下次启动直接加载凭据，跳过扫码，连原来的接口**——这就是"如果之前注册过再启动就监听原接口"。
- `base_url` 用登录时服务器下发的值（可能因区域有 redirect），不要写死。
- 消息游标 `get_updates_buf` 也要持久化（本项目：`data/sync_buf.txt`），否则重启会重复收到旧消息。

### 4.2 token 过期（errcode -14）

实测日志：

```text
ERROR weixin_agent::monitor::poll_loop: bot token is stale, pausing poll loop
      errcode=-14 pause_min=59
```

- token 有效期约 24 小时，过期后长轮询会收到 `-14`；
- 多数 SDK 会**自动暂停约 1 小时**再重试；
- 想立即恢复：删除 `data/wechat_credentials.json` 重启，重新扫码即可。

### 4.3 发送频率限制

- 实测 **34 秒内连发 18 条会触发反刷**（`ret=-2, prepare failed`），之后分钟级所有发送失败；
- 170 秒发 10 条安全。**长回复合并成一条发，不要拆成大量小消息**。

### 4.4 功能边界

- 官方插件**只支持私聊**（能力元数据未声明群聊），群聊别想了；
- 没有历史消息 API，只能从接入时刻开始收；
- 同一时刻只有一个进程能轮询 `getupdates`；多后端用 `ilink-hub` 做转发。

### 4.5 GUI / 二维码

- 二维码一定要**本地生成**（用 `qrcode` crate 等），不要信任服务端给的"图片"字段；
- 二维码过期会自动刷新，日志会打"二维码已过期，重新获取"；
- GUI 关闭不影响后台机器人，进程继续轮询。

---

## 五、技术选型

### 方案 A：OpenClaw（Node，官方参考，零代码）

```bash
npm install -g openclaw@latest
openclaw onboard --install-daemon
openclaw plugins install "@tencent-weixin/openclaw-weixin"
openclaw config set plugins.entries.openclaw-weixin.enabled true
openclaw gateway restart
openclaw channels login --channel openclaw-weixin   # 扫码
```

优点：最快跑通、有官方维护、人设/白名单/MCP 工具齐全。
缺点：Node 生态、体积大；只想要轻量单 exe 时不合适。

### 方案 B：独立实现（推荐给轻量化场景）

Rust 生态三个真实可用的选择：

| crate | 特点 |
|---|---|
| `weixin-agent` | 协议层最完整，基于官方插件 2.4.x 移植，文档多、有真机实测记录 |
| `wechat-ilink` | stream 风格 API，0.x 实验性，自认非官方 |
| `ilink-hub` | 多后端多路复用，配合上面两个用 |

本项目架构（`D:\WXBot`）：

```text
axum HTTP 服务（/health、/api/chat 调 DeepSeek）
        └── tokio 后台任务
              ├─ 扫码登录（egui GUI 显示二维码）→ 存凭据
              └─ 长轮询 getupdates → MessageHandler
                     └─ 调 DeepSeek → sendmessage 回发
```

核心代码量（不含 GUI）约 200 行，release 单 exe 几 MB。

---

## 六、从零到跑通 checklist

1. 微信更新到支持 ClawBot 的版本，在「我-设置-插件」确认 ClawBot 已开启；
2. 准备模型 API Key（DeepSeek / 任意 OpenAI 兼容接口）；
3. 配置 `.env`：`DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`；
4. `cargo run` → 弹出二维码窗口 → 手机微信扫码授权；
5. 日志出现 `微信 ClawBot 已连接` 后，给「微信ClawBot」联系人发消息验证；
6. 重启验证：直接加载凭据连原接口，无需再扫码；
7. 遇到 `-14`：删除 `data/wechat_credentials.json` 重启重扫。

---

## 七、合规边界（官方条款要点）

- 腾讯定位是**管道**：只做信息收发，不存储对话内容、不提供 AI 服务；
- 腾讯保留控制权：可随时限速、拦截、调整可接入的第三方 AI 服务，甚至终止功能；
- **不要**绕过/破解微信技术保护措施，不要高频群发；
- 不要拿这套 API 做核心业务——它可能被随时变更或终止，要有降级方案；
- 逆向方案（NapCat/wxauto/itchat 之类）不在本文讨论范围，风险自担。

---

## 八、后续可做方向

- 白名单：只允许指定 `from_user_id` 触发，防止陌生人驱动本地工具；
- 媒体收发：图片/文件下载（CDN + AES 解密）后喂给多模态模型；
- 记忆与多轮：把 `context_token` / 对话历史持久化；
- 多账号、多后端：`ilink-hub` 或扩展 `Credentials` 为多份；
- 人设：OpenClaw 的 `identity` / `IDENTITY.md`，或自己维护 system prompt。
