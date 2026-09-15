# -*- coding: utf-8 -*-
"""安装后写入安装目录的《使用教程说明书》内容（安装器与打包脚本共用）。

说明书同时生成两种格式：
- 使用教程说明书.txt   （UTF-8 BOM，记事本直接打开不乱码）
- 使用教程说明书.html  （排版好看，双击用浏览器打开）

文本里 {ROOT} 会替换成实际安装目录。
"""
import os

TITLE = "AIpet 丛雨 AI 桌宠 · 使用教程说明书"

BODY = """============================================================
  {TITLE}
  安装目录：{ROOT}
  版本：{VERSION}     生成时间：{DATE}
============================================================

【一、安装目录里有什么】

  AIpet-Murasame.exe      启动器（图形界面，日常就从它开始）
  run.py / main.py        桌宠本体（由启动器调用，一般不用手动开）
  run_qq.py               QQ 聊天模块（由启动器调用）
  runtime\\venv\\          Python 运行环境（已装好全部依赖，勿删）
  python\\                 便携版 Python（运行环境的基础解释器，勿删）
  场景素材\\               立绘背景场景图（可自己往里放图片）
  pets\\                   角色包：立绘素材、人设、语音参考、记忆
  NapCat.Shell.Windows.OneKey\\   QQ 协议端（扫码登录 QQ 用）
  F5-TTS_Models\\          长文本语音模型（可选功能）
  data\\                   运行数据：记忆、学习、已发内容记录等（可备份）
  face_shibie\\            人脸识别数据
  tmp\\                    临时文件（可随时清空）
  使用教程说明书.txt/.html  本文件

【二、第一次使用（3 步）】

  1) 双击 AIpet-Murasame.exe 打开启动器
     - 首次启动会自动检查依赖（已随包安装，通常几秒内完成；如提示联网失败可忽略）

  2) 填写对话模型 API Key（必须，否则不会说话）
     启动器 → 设置 → 「模型与接口」区：
       · 对话模型：local（本地 ollama）/ deepseek / qwen 三选一
       · 云端模式要把 API Key 填进对应输入框（DeepSeek 或 通义千问控制台申请）
     填好后点「保存」。

  3) 启动
     · 桌宠：点底部「启动 AIpet 桌宠」→ 屏幕上出现丛雨，点她/右键看她说话
     · QQ ：点「启动 QQ AIpet」→ 首次需扫码登录 QQ（见第四节）

【三、桌宠模式怎么玩】

  · 左键点头部    摸头（会害羞/生气）
  · 左键点下半身  打开输入框，打字聊天
  · 右键          弹出菜单：切换服装（制服/睡衣/私服/刀服）、切换立绘类型（a/b）
  · 中键拖动      移动桌宠位置
  · 长按 Shift    切换 Live2D 模式（若装了 Live2D 依赖）
  · 空闲/截图/摄像头触发的自动对话可在 设置 → 桌宠配置 里开关

【四、QQ 聊天怎么用】

  1) 启动器 → 设置 → QQ 配置：填「主主人 QQ 号」（你自己的 QQ，决定谁被叫主人）
  2) 点「启动 QQ AIpet」
     · 首次：会自动拉起 NapCat 并弹出二维码，用手机 QQ 扫码登录
       （登录后请勿在手机上顶号，否则会掉线需要重新扫码）
     · 之后：令牌有效期内自动快速登录
  3) 群里 @它 就会回复；私聊按「私信回复范围」设置决定是否回复
  4) 常用开关（都在 设置 → QQ 配置）：
     · QQ 功能总开关 / 群聊(需@) / 群聊私聊回复范围
     · 单条回复最多字数、单条回复最多发几条消息（超出会拆成 2~3 条短消息，不截断句子）
     · 私信回复范围：允许回复私信总开关 / 回复陌生人 / 回复好友 / 只回复主人
     · 表情包、图片识别、语音识别、离线补拉、活泼模式（主动接话）
  5) 主人专属指令（QQ 里发）：/clear 清空记忆、/switch 切换角色 等
     详见 设置 → QQ 配置 下方的说明

【五、立绘工坊（换装 / 表情 / 场景）】

  启动器 → 🐾 桌宠管理 → 角色卡片上的「🎨 立绘工坊」
  · 立绘类型：a / b 是两套独立素材，服装与表情各自成套、互不串用
  · 服装：制服（校服）/ 寝間着（睡衣）/ 私服（便服）/ 刀服（和装）
  · 表情：51 种（a 套）/ 42 种（b 套），保存后仍随对话情绪自动变化
  · 附加装饰：脸红 / 叹气（b 套为 脸红 / 不满）
  · 背景场景：从「场景素材」文件夹随机或指定某张（自动裁剪放大，无黑边）
  · 「💾 保存为默认立绘」后 QQ 立绘与桌宠立绘同时生效并记住
  · 想加自己的背景：把图片放进 场景素材\\ 文件夹即可（也可在 config.json
    设 portrait_scene_dir 指向别的目录）

  桌宠说话时会闲聊着按概率在两套立绘之间做透明渐变切换（同款服装都有的情况下），
  这是"灵动"效果，也可右键手动切换。

【六、语音相关（可选）】

  · 桌宠语音：需要 GPT-SoVITS 服务（端口 9880）。未启动时桌宠只会说话不发声，
    在控制台会提示"语音服务不可用，跳过"——不影响文字聊天。
  · 长文本语音：需要 F5-TTS 服务（端口 9881）。
  · 关闭语音合成：设置 → 语音合成与识别 → 「启用语音合成」设为 false（可加快回复）。
  · 语音识别（听语音消息）：需要把 Whisper 模型放在 models\\hf 目录
    （安装包未附带，首次启用时程序会尝试自动下载；网络不便可手动放置）。

【七、升级与备份】

  · 升级：把新版安装程序装到同一个目录即可，安装器会保留 data\\、config.json、
    pets\\<角色>\\memory\\ 等个人数据（不会覆盖用户数据）。
  · 备份：直接复制 data\\ 、config.json 、pets\\ 三个位置即可。

【八、常见问题】

  Q1 双击没反应 / 一闪而过？
     → 用命令行进入安装目录执行：runtime\\venv\\Scripts\\python.exe run.py
       查看报错信息；多为缺少 API Key 或端口占用。
  Q2 桌宠能说话但 QQ 不回？
     → 检查：设置 → QQ 配置 → QQ 功能总开关=开；QQ 是否已扫码登录；
       群里是否 @ 了它；私信是否被"私信回复范围"挡住了。
  Q3 提示 NapCat 掉线 / 需要重新扫码？
     → QQ 侧风控会定期让登录失效，重新扫码即可（启动器里有"重新扫码登录"按钮）。
  Q4 语音听起来没有起伏？
     → 语音语气由情感标签决定；启动本地 ollama（端口 11434）后情绪判断更细腻。
       未启动时会按人设默认的「高兴」语气说话。
  Q5 磁盘占用？
     → 本安装约 {SIZE}（含运行环境）；GPT-SoVITS 语音模型需另装（约 20GB）。

【九、卸载】

  · 直接删除整个安装目录即可（不写注册表、不装服务）。
  · 桌面快捷方式可一并删除。

============================================================
  祝你和丛雨玩得开心～ 有问题随时找分享给你的人 :)
============================================================
"""


def render(root: str, version: str = "1.0", size_text: str = "约 5 GB") -> str:
    import datetime
    return (BODY.replace("{TITLE}", TITLE)
                .replace("{ROOT}", root)
                .replace("{VERSION}", version)
                .replace("{SIZE}", size_text)
                .replace("{DATE}", datetime.datetime.now().strftime("%Y-%m-%d %H:%M")))


def render_html(root: str, version: str = "1.0", size_text: str = "约 5 GB") -> str:
    import datetime
    import html
    body = render(root, version, size_text)
    esc = html.escape(body)
    # 让【小节】标题变粗、行内路径更清晰
    lines = []
    for ln in esc.split("\n"):
        s = ln.rstrip()
        if s.startswith("【") or s.startswith("=="):
            lines.append(f'<div class="h">{s}</div>')
        elif s.startswith("  ·") or s.startswith("  -") or s.startswith("   ·"):
            lines.append(f'<div class="li">{s}</div>')
        elif not s:
            lines.append('<div class="sp"></div>')
        else:
            lines.append(f'<div class="p">{s}</div>')
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>{html.escape(TITLE)}</title>
<style>
 body{{background:#1e1e26;color:#e8e8f0;font-family:"Microsoft YaHei",system-ui,sans-serif;
       margin:0;padding:32px 10%;line-height:1.75;font-size:15px}}
 .h{{color:#ffb3c7;font-weight:bold;margin:18px 0 6px}}
 .li{{color:#dfe3ee;padding-left:1.2em;text-indent:-1.2em}}
 .p{{color:#c9cddb;white-space:pre-wrap}}
 .sp{{height:8px}}
 h1{{color:#ff8fb1;font-size:22px}}
 .box{{background:#262631;border-left:4px solid #ff8fb1;border-radius:8px;padding:14px 18px;margin:14px 0}}
</style></head><body>
<h1>{html.escape(TITLE)}</h1>
<div class="box">安装目录：{html.escape(root)}<br>版本 {html.escape(version)} · 生成于 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
{chr(10).join(lines)}
</body></html>"""


def write_manual(install_dir: str, version: str = "1.0", size_text: str = "约 5 GB") -> list:
    """在安装目录写出 txt + html 两份说明书，返回写出的文件路径列表"""
    out = []
    txt = os.path.join(install_dir, "使用教程说明书.txt")
    with open(txt, "w", encoding="utf-8-sig") as f:
        f.write(render(install_dir, version, size_text))
    out.append(txt)
    htm = os.path.join(install_dir, "使用教程说明书.html")
    with open(htm, "w", encoding="utf-8") as f:
        f.write(render_html(install_dir, version, size_text))
    out.append(htm)
    return out
