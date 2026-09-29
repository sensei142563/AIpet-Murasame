# -*- coding: utf-8 -*-
"""一键自检：确认桌宠各个子系统都在、接线没断、数据文件能读写。

用法：
    runtime\\venv\\Scripts\\python.exe -m tool.selftest          # 人看的表格
    runtime\\venv\\Scripts\\python.exe -m tool.selftest --json   # 机器读的 JSON

检查四类（只读为主，只在 tmp/ 与 data/ 写一条探针文件再删掉）：

  1. 模块导入 / 入口语法：该在的模块都在、入口脚本能编译
  2. 关键接线：那些"删掉一行就悄悄坏掉、跑起来看不出来"的钩子（用源码断言钉住）
     —— 包括本项目已经修过的坑：MSVC 自愈顺序、本机代理绕过、立绘稳定/裁切、
        语音响度、性能守卫、云对话直连回落 …
  3. 运行时：config 能读、数据目录能写、角色包装得对（pet.json / 头像 / 2D 素材）
  4. 可选依赖：装了没有（缺了只提示，不算失败）

为什么要有：功能一多，改 A 处很容易把 B 处的接线弄断，而且**运行时不一定立刻暴露**。
跑一遍这个能一眼看出哪块坏了；也可以给启动器做成一个「自检」按钮。
"""
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ── 1. 该能导入的模块 ────────────────────────────────────────────────
CORE_MODULES = (
    "tool.config", "tool.paths", "tool.net_env", "tool.perf_guard", "tool.audio_polish",
    "tool.msvc_runtime", "tool.napcat_version", "tool.portrait_geom", "tool.portrait_outfit",
    "tool.vision_check", "tool.status_snapshot", "tool.plugins",
    "tool.portrait_cli", "tool.generate", "tool.chat", "tool.cloud_API_chat", "tool.api_server",
    "tool.stt", "tool.camera", "tool.face_recognition", "tool.touch_areas",
    "tool.voice_trigger", "tool.time_utils", "tool.weather_utils",
    "pets.pet_registry", "classes.Worker_class", "classes.murasame_class",
    "pcl_launcher.colors", "pcl_launcher.widgets",
)
# 只做语法检查（导入会拉起 torch/Qt 或产生副作用）
COMPILE_ONLY = (
    "run.py", "main.py", "run_launcher.py", "run_qq.py", "run_wechat.py", "api.py",
    "build_launcher.py", "download.py", "download_stt.py", "time_sync_guard.py",
    "tool/pack/build_installer.py", "tool/pack/installer_main.py", "tool/pack/verify_installer.py",
    "longtext/longtext_tts.py", "longtext/f5tts_server.py", "qq/qq_bridge.py",
    "wechat/ilink_client.py",
    # 启动器外壳（12 万字节、全仓库最大）以前**既不在导入表也不在语法表**里，
    # 改坏了要等到真启动才知道；这里补上语法检查，改动后至少不会带语法错上桌。
    "pcl_launcher/silicon_window.py", "pcl_launcher/status_panel.py",
)

# ── 2. 关键接线（源码断言）─────────────────────────────────────────
# (文件, 必须出现的片段, 说明)
WIRING = (
    ("run.py", "from tool.msvc_runtime import", "run.py 缺 MSVC 运行时自愈入口"),
    ("run.py", "import torch as _early_torch", "run.py 缺「提前加载 torch」（否则先 Qt 后 torch 会崩）"),
    ("run.py", "import PyQt5", "run.py 里 Qt 的首次导入不见了"),
    ("run.py", "from tool.net_env import bypass_proxy_for_local", "run.py 缺本机绕过系统代理"),
    ("main.py", "from tool.net_env import bypass_proxy_for_local", "main.py 缺本机绕过系统代理"),
    ("run_launcher.py", "from tool.net_env import bypass_proxy_for_local", "run_launcher.py 缺本机绕过系统代理"),
    ("run_qq.py", "from tool.net_env import bypass_proxy_for_local", "run_qq.py 缺本机绕过系统代理"),
    ("run_wechat.py", "from tool.net_env import bypass_proxy_for_local", "run_wechat.py 缺本机绕过系统代理"),
    ("tool/net_env.py", "def bypass_proxy_for_local", "net_env 少了本机绕过函数"),
    ("tool/net_env.py", "def post_with_direct_fallback", "net_env 少了直连回落函数"),
    ("tool/cloud_API_chat.py", "post_with_direct_fallback", "云对话没走「代理挂了自动直连」"),
    ("tool/generate.py", "_pos_of", "立绘合成少了「图层↔坐标一一对应」表"),
    ("tool/generate.py", "画布就地长大", "立绘合成少了「画布长大而不是裁人」"),
    ("classes/murasame_class.py", "def _stabilize_portrait_canvas", "桌宠少了稳定画布"),
    ("classes/murasame_class.py", "self._stabilize_portrait_canvas(self._scale_portrait_pixmap",
     "稳定画布没接在合成出口上"),
    ("classes/murasame_class.py", "def _pad_pixmap(pm, size, center_x=False)",
     "_pad_pixmap 少了 center_x（过渡会左移）"),
    ("classes/murasame_class.py", "def _perf_tick", "桌宠少了性能守卫 tick"),
    ("classes/murasame_class.py", "set_process_priority(False)", "启动时没把进程优先级降到 BelowNormal"),
    ("tool/chat.py", "polish_wav_bytes", "短语音没做响度统一"),
    ("longtext/longtext_tts.py", "polish_wav_bytes", "长语音没做响度统一"),
    ("pcl_launcher/portrait_studio.py", "stable_canvas_width", "工坊预览没和桌面共用几何"),
    ("tool/portrait_geom.py", "def canvas_size_for", "立绘几何模块少了算法入口"),
    ("build_launcher.py", "AIPET_QT_PATHFIX",
     "打包没注入「非 ASCII 路径」修复（中文目录下会缺整个 PyQt5）"),
    ("tool/pyinstaller_qtfix/sitecustomize.py", "_repair",
     "非 ASCII 路径修复模块缺 _repair（或文件被删）"),
    ("tool/state.py", "def prompt_note", "长期状态模块缺 prompt_note（心情/好感度）"),
    ("tool/chat.py", "prompt_note", "聊天提示词没注入「她此刻的状态」"),
    ("classes/murasame_class.py", "state as _st_touch",
     "触摸没记长期状态（心情/好感度不再变化）"),
    ("tool/agent_bridge.py", "def run_task", "agent 桥接模块缺 run_task"),
    ("classes/murasame_class.py", "def _run_agent_task", "/agent 入口不见了"),
    ("classes/Worker_class.py", "class AgentWorker", "AgentWorker 不见了（/agent 会没反应）"),
    ("tool/habits.py", "def note_active", "习惯模块缺 note_active"),
    ("classes/murasame_class.py", "_habits_timer",
     "习惯采集定时器不见了（「常用软件」统计会停）"),
    ("tool/chat.py", "habits as _hb2", "提示词没注入「主人的习惯」"),
    ("tool/experience.py", "def note_for", "经验模块缺 note_for"),
    ("classes/Worker_class.py", "note_for", "AgentWorker 没查经验（下次不会照做）"),
    ("classes/Worker_class.py", "learn(", "AgentWorker 没记经验（做过的事没沉淀）"),
    ("tool/attention.py", "def should_speak", "开口时机模块缺 should_speak"),
    ("classes/murasame_class.py", "def _attention_ok", "主动搭话没过「开口时机」闸门"),
    ("classes/murasame_class.py", "note_spoke()", "开口后没记一笔（会变话痨）"),
    ("tool/desire.py", "def wants", "动机层缺 wants（她不会自己找事做）"),
    ("classes/murasame_class.py", "_desire_timer", "动机结算定时器不见了（需求不再变化）"),
    ("tool/chat.py", "desire as _dz3", "提示词没注入她的动机"),
    ("tool/care.py", "def check", "主动关怀模块缺 check"),
    ("classes/murasame_class.py", "_care_timer", "关怀定时器不见了（熬夜/久坐不再提醒）"),
    ("main.py", "startup_line", "开机问候不见了（「在一起第 N 天」不说了）"),
    ("tool/reminder.py", "def take_due", "提醒模块缺 take_due"),
    ("classes/murasame_class.py", "_reminder_timer", "提醒轮询不见了（到点不会叫她）"),
    ("tool/chat.py", "reminder as _rm_rules", "本地链路没注入提醒语法（她不会记事）"),
    ("tool/cloud_API_chat.py", "reminder as _rm_rules", "云端链路没注入提醒语法"),
    ("tool/autonomy.py", "def may_propose", "自主行动分档模块缺 may_propose"),
    ("tool/agent_bridge.py", "autonomy as _au", "agent 桥接没读「自主行动分档」政策"),
    ("classes/murasame_class.py", "def _set_autonomy", "自主性切换入口不见了"),
    ("tool/self_learn.py", "def memory_note", "自主学习模块缺 memory_note（记不住东西）"),
    ("classes/murasame_class.py", "_learn_timer", "自主学习定时器不见了"),
    ("classes/murasame_class.py", "def _toggle_learn", "自主学习开关入口不见了"),
    ("tool/chat.py", "self_learn as _sl_note", "本地链路没注入她的长期记忆"),
    ("tool/cloud_API_chat.py", "self_learn as _sl_note", "云端链路没注入她的长期记忆"),
    ("tool/screen_capture.py", "def capture_qimage", "Win32 抓屏模块缺 capture_qimage"),
    ("classes/Worker_class.py", "screen_capture as _sc",
     "截图线程又退回 QScreen.grabWindow 了（后台线程调用会让进程凭空消失）"),
    ("tool/screen_intent.py", "def needs_screen_look", "屏幕意图模块缺 needs_screen_look"),
    ("tool/chat.py", "screen_intent as _si", "本地链路没接「当场看屏幕」"),
    ("tool/cloud_API_chat.py", "screen_intent as _si", "云端链路没接「当场看屏幕」"),
    ("tool/net_env.py", "def port_open",
     "net_env 少了本机端口探测（bind 预检：0ms 判断本机代理在不在）"),
    ("tool/vision_check.py", "def check", "识图自检模块缺 check（识图通不通没人能一眼看出来）"),
    ("tool/vision_check.py", "def tiny_png",
     "识图自检少了「自造测试小图」（拿屏幕截图去测等于把主人屏幕送出去）"),
    ("tool/cloud_API_chat.py", "本次不识别",
     "cloud_vl 没配视觉模型时又返回人话占位了（她会把它当成亲眼所见照着念）"),
    ("tool/camera.py", "本次不识别",
     "摄像头识图又把错误提示当描述返回了（她会照着念）"),
    ("main.py", "from tool import screen_capture as _sc",
     "截图任务又退回 QScreen.grabWindow（后台线程里调用会让进程凭空消失）"),
    ("tool/status_snapshot.py", "def snapshot",
     "状态快照模块缺 snapshot（「她的状态」没有数据来源）"),
    ("tool/status_snapshot.py", "def as_text",
     "状态快照模块缺 as_text（出问题时没法一键复制成文字）"),
    ("classes/status_window.py", "def show_status_window",
     "状态窗缺入口（右键「她的状态」会没反应）"),
    ("classes/murasame_class.py", "_show_status_window",
     "右键菜单没挂「她的状态」入口"),
    ("tool/config.py", "def set_key",
     "config 少了安全的单键写入（整份 dump 会把示例占位值当成主人的设置落盘）"),
    ("tool/plugins.py", "def handle_reply",
     "插件框架缺 handle_reply（回复里的插件标记没人处理）"),
    ("tool/plugins.py", "def run_one", "插件框架缺 run_one"),
    ("tool/plugins.py", "def manifest_dirs",
     "插件清单会漏掉只有 plugin.json 的目录（主人会以为插件丢了）"),
    ("tool/chat.py", "plugins as _pl_rules", "本地链路没注入插件能力"),
    ("tool/cloud_API_chat.py", "plugins as _pl_rules", "云端链路没注入插件能力"),
    ("classes/murasame_class.py", "_toggle_plugins", "右键菜单没挂插件总开关"),
    ("tool/web_search.py", "def needs_search",
     "联网搜索缺意图判断（问「最新/多少钱」也不会去查）"),
    ("tool/web_search.py", "def parse_bing",
     "联网搜索缺 Bing 解析（外网结果取不到）"),
    ("tool/chat.py", "web_search as _ws", "本地链路没接「不确定就上网查」"),
    ("tool/cloud_API_chat.py", "web_search as _ws", "云端链路没接「不确定就上网查」"),
    ("classes/murasame_class.py", "_toggle_search", "右键菜单没挂联网搜索开关"),
    # ── 配置路径（cwd 不是程序目录时会读错/写错配置，§22 记过 ──
    ("tool/config.py", "def resolve_path",
     "配置路径的中央解析没了（cwd 不对就会读错配置：静默退回示例默认值）"),
    ("tool/config.py", "p = resolve_path(path)",
     "get_config / set_key 没走中央解析（读的和写的可能不是同一份配置）"),
    ("tool/config.py", "under_app = os.path.join(APP_DIR, path.lstrip",
     "带子目录的相对路径没保留结构（会被拍平成程序目录下的同名文件）"),
    ("main.py", '_set_key("./config.json", "live2d_probe_ok"',
     "Live2D 探测结果又用相对路径整份写回了（会写到别的 cwd）"),
    ("classes/murasame_class.py", 'set_key("./config.json", "screen_type"',
     "开屏幕开关的保存没走 set_key（相对路径 + 整份写回）"),
    ("classes/murasame_class.py", 'set_key("./config.json", "camera_enabled"',
     "摄像头开关的保存没走 set_key"),
    ("classes/murasame_class.py", 'set_key("./config.json", "portrait_auto_switch"',
     "自动切换立绘的保存没走 set_key"),
    ("pcl_launcher/status_panel.py", "class PCLStatusPanel",
     "启动器缺「状态」页面板（前端看不到她的状态）"),
    ("pcl_launcher/status_panel.py", "def _switches",
     "启动器状态页没列新增开关（本次更新的东西前端还是找不到）"),
    ("pcl_launcher/silicon_window.py",
     '_host_page("status", _mk("pcl_launcher.status_panel", "PCLStatusPanel"))',
     "启动器没登记「状态」页（导航点了会显示错误页）"),
    ("pcl_launcher/silicon_window.py", '("status",',
     "启动器左栏导航没有「状态」入口"),
    # ── 入口脚本不许"被 import 就启动程序"（实测把真桌宠拉起来过，见交接文档 §27.1）──
    ("run.py", 'if __name__ != "__main__":',
     "run.py 的换解释器缺 import 守卫（被 import 会拉起一个真解释器 → 真桌宠自己跑起来）"),
    # ── 插件标记：参数正则与"清理要念的话"的正则必须分开（合并会吃掉她自己的话）──
    ("tool/plugins.py", "_MARK_ARG_RE",
     "插件标记的参数正则没了/又和清理正则合并（实测会把标记后面她的话一起删掉）"),
    ("tool/plugins.py", "_MARK_ARG_RE.fullmatch(line.strip())",
     "清理不复用 fullmatch 判据了（分不清'整行就是标记+参数'与'她把话写在标记后面'）"),
    # ── NapCat token：显式配置优先、没配才自动发现（曾经被同名重复键静默覆盖，见 §27.4）──
    ("qq/qq_config.py", "or get_qq_token(_ws)",
     "NapCat token 的自动发现又被挤掉了（口径应是：显式配置优先，没配才自动发现）"),
    ("qq/qq_config.py", '"http_url"',
     "QQ 配置里 http_url 没了（启动器的「打开 WebUI」会失效）"),
    # ── 真值判断统一走权威实现 as_bool（1/true/yes/y/on/开/开启 → 真）──
    #    抄出来的版本普遍更窄（只认小写 "true"）或方向写反，见交接文档 §27.5
    ("qq/qq_config.py", "from tool.config import as_bool",
     "QQ 配置的真值判断没走权威实现（用户写 1/on/开 会被当成关）"),
    ("tool/weather_utils.py", "as_bool(_read_cfg()",
     "天气开关又变成反向判断了（只有恰好写 false 才算关：0/off/no/关 全算开）"),
    ("pcl_launcher/plugins_panel.py", "from tool.config import as_bool",
     "启动器插件页的真值判断没走权威实现"),
    ("main.py", 'as_bool(CONFIG.get("voice_trigger"), False)',
     "语音触发开关又变成大小写敏感判断了（写 True 会被当成关）"),
    # ── 数值型配置：读不懂用默认、越界夹住（写 0/负数会让"间隔"变忙循环，见 §27.6）──
    ("tool/config.py", "def num(",
     "配置数值的兜底/夹取实现没了（间隔写 0 会让抓屏/抓帧变忙循环）"),
    ("classes/Worker_class.py", "num(interval_sec,",
     "worker 的间隔没走 num() 夹取（0/负数 → run() 里一次都不睡）"),
    ("classes/Worker_class.py", 'get_config("./config.json").get("screen_index")',
     "screen_index 又用直接下标了（缺键 KeyError、越界在截图线程里静默死掉）"),
    ("classes/murasame_class.py", 'num(CONFIG.get("camera_interval")',
     "摄像头间隔没走 num() 夹取"),
    ("classes/murasame_class.py", 'num(CONFIG.get("screen_interval")',
     "截图间隔没走 num() 夹取（原来还是直接下标，缺键就 KeyError）"),
    # ── 显示参数（pet.json）：离谱值要夹，但**真实角色的值一个都不能被改动**（见 §27.7）──
    ("pets/pet_registry.py", '"live2d_font_scale": (0.10, 3.00)',
     "字号夹取下界被改大了（真实角色 pet.json 里就是 0.35，夹到 0.40 = 改了角色的显示）"),
    ("pets/pet_registry.py", "num(m.get(key, default), default, lo, hi)",
     "显示参数的夹取没走 num()（读得懂但离谱的值会原样传下去：模型看不见/交互区跑到屏外）"),
    ("pcl_launcher/live2d_preview.py", 'num(disp.get("scale"), 1.0, 0.30, 2.00)',
     "Live2D 预览窗的缩放没夹（原来连 try 都没有，值写坏就抛异常、窗口打不开）"),
    ("classes/murasame_class.py", 'num(_pet_cfg.get("model", {}).get("portrait_height_ratio")',
     "立绘占屏比没夹（写 0 → 桌宠高度 0，直接看不见）"),
    # ── 配置"存在但缺键"时不许 KeyError（老配置/手删键/精简配置，见 §27.8）──
    ("tool/config.py", "_notice_missing_keys",
     "配置缺键时不再给可读提示（用户只会看到 KeyError + 一大段 traceback）"),
    ("tool/chat.py", '_api = _cfg0.get("local_api") or {}',
     "tool.chat 的双层下标又回来了（这几行在**模块导入期**执行 → 缺键 KeyError → 桌宠起不来）"),
    ("classes/murasame_class.py", 'enum_of(CONFIG.get("model_type")',
     "model_type 又裸比了（同一进程里两处判断会不一致）"),
    ("main.py", 'CONFIG.get("screen_index", 0)',
     "screen_index 又用下标访问了"),
    # ── 枚举值（model_type / tts_type / screen_type）：读取点必须归一（见 §27.9）──
    ("tool/config.py", "def enum_of(",
     "枚举值的归一/提示实现没了（写 Local/LOCAL/尾随空格会被当成另一条分支）"),
    ("classes/murasame_class.py", 'enum_of(CONFIG.get("model_type")',
     "model_type 又裸比了（同一进程里两处判断会不一致）"),
    ("classes/murasame_class.py", 'enum_of(CONFIG.get("screen_type")',
     "screen_type 没归一（写 True 会被当成关）"),
    ("run.py", 'enum_of(cfg.get("tts_type")',
     "tts_type 没归一（写 LOCAL 会走错分支）"),
    ("tool/chat.py", "from tool.config import enum_of, get_config",
     "tool.chat 没导入 enum_of（用了就是导入期 NameError）"),
    ("api.py", 'enum_of(get_config("./config.json").get("model_type")',
     "api.py 的 model_type 没归一（同一个文件里两处判断会相反）"),
    # ── 后台线程要停得掉：agent 会以主人身份操作电脑，退出时必须收干净（见 §27.10）──
    ("tool/agent_bridge.py", "should_stop=None",
     "run_task 不支持取消（关掉桌宠后外部 agent 会继续操作电脑到超时为止）"),
    ("tool/agent_bridge.py", "if cancelled:",
     "取消分支没了（should_stop 为真时要立刻杀进程树收手）"),
    ("classes/Worker_class.py", "should_stop=lambda: self.isInterruptionRequested()",
     "AgentWorker 没把线程中断接到取消上"),
    ("classes/murasame_class.py", "def stop_all_workers",
     "退出前的统一收尾没了（线程还活着就退出 → QThread 告警/abort）"),
    ("main.py", "aboutToQuit.connect(lambda: pet.stop_all_workers())",
     "退出钩子没挂上（没人停后台线程）"),
    ("classes/murasame_class.py", "我还在做上一件事",
     "agent 又允许同时跑多个了（两个 agent 同时在动主人的电脑）"),
)
# 绝不能出现的（历史坑，回来就是 bug 复发）—— **正则**，只扫非注释行：
#   注释里写着"原来写死了 infos[57:65]"是对的（解释历史），不能算复发（自测自己踩过这个误报）
FORBIDDEN = (
    (r"infos\[57:65\]", "立绘合成又把丛雨索引行号写死了（会裁人）"),
    (r"infos\[47:51\]", "立绘合成又把丛雨索引行号写死了（会裁人）"),
    # ⚠ 2026-09-29 自己踩的：给 tool/paths.py 也加了 `if __name__ != "__main__":` 守卫，
    #   结果 (a) 该模块的 __name__ 永远是 "tool.paths" → 把 run_launcher 的**正当自切换**
    #   一起禁掉（test_source_startup 当场抓到）；(b) 文件里出现 "__main__" 字样 →
    #   被 test_entry_console_guard 误判成"入口脚本且缺编码守卫"。
    #   入口脚本自己的那份守卫在 run.py（WIRING 里有断言），这里钉住 paths.py **不许加**。
    (r'if __name__ != "__main__":',
     "tool/paths.py 又加了 name 守卫（它的 __name__ 永远是 tool.paths，会禁掉正当自切换）"),
)
FORBIDDEN_FILES = ("tool/generate.py", "tool/paths.py")


def _src(rel: str) -> str:
    """读仓库里某个文件的源码（检查器与被检查对象分开，便于测试替换）"""
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        return ""
    return io.open(p, encoding="utf-8", errors="replace").read()


def _code_lines(rel: str):
    """只取**非注释、非空**的代码行（注释里的历史说明不算问题）"""
    out = []
    for ln in _src(rel).splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s)
    return out


def _try(fn, name, results):
    try:
        ok, info = fn()
    except Exception as e:
        ok, info = False, "%s: %s" % (type(e).__name__, e)
    results.append((name, bool(ok), str(info)[:90]))
    return ok


def check_modules(results):
    bad = []
    for m in CORE_MODULES:
        try:
            __import__(m)
        except Exception as e:
            bad.append("%s(%s)" % (m, type(e).__name__))
    results.append(("核心模块导入（%d 个）" % len(CORE_MODULES), not bad,
                    "全部通过" if not bad else "失败: " + ", ".join(bad)))
    # ⚠ 不要用 py_compile + cfile=os.devnull：Windows 上 "nul" 会被当普通文件，
    #   报 FileExistsError（自测自己踩过）。直接在内存里 compile()，还不会产生 .pyc 垃圾。
    bad2 = []
    for rel in COMPILE_ONLY:
        p = os.path.join(ROOT, rel)
        if not os.path.isfile(p):
            bad2.append("%s(缺失)" % rel)
            continue
        try:
            src = io.open(p, encoding="utf-8", errors="replace").read()
            compile(src, p, "exec")
        except Exception as e:
            bad2.append("%s(%s)" % (rel, type(e).__name__))
    results.append(("入口/重模块语法（%d 个）" % len(COMPILE_ONLY), not bad2,
                    "全部通过" if not bad2 else "失败: " + ", ".join(bad2)))


def check_wiring(results):
    missing = []
    for rel, needle, why in WIRING:
        if needle not in _src(rel):
            missing.append("%s ← %s" % (why, rel))
    results.append(("关键接线（%d 处）" % len(WIRING), not missing,
                    "全部通过" if not missing else "断了 %d 处: %s"
                    % (len(missing), " | ".join(missing[:3]))))
    bad = []
    for pat, why in FORBIDDEN:
        rx = re.compile(pat)
        for rel in FORBIDDEN_FILES:
            hit = next((ln for ln in _code_lines(rel) if rx.search(ln)), None)
            if hit:
                bad.append("%s（%s: %s）" % (why, rel, hit[:44]))
    results.append(("历史坑未复发（%d 条）" % len(FORBIDDEN), not bad,
                    "干净" if not bad else "复发: " + " | ".join(bad)))


def check_runtime(results):
    # config：能读（读不到会自动回落到 config.example.json，也算通过但要说明）
    def _cfg():
        from tool.config import get_config
        c = get_config(os.path.join(ROOT, "config.json"))
        if not isinstance(c, dict) or not c:
            return False, "读不到配置"
        from pets.pet_registry import get_active_pet_id
        return True, "角色=%s，键 %d 个" % (get_active_pet_id(), len(c))
    _try(_cfg, "config 可读", results)

    # 数据目录可写（写一条探针再删）
    def _writable():
        import tempfile
        done = []
        for d in ("tmp", "data"):
            p = os.path.join(ROOT, d)
            os.makedirs(p, exist_ok=True)
            fd, f = tempfile.mkstemp(prefix=".selftest_", dir=p)
            os.close(fd)
            os.remove(f)
            done.append(d)
        return True, "可写: " + ", ".join(done)
    _try(_writable, "数据目录可写（tmp/data）", results)

    # 角色包：pet_list 可解析、active 角色存在、pet.json 与头像都在
    def _pets():
        pj = os.path.join(ROOT, "pets", "pet_list.json")
        data = json.load(io.open(pj, encoding="utf-8"))
        ids = [p.get("id") for p in data.get("pets", [])]
        act = str(data.get("active") or "")
        if act not in ids:
            return False, "active=%r 不在列表 %s 里" % (act, ids)
        bad = []
        for pid in ids:
            d = os.path.join(ROOT, "pets", pid)
            pj2 = os.path.join(d, "pet.json")
            if not os.path.isfile(pj2):
                bad.append("%s 缺 pet.json" % pid)
                continue
            cfg = json.load(io.open(pj2, encoding="utf-8"))
            av = cfg.get("avatar") or ""
            if av and not os.path.isfile(os.path.join(d, av)):
                bad.append("%s 头像缺失(%s)" % (pid, av))
        return (not bad), ("角色 %d 个，active=%s%s" % (len(ids), act,
                                                     "" if not bad else "；问题: " + ", ".join(bad)))
    _try(_pets, "角色包完整（pet_list / pet.json / 头像）", results)

    # 立绘几何：当前角色有 2D 素材时应该算得出画布
    def _geom():
        from pets.pet_registry import get_active_pet_id, has_fgimages
        pid = get_active_pet_id()
        if not has_fgimages(pid):
            return True, "%s 没有 2D 素材（跳过）" % pid
        from tool.portrait_geom import stable_canvas_width
        w = stable_canvas_width(pid, "a", 900)
        return (w > 0), ("%s a 套 900px → 宽 %d" % (pid, w))
    _try(_geom, "立绘几何可算", results)


def check_optional(results):
    mods = ("numpy", "requests", "cv2", "PyQt5", "torch", "sounddevice", "soundfile",
            "websocket", "Crypto", "qrcode", "pilk", "live2d", "OpenGL")
    import importlib.util
    missing = [m for m in mods if importlib.util.find_spec(m) is None]
    results.append(("可选依赖（%d 个）" % len(mods), True,
                    "全部在" if not missing else "缺: " + ", ".join(missing)
                    + "（对应功能不可用，不算失败）"))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in argv
    results = []
    sys.path.insert(0, ROOT)
    os.chdir(ROOT)
    if as_json:
        # ⚠ JSON 消费者的 stdout 必须是**干净**的：被导入的模块会自己打印横幅
        #   （实测 pygame 会往 stdout 打两行）→ 检查阶段先把 stdout 收走，最后只输出 JSON。
        import contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            check_modules(results)
            check_wiring(results)
            check_runtime(results)
            check_optional(results)
    else:
        check_modules(results)
        check_wiring(results)
        check_runtime(results)
        check_optional(results)
    fails = [(n, i) for n, ok, i in results if not ok]
    if as_json:
        print(json.dumps({"ok": not fails, "checks": [
            {"name": n, "ok": ok, "info": i} for n, ok, i in results]},
            ensure_ascii=False, indent=2))
    else:
        print("=== AIpet 自检（%d 项）===" % len(results))
        for n, ok, info in results:
            print("  %s %-28s %s" % ("✓" if ok else "✗", n, info))
        print("")
        if fails:
            print("失败 %d 项：" % len(fails))
            for n, i in fails:
                print("  ✗ %s —— %s" % (n, i))
        else:
            print("全部通过：模块/接线/运行时/依赖四项都正常（%d 项）" % len(results))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
