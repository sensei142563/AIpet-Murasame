import json
import os
import time
import textwrap
import wave
import ctypes
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtCore import Qt, QRect
from PyQt5.QtGui import QGuiApplication, QImage
from PyQt5.QtGui import QPainter, QColor, QFont, QPixmap, QFontMetrics
from PyQt5.QtMultimedia import QSound
from PyQt5.QtWidgets import QLabel

from classes.Worker_class import ScreenWorker
from classes.Worker_class import qwen3_lora_Worker, cloud_API_Worker, CameraWorker
from tool.config import get_config
from tool.chat import ollama_qwen25vl
from tool.cloud_API_chat import cloud_vl
from tool.generate import generate_fgimage
from longtext.longtext_manager import LongTextManager
from longtext.longtext_tts import LongTextVoice, LongTextTTSManager
from longtext.longtext_history import load_long_history, save_long_history, sync_to_short_history, clear_long_history, demote_high_priority


def wrap_text(s, width=10):
    return "\n".join(
        textwrap.wrap(
            s,
            width=width,
            break_long_words=True,
            break_on_hyphens=False,
        )
    )


CONFIG = get_config("./config.json")
portrait_type = CONFIG["portrait"]
model_type = CONFIG["model_type"]
screen_type = CONFIG.get("screen_type", "true")
camera_type = CONFIG.get("camera_enabled", "false")
camera_interval = CONFIG.get("camera_interval", 300)
DEFAULT_PORTRAIT_SCREEN_RATIO = CONFIG["DEFAULT_PORTRAIT_SCREEN_RATIO"]
IDLE_THINKING_MINUTES = CONFIG.get("idle_thinking_minutes")
IDLE_AWAY_MINUTES = CONFIG.get("idle_away_minutes")


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("dwTime", ctypes.c_uint),
    ]


def get_idle_seconds() -> float:
    """基于 Windows GetLastInputInfo 计算全局空闲时间（秒）"""
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
    except AttributeError:
        # 非 Windows 平台直接认为无空闲
        return 0.0

    last_input_info = LASTINPUTINFO()
    last_input_info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not user32.GetLastInputInfo(ctypes.byref(last_input_info)):
        return 0.0

    tick_count = kernel32.GetTickCount()
    idle_ms = tick_count - last_input_info.dwTime
    if idle_ms < 0:
        idle_ms = 0
    return idle_ms / 1000.0


class Murasame(QLabel):
    # 跨线程安全触发对话：worker 线程（截图/摄像头）只发信号，
    # 主线程槽函数才执行 start_thread（内部含大量 Qt GUI 操作，必须在主线程）
    _request_dialog = pyqtSignal(str, str, bool)

    # 初始
    def __init__(self):
        super().__init__()
        self._request_dialog.connect(self.start_thread)
        # 文字
        self.full_text = ""  # 打字机效果用到的整体字符串
        from pets.pet_registry import get_pet_config, get_fgimages_dir
        _pet_cfg = get_pet_config()
        self.pet_name = _pet_cfg.get("name", "丛雨")  # 宠物名称（从角色包读取）
        self._pet_display_name = _pet_cfg.get("display_name", self.pet_name)
        self._fgimages_prefix = _pet_cfg.get("model", {}).get("fgimages_prefix", "")
        self._fgimages_sets = _pet_cfg.get("model", {}).get("fgimages_sets", [])
        # 默认显示方式（pet.json model.default：2d / live2d）
        self._default_display = str(_pet_cfg.get("model", {}).get("default", "2d") or "2d").lower()
        # 是否有 2D 立绘图层面板（纯 Live2D 角色没有 fgimages → 跳过 2D 立绘生成）
        self._has_fgimages = bool(get_fgimages_dir())
        # Live2D 文字层字号缩放（pet.json model.live2d_font_scale）
        try:
            self._live2d_font_scale = float(_pet_cfg.get("model", {}).get("live2d_font_scale", 1.0) or 1.0)
        except (TypeError, ValueError):
            self._live2d_font_scale = 1.0
        # 文字区域位置（pet.json interaction.text_area：top 上半身 / bottom 下半身）
        self._text_area_bottom = str(_pet_cfg.get("interaction", {}).get("text_area", "top")).lower() == "bottom"
        # 文本框位置微调（pet.json interaction.text_offset_x/y，Shift+方向键调整，F5 保存）
        try:
            self._text_offset_x = int(_pet_cfg.get("interaction", {}).get("text_offset_x", 0) or 0)
            self._text_offset_y = int(_pet_cfg.get("interaction", {}).get("text_offset_y", 0) or 0)
        except (TypeError, ValueError):
            self._text_offset_x = 0
            self._text_offset_y = 0
        self.user_name = CONFIG["user_name"]  # 用户名字
        self.display_text = ""  # 将要展示的文字
        self._font_family = "思源黑体Bold.otf"
        self._base_font_size = 40
        self._base_text_x_offset = 140  # 文本框左右偏移量
        self._base_text_y_offset = -100  # 文本框上下偏移量
        self._base_border_size = 2
        self._current_scale = 1.0
        self.border_size = self._base_border_size
        self._update_text_scaling()

        # 创建打字机效果的计时器
        self.typing_timer = QTimer(self)
        self.typing_speed = 40
        self.typing_timer.setInterval(self.typing_speed)  # 每 40 毫秒触发一次（打字机速度）

        # 输入
        self.input_mode = False  # 是否处于输入模式
        self.input_buffer = ""  # 输入模式下已确认的文字
        self.preedit_text = ""  # 输入模式下的拼音/候选
        self.setFocusPolicy(Qt.StrongFocus)  # 接收键盘焦点
        self.setAttribute(Qt.WA_InputMethodEnabled, True)  # 开启输入法支持
        self.setFocus()
        # 鼠标事件
        self.touch_head = False  # 是否正在摸头（左键点头部后进入判定）
        self.head_press_x = None  # 按下头部时的横坐标，用来判断是否“晃动”
        self.offset = None  # 中键拖动时记录的偏移量

        # AI 对话
        self.history = []
        self.portrait_history = []
        self.screen_history = ["", ""]
        # 短文本记忆按角色分仓（修复多角色共用记忆导致人设串味，如诺瓦说出"神社"）
        from pets.pet_registry import get_memory_dir
        self.history_file = Path(get_memory_dir()) / "history.json"
        self._load_history()

        # 初始立绘（从角色包 portrait_prompts.json 读取默认图层）
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )  # 去掉标题栏和边框，窗口总在最前面，任务栏不单独显示图标
        self.setAttribute(Qt.WA_TranslucentBackground, True)  # 让整个窗口支持透明区域
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)  # Live2D 文字层显示时不抢键盘焦点
        from pets.pet_registry import get_portrait_prompts
        _pp = get_portrait_prompts()
        _set_pp = _pp.get("sets", {}).get(portrait_type, {})
        self.first_portrait = _set_pp.get("first_portrait", [1715, 1306, 1719])
        self.portrait_target = f"{self._fgimages_prefix}{portrait_type}" if self._fgimages_prefix else f"ムラサメ{portrait_type}"
        # 纯 Live2D 角色（无 fgimages 立绘图层面板）跳过 2D 立绘生成，避免空画布
        if self._has_fgimages:
            self.update_portrait(self.portrait_target, self.first_portrait)
        if not self.portrait_history:
            self.portrait_history.append(("", str(self.first_portrait)))
            self._save_history()

        # 对话锁：自动触发的对话（屏幕/摄像头/空闲）在已有对话时跳过
        self._talking = False

        # 线程
        self.worker = None
        self.interval = CONFIG["screen_interval"]
        self._screenshot_worker = None
        self._screenshot_executor = ThreadPoolExecutor(
            max_workers=1
        )  # 处理屏幕截图网络调用
        self.force_stop = False  # 是否处于强制中断状态

        # 常开截图线程
        if screen_type == "true":
            QTimer.singleShot(
                1000, lambda: self.start_screenshot_worker(interval=self.interval)
            )

        # 常开摄像头线程（类比截图，受 camera_enabled 控制）
        self._camera_worker = None
        self._camera_executor = ThreadPoolExecutor(max_workers=1)
        if camera_type == "true":
            camera_id = CONFIG.get("camera_id", 0)
            QTimer.singleShot(
                1500, lambda: self.start_camera_worker(interval=camera_interval, camera_id=camera_id)
            )

        # 空闲检测相关
        self.idle_thinking_triggered = False
        self.idle_away_triggered = False
        self.idle_thinking_seconds = max(0, IDLE_THINKING_MINUTES) * 60
        self.idle_away_seconds = max(
            self.idle_thinking_seconds + 60,
            max(0, IDLE_AWAY_MINUTES) * 60,
        )

        # 记录离开屏幕的时间，用于回来后问候
        self.away_trigger_time = None

        self.idle_timer = QTimer(self)
        self.idle_timer.setInterval(1000)
        self.idle_timer.timeout.connect(self.check_idle_state)
        self.idle_timer.start()

        # 勿扰模式：开启后关闭截图与空闲检测，并禁止主动搭话
        self._dnd_enabled = False

        # Live2D 模式相关
        self._live2d_widget = None
        self._live2d_mode = False
        self._saved_portrait_info = None
        self._live2d_initialized = False
        # Live2D 文字层（透明覆盖层）：常显 + 点击穿透，行为对齐 2D
        self._overlay_visible = False
        self._overlay_click_through = False

        # ===== 长文本模式 =====
        # config 总开关（关闭后禁止开启长文本模式）
        self.long_text_mode_enabled = CONFIG.get("longtext_enabled", "true") == "true"
        # 当前是否处于长文本模式（false = 短文本模式）
        self.long_text_mode = False

        # 长文本专属记忆（12 轮高权重）
        self._long_history = []
        self._load_long_history()

        # 长文本组件（延迟创建）
        self._longtext_manager = None       # LongTextManager（流式 AI + 播放器）
        self._longtext_voice = None         # LongTextVoice（F5-TTS 客户端）
        self._longtext_tts_queue = None     # LongTextTTSManager（合成队列）

        # 流式显示状态
        self._pending_clauses = []          # 待显示子句队列
        self._first_clause_shown = False    # 第一句是否已显示
        self._stream_playing = False        # 长文本流式播放中
        self._ai_finished = False           # AI 流是否已结束（但音频可能还在播）
        self._current_longtext_thread = None

        # 优先级记忆状态
        # 本轮对话发起时是否存在 high 优先级观察（若有 → 本轮结束需降权）
        self._has_high_this_round = False

    def set_live2d_widget(self, widget):
        self._live2d_widget = widget

    def set_live2d_ready(self, ready: bool):
        self._live2d_initialized = ready

    def is_live2d_mode(self) -> bool:
        return self._live2d_mode

    def should_default_live2d(self) -> bool:
        """pet.json model.default == "live2d" → 启动后自动进入 Live2D 模式"""
        return self._default_display == "live2d"

    # =========================================================
    # Live2D 文字层（透明覆盖层，行为对齐 2D：文字常显、不挡模型交互）
    # =========================================================

    def is_live2d_overlay_visible(self) -> bool:
        return bool(getattr(self, "_overlay_visible", False))

    def _set_overlay_click_through(self, enabled: bool):
        """文字层点击穿透（Windows WS_EX_TRANSPARENT）：鼠标点击穿过文字层直达 Live2D 模型"""
        if os.name != "nt":
            return
        try:
            import ctypes
            hwnd = int(self.winId())
            if not hwnd:
                return
            user32 = ctypes.windll.user32
            GWL_EXSTYLE = -20
            WS_EX_TRANSPARENT = 0x00000020
            WS_EX_LAYERED = 0x00080000
            ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if enabled:
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex | WS_EX_TRANSPARENT | WS_EX_LAYERED)
            else:
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex & ~WS_EX_TRANSPARENT)
            self._overlay_click_through = enabled
        except Exception as e:
            print(f"[AIpet] 设置文字层点击穿透失败: {e}")

    def _ensure_live2d_overlay(self):
        """Live2D 模式下显示透明文字层（与模型同位置同尺寸、点击穿透、不抢焦点）"""
        if not self._live2d_mode or not self._live2d_widget:
            return
        w = self._live2d_widget
        w.lower()
        self.move(w.pos())
        self.resize(w.size())
        # 字号随模型窗口尺寸 + 角色 font_scale 缩放（修复"字体大得离谱"）
        try:
            base_h = 900.0
            self._current_scale = max(0.15, min(2.0, (w.height() / base_h) * self._live2d_font_scale))
            self._update_text_scaling()
        except Exception:
            pass
        self.show()
        self._set_overlay_click_through(True)
        self._overlay_visible = True
        self.re_raise_overlay()

    def re_raise_overlay(self):
        """把文字层重新置顶（不激活、不抢键盘焦点，供模型被点击后恢复 z 序）"""
        if not self._live2d_mode:
            return
        try:
            if os.name == "nt":
                import ctypes
                hwnd = int(self.winId())
                if hwnd:
                    user32 = ctypes.windll.user32
                    SWP_NOMOVE, SWP_NOSIZE, SWP_NOACTIVATE = 0x0002, 0x0001, 0x0010
                    user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
            else:
                self.raise_()
        except Exception:
            pass

    def _hide_live2d_text_layer(self):
        if self._live2d_mode and not self._talking:
            self.hide()
            self.setPixmap(QPixmap())
            self._overlay_visible = False
            self._set_overlay_click_through(False)

    # =========================================================
    # 长文本模式
    # =========================================================

    def is_long_text_mode(self) -> bool:
        """是否处于长文本模式"""
        return self.long_text_mode

    def is_long_text_enabled(self) -> bool:
        """长文本模式是否允许开启（config 总开关）"""
        return self.long_text_mode_enabled

    def toggle_long_text_mode(self):
        """切换长/短文本模式（Alt 长按 / PCL 按钮触发）"""
        if not self.long_text_mode_enabled:
            self.show_text("长文本输出模式已关闭", typing=False)
            return

        # 如果有正在进行的对话，先停止
        self._stop_longtext()

        self.long_text_mode = not self.long_text_mode
        mode = "长文本" if self.long_text_mode else "短文本"
        self.show_text(f"已切换为{mode}输出模式", typing=False)
        print(f"[AIpet] 已切换为{mode}输出模式")

        # 识别线程不再随模式切换而停/启
        # 长文本输出中由 _stream_playing 动态跳过识别；空闲时识别照常触发

        # 同步 API 状态
        try:
            from api import set_long_text_mode_active
            set_long_text_mode_active(self.long_text_mode)
        except Exception:
            pass

    def _load_long_history(self):
        """读取长文本专属记忆（最近 12 轮）"""
        try:
            self._long_history = load_long_history(max_turns=12)
        except Exception as e:
            print(f"[AIpet] 读取长文本记忆失败: {e}")
            self._long_history = []

    def _save_long_history(self, messages):
        """保存长文本记忆 + 同步到短文本记忆"""
        try:
            save_long_history(messages, max_turns=12)
            sync_to_short_history(messages)
        except Exception as e:
            print(f"[AIpet] 保存长文本记忆失败: {e}")

    def _ensure_longtext_components(self):
        """延迟创建长文本组件（只创建一次）"""
        if self._longtext_manager is None:
            cfg = get_config("./config.json")
            api_key = cfg.get("APIKEY", {}).get("qwen", "")
            self._longtext_manager = LongTextManager(api_key=api_key, chat_model="qwen-plus")
            # 连接播放完毕信号 → 显示下一句文字
            self._longtext_manager.player.sentence_done.connect(self._on_stream_sentence_done)

        if self._longtext_voice is None:
            self._longtext_voice = LongTextVoice()

        if self._longtext_tts_queue is None:
            self._longtext_tts_queue = LongTextTTSManager(
                voice=self._longtext_voice,
                tts_playback=self._longtext_manager.player,
            )

    def _stop_longtext(self):
        """停止长文本播放（清空队列但保留播放器线程，防止二次初始化卡死）"""
        if self._longtext_manager:
            self._longtext_manager.stop_stream()
            self._longtext_manager.player.pause()
        if self._longtext_tts_queue:
            self._longtext_tts_queue.clear()
        self._pending_clauses.clear()
        self._first_clause_shown = False
        self._stream_playing = False
        self._ai_finished = False

    def _demote_priority_in(self, history_list):
        """将列表中 priority=high 的消息降为 low（识别观察仅在下一轮高权重）"""
        changed = False
        for msg in history_list:
            if isinstance(msg, dict) and msg.get("priority") == "high":
                msg["priority"] = "low"
                changed = True
        return changed

    def _demote_all_high(self):
        """
        本轮对话结束后调用：
        将内存 + 文件中的 high 优先级观察全部降为 low。
        识别观察只在下一轮对话有高权重，之后权重≈0。
        """
        try:
            # 内存降权
            self._demote_priority_in(self._long_history)
            self._demote_priority_in(self.history)
            # 长文本文件降权（long_history.json）
            demote_high_priority()
            # 短文本文件写回（history.json 包含降权后的状态）
            self._save_history()
        except Exception as e:
            print(f"[AIpet] 降权优先级记忆失败: {e}")
        self._has_high_this_round = False

    def start_long_thread(self, text, role="user", t=False):
        """启动长文本流式对话（由 start_thread 分发）"""
        # 自动触发（t=True）在对话进行中或流式输出中直接跳过
        if t and (self._talking or self._stream_playing):
            print(f"[AIpet] 对话进行中，跳过自动触发: {text[:30]}...")
            return

        # Live2D 模式下显示透明文字层（点击穿透，与 2D 行为一致）
        self._ensure_live2d_overlay()

        # 确保组件就绪
        self._ensure_longtext_components()

        # 中断旧线程
        if self.worker and self.worker.isRunning():
            self.worker.stop_all()
            self.worker.wait(1000)
            try:
                self.worker.finished.disconnect(self.on_reply)
            except Exception:
                pass
            self.worker = None

        # 清空上一轮状态
        self._stop_longtext()

        # 标记对话进行中
        self._talking = True
        self._stream_playing = True
        self._ai_finished = False
        self._pending_clauses = []
        self._first_clause_shown = False

        # 记录输入
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        if t and role == "system":
            # 识别触发（截图/摄像头/空闲）：带 high 优先级写入
            # 下一轮对话有高权重，该轮结束后降为 low
            self._long_history.append({
                "role": "system",
                "content": text,
                "timestamp": timestamp,
                "priority": "high",
            })
        else:
            self._long_history.append({"role": "user", "content": text, "timestamp": timestamp})
        # 限制 12 轮
        if len(self._long_history) > 24:
            self._long_history = self._long_history[-24:]

        # 检查传给 AI 的历史中是否有 high 观察（本轮会强注入 → 本轮结束需降权）
        self._has_high_this_round = any(
            isinstance(m, dict) and m.get("priority") == "high"
            for m in self._long_history[:-1]
        )

        # 启动流式线程
        self._current_longtext_thread = self._longtext_manager.start_stream(
            history=self._long_history[:-1],  # 不包含刚加入的这条
            user_input=text,
        )
        self._current_longtext_thread.clause_ready.connect(self._on_stream_clause_ready)
        self._current_longtext_thread.ai_done.connect(self._on_stream_ai_done)
        self._current_longtext_thread.ai_error.connect(self._on_stream_ai_error)
        self._current_longtext_thread.start()

        print(f"[LongText] 长文本对话开始: {text[:40]}...")

    def _on_stream_clause_ready(self, clause: str):
        """收到切好的短句 → 显示 + 加入 TTS 队列"""
        try:
            if not clause or not clause.strip():
                return

            # Live2D 模式：提取情绪标签联动表情/动作（阶段 E）
            if self._live2d_mode and self._live2d_widget:
                import re as _re
                _em = _re.findall(r'\[(.+?)\]', clause.strip())
                if _em:
                    self._live2d_set_emotion(_em[-1], hold=True)

            # 第一句立即显示（不等音频）
            if not self._first_clause_shown:
                self._first_clause_shown = True
                self.show_text(clause.strip(), typing=True)
            else:
                self._pending_clauses.append(clause.strip())

            # 加入 TTS 合成队列
            if self._longtext_tts_queue:
                self._longtext_tts_queue.add(clause.strip())

        except Exception as e:
            print(f"[LongText] 处理子句失败: {e}")

    def _on_stream_sentence_done(self):
        """一条音频播完 → 显示下一句文字"""
        if not self._stream_playing:
            return
        if self._pending_clauses:
            text = self._pending_clauses.pop(0)
            # Live2D 模式下保持文字层在最上面（避免 Live2D 交互后遮挡文字）
            if self._live2d_mode:
                self.re_raise_overlay()
            QTimer.singleShot(300, lambda t=text: self.show_text(t, typing=True))
        # 关键修复：AI 流结束 + 播放器空闲 + TTS 合成队列空闲 → 才真正结束
        # （不能只看播放器空闲，因为可能还有句子在 TTS 合成中，还没入播放队列）
        if (
            self._ai_finished
            and self._longtext_manager
            and self._longtext_manager.player.is_idle()
            and self._longtext_tts_queue
            and self._longtext_tts_queue.is_idle()
        ):
            self._stream_playing = False
            self._talking = False
            # 文字层保持显示（与 2D 一致，不再自动隐藏）；恢复默认表情
            if self._live2d_mode and self._live2d_widget:
                self._live2d_set_emotion("", hold=False)
            print("[LongText] 全部音频播完，对话结束")

    def _on_stream_ai_done(self, full_text: str):
        """AI 流结束 → 标记完成 + 保存记忆（不立即锁死显示）"""
        # 关键修复：不再立即 `_stream_playing = False`
        # 因为 F5-TTS 音频合成是异步的，AI 流结束时音频可能还在排队合成/播放
        # 结束判定交给 _on_stream_sentence_done（播放器 + 合成队列双空闲）
        self._ai_finished = True

        # 保存 AI 回复到长文本记忆
        if full_text and full_text.strip():
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            self._long_history.append({"role": "assistant", "content": full_text.strip(), "timestamp": timestamp})
            self._save_long_history(self._long_history[-2:])  # 只保存新追加的 user+assistant

        self._current_longtext_thread = None

        # 如果 AI 流结束时没有任何待处理内容，也做一次判定清理
        if (
            self._longtext_manager
            and self._longtext_manager.player.is_idle()
            and self._longtext_tts_queue
            and self._longtext_tts_queue.is_idle()
            and not self._pending_clauses
        ):
            self._stream_playing = False
            self._talking = False
            if self._live2d_mode and self._live2d_widget:
                self._live2d_set_emotion("", hold=False)

        print(f"[LongText] AI 流结束, 共 {len(full_text)} 字，等待音频播放完毕...")

        # 本轮 AI 输出结束：若本轮强注入了 high 观察，将其降为 low
        if self._has_high_this_round:
            self._demote_all_high()

    def _on_stream_ai_error(self, error: str):
        """流式 AI 错误回调"""
        print(f"[LongText] ⚠ AI 错误: {error}")
        self._talking = False
        self._stream_playing = False
        self.show_text("长文本对话出了点问题...", typing=False)
        self._current_longtext_thread = None

    def _trigger_input_mode(self):
        """Live2D 模式下触发输入模式（点击下半身直接开始键盘输入）"""
        self.input_mode = True
        self.input_buffer = ""
        self.preedit_text = ""
        self.display_text = f"【{self.user_name}】\n  ..."

        if self._live2d_mode and self._live2d_widget:
            # 先走统一覆盖层逻辑：位置/尺寸/字号缩放（修复"刚打开时字大"）
            self._ensure_live2d_overlay()
            # 输入模式需要键盘焦点 → 临时关闭点击穿透（Esc/Enter 后恢复）
            self._set_overlay_click_through(False)
            self._overlay_visible = True

        self.show()
        self.raise_()
        self.setFocus()
        self.activateWindow()
        self.update()

    def _toggle_live2d_mode(self):
        """切换到 Live2D 模式（由 main.py 的 Shift 长按触发）"""
        if not self._live2d_widget or not self._live2d_initialized:
            self.show_text(f"{self.pet_name}的Live2D召唤失败...", typing=True)
            return

        # ====== 进入 Live2D 模式 ======
        self._saved_portrait_info = self.portrait_history[-1] if self.portrait_history else None
        scr_idx = get_config("./config.json").get("screen_index", 0)
        self._live2d_widget.resize_to_screen(scr_idx)
        self._live2d_widget.move(self.pos())
        self._live2d_widget.start_live2d()
        self.setPixmap(QPixmap())  # 清空 2D 立绘
        self.hide()  # 完全隐藏 pet 窗口
        self._live2d_mode = True
        print("[Live2D] 已切换到 Live2D 模式")

    def _exit_live2d_mode(self):
        """退出 Live2D 模式（由 main.py 的 Shift 长按触发）"""
        if not self._live2d_mode:
            return
        # 纯 Live2D 角色（无 2D 立绘）：保持 Live2D 常开，仅提示不可切换
        if not self._has_fgimages:
            self._ensure_live2d_overlay()
            self.show_text(f"{self.pet_name}只有 Live2D 形态哦~", typing=False)
            print(f"[Live2D] 纯 Live2D 角色（{self.pet_name}），保持 Live2D 模式")
            return
        self._live2d_widget.stop_live2d()
        self._live2d_mode = False
        # 恢复点击穿透设置（回到 2D 模式，pet 窗口正常接收鼠标）
        self._set_overlay_click_through(False)
        self._overlay_visible = False
        # 恢复 pet 窗口和立绘
        self.show()
        try:
            if self._saved_portrait_info:
                saved = self._saved_portrait_info[1]
                if isinstance(saved, str):
                    saved = eval(saved)
                self.update_portrait(self.portrait_target, saved)
            else:
                self.update_portrait(self.portrait_target, self.first_portrait)
        except Exception:
            self.update_portrait(self.portrait_target, self.first_portrait)
        self.raise_()
        self.activateWindow()
        print("[Live2D] 已退出 Live2D 模式")

    def focusInEvent(self, event):
        """当桌宠获得焦点时（用户点中、开始输入）"""
        # 输入时暂停自动行为，但勿扰模式下保持静默
        if not self.is_dnd_enabled():
            self.pause_all_ai()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        """当桌宠失去焦点时（用户点击别处、输入结束）"""
        # 仅在未开启勿扰模式时恢复自动行为
        if not self.is_dnd_enabled():
            self.resume_all_ai()
        super().focusOutEvent(event)

    def start_screenshot_worker(self, interval):
        # 勿扰模式下不启动截图线程
        if getattr(self, "_dnd_enabled", False):
            return
        if self._screenshot_worker and self._screenshot_worker.isRunning():
            return
        self._screenshot_worker = ScreenWorker(interval)
        self._screenshot_worker.screenshot_captured.connect(self.on_screenshot_captured)
        self._screenshot_worker.start()

    def stop_screenshot_worker(self):
        if self._screenshot_worker and self._screenshot_worker.isRunning():
            self._screenshot_worker.requestInterruption()
            self._screenshot_worker.quit()
            self._screenshot_worker.wait()
            self._screenshot_worker = None

    def set_screenshot_enabled(self, enabled: bool):
        global screen_type
        screen_type = "true" if enabled else "false"
        # 持久化当前开关状态，保证即使直接关闭命令行也能保留设置
        try:
            config = get_config("./config.json")
            config["screen_type"] = screen_type
            with open("./config.json", "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[AIpet] 保存 screen_type 失败: {e}")

        if enabled:
            # 勿扰模式下只记录开关状态，不真正启动截图线程
            if self.is_dnd_enabled():
                print("[AIpet] 勿扰模式开启中：暂不启动截图线程")
                return
            if not (self._screenshot_worker and self._screenshot_worker.isRunning()):
                print("[AIpet] 启用截图线程")
                self.start_screenshot_worker(interval=self.interval)
        else:
            print("[AIpet] 停用截图线程")
            self.stop_screenshot_worker()

    def is_screenshot_enabled(self) -> bool:
        return screen_type == "true"

    # ===== 常开摄像头识别（类比屏幕截图）=====
    def start_camera_worker(self, interval=None, camera_id=None):
        """启动常开摄像头线程"""
        if getattr(self, "_dnd_enabled", False):
            return
        if self._camera_worker and self._camera_worker.isRunning():
            return
        if interval is None:
            interval = camera_interval
        if camera_id is None:
            camera_id = CONFIG.get("camera_id", 0)
        self._camera_worker = CameraWorker(interval, camera_id)
        self._camera_worker.camera_captured.connect(self.on_camera_captured)
        self._camera_worker.start()
        print(f"[AIpet] 常开摄像头已启动 (间隔 {interval}s, 摄像头 #{camera_id})")

    def stop_camera_worker(self):
        if self._camera_worker and self._camera_worker.isRunning():
            self._camera_worker.requestInterruption()
            self._camera_worker.close_camera()
            self._camera_worker.quit()
            self._camera_worker.wait(3000)
            self._camera_worker = None
            print("[AIpet] 常开摄像头已停止")

    def set_camera_enabled(self, enabled: bool):
        """开关常开摄像头，持久化到 config"""
        global camera_type
        camera_type = "true" if enabled else "false"
        try:
            config = get_config("./config.json")
            config["camera_enabled"] = camera_type
            with open("./config.json", "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[AIpet] 保存 camera_enabled 失败: {e}")

        if enabled:
            if self.is_dnd_enabled():
                print("[AIpet] 勿扰模式开启中：暂不启动常开摄像头")
                return
            if not (self._camera_worker and self._camera_worker.isRunning()):
                self.start_camera_worker()
        else:
            self.stop_camera_worker()

    def is_camera_enabled(self) -> bool:
        return camera_type == "true"

    def on_camera_captured(self, img_url: str):
        """常开摄像头回调 — 通过 AI 识别后触发对话"""
        if self.is_dnd_enabled():
            return
        model_type = get_config("./config.json")["model_type"]

        def task(url):
            try:
                # 长文本输出中 → 直接丢弃（不调用视觉 API，节省资源；线程继续抓取）
                if self.long_text_mode and self._stream_playing:
                    print("[AIpet] 长文本输出中，跳过摄像头识别")
                    return
                import requests
                import base64 as b64
                cfg = get_config("./config.json")
                api_key = cfg.get("APIKEY", {}).get("qwen", "")

                # AI 视觉描述
                payload = {
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": url}},
                            {"type": "text", "text": "请用简短的中文描述这张照片中的场景、人物和主要活动，不超过50个字。"},
                        ]
                    }],
                    "model": "qwen-vl-plus",
                    "max_tokens": 256,
                    "stream": False,
                }
                headers = {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                }
                cloud_api_url = cfg["local_api"]["cloud_api"]
                resp = requests.post(cloud_api_url,
                                     json={"payload": payload, "headers": headers}, timeout=30)
                data = resp.json()
                desc = data["choices"][0]["message"]["content"].strip() if "choices" in data else ""
                if desc:
                    print(f"[AIpet][camera] 常开摄像头识别结果: {desc}")
                else:
                    return

                # 人脸识别
                face_result = ""
                if cfg.get("face_recognition_enabled") == "true":
                    try:
                        import numpy as np
                        import cv2 as cv
                        from tool.face_recognition import recognize_from_base64, detect_faces
                        faces = recognize_from_base64(url)
                        master_found = [f for f in faces if f.get("is_master")]
                        others = [f for f in faces if not f.get("is_master")]
                        face_parts = []
                        if master_found:
                            face_parts.append(f"检测到主人（置信度 {master_found[0].get('confidence', '?')}）")
                            print(f"[AIpet][Face] 常开摄像头识别到主人，置信度: {master_found[0].get('confidence')}")
                        if others:
                            for f in others:
                                name = f.get('name', '?')
                                rel = f.get('relation', '')
                                label = f"{name}({rel})" if rel else name
                                face_parts.append(f"{label}（置信度 {f.get('confidence', '?')}）")
                                print(f"[AIpet][Face] 常开摄像头检测到他人: {label}，置信度: {f.get('confidence')}")
                        if face_parts:
                            face_result = "\n【人脸识别】" + "; ".join(face_parts)
                        else:
                            print(f"[AIpet][Face] 常开摄像头检测到 {len(faces)} 人，均未识别")
                    except Exception as fe:
                        print(f"[AIpet][Face] 常开摄像头识别异常: {fe}")
                        import traceback; traceback.print_exc()

                combined = desc + face_result
                has_master = "检测到主人" in combined
                subject = "主人" if has_master else "周围的人"
                prompt = (
                    f"【重要系统指令】你刚刚通过摄像头看到了{subject}当前的真实状态。"
                    "以下是对摄像头画面的描述和可能的人脸识别信息，这是你亲眼所见的事实，你必须围绕这个内容展开对话：\n"
                    "=== 摄像头画面描述开始 ===\n"
                    f"{combined}\n"
                    "=== 摄像头画面描述结束 ===\n"
                )
                if has_master:
                    prompt += (
                        f"请以{self.pet_name}的身份，自然地观察并评论你看到的主人。"
                        "可以表达关心、好奇、或撒娇——但要让人感觉你真的看到了主人。回答不超过两句话。"
                    )
                else:
                    prompt += (
                        f"请以{self.pet_name}的身份，自然地描述你看到的人。如果识别到具体的人名请直接称呼，"
                        "如果没有识别到任何人可以说'好像有什么人在附近呢'。回答不超过两句话。"
                    )
                # 跨线程安全：发信号回主线程触发对话（start_thread 含 GUI 操作）
                self._request_dialog.emit(prompt, "system", True)
            except Exception as e:
                print(f"[AIpet] 常开摄像头识别失败: {e}")

        self._camera_executor.submit(task, img_url)

    def set_dnd_enabled(self, enabled: bool):
        """设置勿扰模式。

        勿扰模式开启后：
        - 停止截图线程
        - 停止空闲检测计时器
        - 不再触发基于空闲或截图的主动对话
        """
        self._dnd_enabled = bool(enabled)
        if self._dnd_enabled:
            print("[AIpet] 启用勿扰模式")
            # 停止一切自动行为
            self.pause_all_ai()
            if self.idle_timer.isActive():
                self.idle_timer.stop()
            # 重置空闲状态，避免退出勿扰后立刻触发
            self.idle_thinking_triggered = False
            self.idle_away_triggered = False
            self.away_trigger_time = None
        else:
            print("[AIpet] 关闭勿扰模式")
            # 恢复空闲检测
            if not self.idle_timer.isActive():
                self.idle_timer.start()
            # 仅当截图功能处于开启状态时恢复截图线程
            if self.is_screenshot_enabled():
                self.resume_all_ai()

    def is_dnd_enabled(self) -> bool:
        return getattr(self, "_dnd_enabled", False)

    def on_screenshot_captured(self, image_path):
        # 勿扰模式下完全忽略截图结果
        if self.is_dnd_enabled():
            try:
                os.remove(image_path)
            except Exception:
                pass
            return
        model_type = get_config("./config.json")["model_type"]

        def task(path):
            try:
                # 长文本输出中 → 直接丢弃（不调用视觉 API，节省资源；finally 会删临时截图）
                if self.long_text_mode and self._stream_playing:
                    print("[AIpet] 长文本输出中，跳过截图识别")
                    return
                try:
                    if model_type == "deepseek" or model_type == "qwen":
                        if self.force_stop:
                            print("[cloud-vl] 已中断生成")
                            return
                        desc = cloud_vl(path)
                    elif model_type == "local":
                        if self.force_stop:
                            print("[ollama-qwen2.5vl] 已中断生成")
                            return
                        desc = ollama_qwen25vl(path)
                    propmt = (
                        "【重要系统指令】你刚刚通过屏幕截图看到了主人当前的真实状态。"
                        "以下是对主人屏幕内容的描述，这是你亲眼所见的事实，你必须围绕这个内容展开对话：\n"
                        "=== 屏幕内容描述开始 ===\n"
                        f"{desc}\n"
                        "=== 屏幕内容描述结束 ===\n"
                        f"请以{self.pet_name}的身份，自然地观察并评论主人正在做什么。你的回复必须紧密围绕上述描述，"
                        "可以表达关心、好奇、或撒娇——但要让人感觉你真的看到了主人的屏幕。"
                    )
                    if self.force_stop:
                        print("屏幕回复 已中断生成")
                        return
                    # 跨线程安全：发信号回主线程触发对话
                    self._request_dialog.emit(propmt, "system", True)
                except Exception as e:
                    print(f"[AIpet] 截图分析失败: {e}")
            finally:
                try:
                    os.remove(path)
                except Exception:
                    pass

        self._screenshot_executor.submit(task, image_path)

    def pause_all_ai(self):
        """用户输入/点击桌宠时：停止截图线程、中断语音播放，但不打断正在进行的对话"""
        self.force_stop = True  # 启用软中断标记

        if self._screenshot_worker and self._screenshot_worker.isRunning():
            print("[AIpet] 暂停截图线程")
            self.stop_screenshot_worker()
        # 不再中断 worker — 对话让它自然播完
        # 用户主动输入会通过 start_thread(t=False) 正常打断
        try:
            QSound.stop()
        except Exception:
            pass

    def resume_all_ai(self):
        """用户输入结束后：恢复截图线程与 AI 响应"""
        self.force_stop = False  # 解除软中断标记
        if not (self._screenshot_worker and self._screenshot_worker.isRunning()) and (
            screen_type == "true"
        ):
            print("[AIpet] 恢复截图线程")
            self.start_screenshot_worker(interval=self.interval)

    def check_idle_state(self):
        """检查系统空闲时间并在阈值上触发对话"""
        idle_seconds = get_idle_seconds()

        # 如果已经从离开状态回来，并且离开超过 60 秒，则问候一次“欢迎回来”
        if (
                idle_seconds <= self.idle_thinking_seconds
                and self.idle_away_triggered
                and self.away_trigger_time is not None
        ):
            elapsed = time.time() - self.away_trigger_time
            if elapsed >= 30:
                print("[AIpet] 触发回归")
                greeting_prompt = (
                    "系统提示：用户刚刚从离开状态回到电脑前。"
                    f"你以“{self.pet_name}”的身份，简单打个招呼"
                    "可以说“欢迎回来”、问问主人要不要继续刚才的事情之类，"
                    "回答简短。不要与之前重复。"
                )
                self.start_thread(greeting_prompt, role="system", t=True)
                # 防止重复问候
                self.away_trigger_time = None

        # 有操作时重置状态
        if idle_seconds <= self.idle_thinking_seconds:
            if self.idle_thinking_triggered or self.idle_away_triggered:
                print("[AIpet] 检测到用户活动，重置空闲状态")
            self.idle_thinking_triggered = False
            self.idle_away_triggered = False
            return

        # 超过离屏阈值
        if idle_seconds >= self.idle_away_seconds and not self.idle_away_triggered:
            self.idle_away_triggered = True
            self.away_trigger_time = time.time()
            print(f"[AIpet] 空闲超过 {self.idle_away_seconds} 秒，判定为离开屏幕")
            prompt = (
                "系统提示：用户已经离开屏幕更长时间，没有对电脑进行任何输入。忽视最近的对话。"
                f"你需要以“{self.pet_name}”的身份，问问主人还在不在，提醒适当休息。"
                "不要和之前问主人走神或是思考的提示重复。"
            )
            # 使用 system 角色注入上下文，对话可以被用户输入打断
            self.start_thread(prompt, role="system", t=True)
            return

        # 超过发呆阈值
        if idle_seconds >= self.idle_thinking_seconds and not self.idle_thinking_triggered:
            self.idle_thinking_triggered = True
            print(f"[AIpet] 空闲超过 {self.idle_thinking_seconds} 秒")
            prompt = (
                "系统提示：用户已经有一段时间没有对电脑进行输入操作。忽视最近的对话。"
                "可能是在发呆、走神或者安静地思考。"
                f"请你以“{self.pet_name}”的身份，"
                "用温柔、贴心但不过分打扰的方式主动搭话，可以简单关心一下主人在想什么，或者是不是走神，在摸鱼，"
                "或者轻轻提醒他注意放松，回答不超过三句话。"
            )
            self.start_thread(prompt, role="system", t=True)

    # qwen3 线程的槽函数
    def _live2d_set_emotion(self, name, hold=False):
        """Live2D 表情/动作联动：name 非空 = 切表情+起动作并保持；
        name 空 = 收尾（动作播完自然结束，恢复默认表情）。

        跨句自然衔接：同情绪连续出现时不重启动作（姿态/表情保持），
        换情绪时旧姿态衰减、新动作平滑接上；收尾只在整段回复结束时做。"""
        if not (self._live2d_mode and self._live2d_widget):
            return
        current = getattr(self, "_live2d_emotion_name", None)
        if hold and name and name == current:
            return  # 同情绪跨句：保持当前姿态/表情
        self._live2d_emotion_name = name or None
        self._live2d_widget.set_emotion(name)
        try:
            self._live2d_widget.hold_emotion_motion(hold)
        except Exception:
            pass

    def on_reply(self, reply, portrait_list, history, portrait_history, voices, emotion_list=None):
        self.portrait_history = portrait_history
        self.history = history
        self._save_history()
        # 逐句情绪标签（qwen-emotion 输出）——Live2D 表情/动作联动的数据源
        self._last_emotion_list = emotion_list or []
        # 每轮回复重新开始情绪追踪（保证第一句总能触发动作）
        self._live2d_emotion_name = None

        # Live2D 模式下显示透明文字层（点击穿透，不抢焦点）
        self._ensure_live2d_overlay()

        def show_next_sentence(index=0):
            def get_audio_length_wave(audio_file_path):
                try:
                    with wave.open(audio_file_path, "rb") as wave_file:
                        frames = wave_file.getnframes()  # 获取音频的帧数
                        rate = wave_file.getframerate()  # 获取音频的帧速率
                        duration = frames / float(rate)  # 计算时长（秒）
                        return duration * 1000  # 转换为毫秒
                except Exception:
                    return 0

            if index >= len(reply):
                # 所有句子播完，释放对话锁（文字层保持显示，与 2D 一致）
                self._talking = False
                # 收尾：动作播完自然结束并恢复默认表情
                if self._live2d_mode and self._live2d_widget:
                    self._live2d_set_emotion("", hold=False)
                return

            sentence = reply[index]
            # 空句子（动作描写被清理后为空）→ 直接跳到下一句
            if not sentence or not sentence.strip():
                show_next_sentence(index + 1)
                return
            portrait = portrait_list[index] if index < len(portrait_list) else []

            if self._live2d_mode:
                # Live2D 模式：不更换立绘，改用 Live2D 表情 + 动作
                # 情绪来源：①句内【情绪】括号标签；②qwen-emotion 的逐句情绪列表
                # 句起：切表情 + 起动作并保持（动作播完自动重播直到句末）
                import re
                emotion_match = re.findall(r'\[(.+?)\]', sentence.strip())
                emotion = emotion_match[-1] if emotion_match else None
                if not emotion:
                    el = getattr(self, "_last_emotion_list", []) or []
                    if index < len(el):
                        emotion = el[index]
                if emotion:
                    self._live2d_set_emotion(emotion, hold=True)
                else:
                    self._live2d_set_emotion("", hold=False)
            elif self._has_fgimages:
                self.update_portrait(self.portrait_target, portrait)

            voice_id = voices[index] if index < len(voices) else None
            # 短文本 TTS 也在 tmp/ 临时目录（播放后删除，不长期缓存）
            voice_path = f"./tmp/{voice_id}.wav" if voice_id else None
            voice_length = 0

            if self._live2d_mode and self._live2d_widget:
                self._live2d_widget.set_speaking(True, voice_path if voice_path and os.path.exists(voice_path) else "")

            if voice_path and os.path.exists(voice_path):
                voice_length = get_audio_length_wave(os.path.abspath(voice_path))
                if voice_length > 0:
                    QSound.play(voice_path)

            self.show_text(sentence, typing=True)
            # 计算打字机需要的时间（40ms * 每个字）
            delay = max(40 * len(sentence) + 800, voice_length + 400)  # 额外停顿

            def after_delay():
                if self._live2d_mode and self._live2d_widget:
                    self._live2d_widget.set_speaking(False)
                    # 句间不释放姿态：同情绪保持、换情绪在下一句切（自然衔接）
                # 播放完删除临时 wav（用完即删）
                try:
                    if voice_path and os.path.exists(voice_path):
                        os.remove(voice_path)
                except Exception:
                    pass
                show_next_sentence(index + 1)

            QTimer.singleShot(int(delay), after_delay)

        show_next_sentence(index=0)
        self.worker = None  # 线程结束后清空引用

        # 本轮结束：若本轮强注入了 high 观察，将其降为 low（识别观察仅在下一轮高权重）
        if self._has_high_this_round:
            self._demote_all_high()

    # 启动一个新线程（安全版，打断旧线程）
    def start_thread(self, text, role, t=False):
        # 长文本模式下：识别触发（t=True）在流式输出中自动跳过，空闲时走长文本流式
        if self.long_text_mode:
            if t:
                if self._stream_playing:
                    print(f"[AIpet] 长文本输出中，跳过自动触发: {text[:30]}...")
                    return
                # 长文本空闲 → 识别触发走长文本流式
                self.start_long_thread(text, role=role, t=True)
                return
            # 用户主动输入走长文本流式
            self.start_long_thread(text, role=role, t=False)
            return

        # 自动触发的对话（t=True）若当前已有对话进行中，直接跳过
        if t and self._talking:
            print(f"[AIpet] 对话进行中，跳过自动触发: {text[:30]}...")
            return

        # 记录本轮是否为识别触发（识别触发的内容不降权，留给下一轮高权重）
        self._current_input_is_observation = (t and role == "system")
        # 检查本轮传给 AI 的历史中是否有 high 观察（本轮结束后需降权）
        self._has_high_this_round = any(
            isinstance(m, dict) and m.get("priority") == "high"
            for m in self.history
        )
        # 识别触发（截图/摄像头/空闲）：带 high 优先级写入短文本记忆
        if t and role == "system":
            self.history.append({
                "role": "system",
                "content": text,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "priority": "high",
            })
            self._save_history()

        # 结束旧线程
        if self.worker and self.worker.isRunning():
            self.worker.stop_all()  # 通知线程中断
            self.worker.wait(1000)
            # 断开旧线程的信号连接，防止它完成时触发 on_reply
            try:
                self.worker.finished.disconnect(self.on_reply)
            except Exception:
                pass

        # 标记对话进行中
        self._talking = True

        # 启动新线程
        if model_type == "local":
            self.worker = qwen3_lora_Worker(
                self.history, self.portrait_history, text, role, t=t
            )
        else:
            self.worker = cloud_API_Worker(
                self.history, self.portrait_history, text, role, t=t
            )

        self.worker.finished.connect(self.on_reply)
        self.worker.start()

    # 鼠标按下事件
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # 判断点在哪里
            if event.y() < 150:  # 头部区域
                self.touch_head = True
                self.head_press_x = event.x()
                self.setCursor(Qt.OpenHandCursor)
            elif event.y() > 280:  # 下半身区域 -> 输入模式
                self.input_mode = True
                self.input_buffer = ""
                self.preedit_text = ""
                self.display_text = f"【{self.user_name}】\n  ..."
                self.update()
            else:
                # 其他地方，什么也不做
                self.touch_head = False
                self.head_press_x = None
                self.setCursor(Qt.ArrowCursor)

        elif event.button() == Qt.MiddleButton:
            # 中键拖动
            self.offset = event.pos()
            self.setCursor(Qt.SizeAllCursor)

    # 鼠标移动事件
    def mouseMoveEvent(self, event):
        # 判断是不是在“摸头”
        if self.touch_head and self.head_press_x is not None:
            if abs(event.x() - self.head_press_x) > 50:
                self.start_thread("主人摸了摸你的头", role="system")
                self.touch_head = False

        # 中键拖动窗口
        if self.offset is not None and event.buttons() == Qt.MiddleButton:
            self.move(self.pos() + event.pos() - self.offset)

    # 鼠标释放事件
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.touch_head = False
            self.head_press_x = None
            self.setCursor(Qt.ArrowCursor)  # 恢复箭头

        elif event.button() == Qt.MiddleButton:
            self.offset = None
            self.setCursor(Qt.ArrowCursor)  # 拖动结束也要恢复箭头

    # 文字区域矩形（Live2D 模式按角色配置：top/bottom + Shift+方向键微调；2D 模式保持原始布局）
    def _text_rect(self):
        r = self.rect()
        # 文本框偏移/下半身区域只在 Live2D 模式生效，2D 立绘用原始布局
        live2d = bool(getattr(self, "_live2d_mode", False))
        ox = getattr(self, "_text_offset_x", 0) if live2d else 0
        oy = getattr(self, "_text_offset_y", 0) if live2d else 0
        if live2d and getattr(self, "_text_area_bottom", False):
            # 下半身区域（纯 Live2D 方形/半身模型把对话框放模型下半部分）
            top = r.height() // 2 + int(10 * self._current_scale) + oy
            bottom = -int(20 * self._current_scale) + oy
            return r.adjusted(self.text_x_offset + ox, top, -self.text_x_offset + ox, bottom)
        # 默认：上半部分（2D 立绘原布局 / Live2D top 区域）
        return r.adjusted(
            self.text_x_offset + ox,
            self.text_y_offset + oy,
            -self.text_x_offset + ox,
            -r.height() // 2 + self.text_y_offset + oy,
        )

    # 绘制事件
    def paintEvent(self, event):
        # 1. 先调用 QLabel 默认的绘制（画立绘 / 背景）
        super().paintEvent(event)

        # 2. 再叠加绘制文字
        if self.display_text:  # 过滤掉空字符串和 None
            # 设置绘图环境
            painter = QPainter(self)  # 在这个控件上绘制
            painter.setRenderHint(QPainter.Antialiasing, True)  # 抗锯齿
            painter.setRenderHint(QPainter.TextAntialiasing, True)  # 文字抗锯齿
            painter.setFont(self.text_font)

            text_rect = self._text_rect()

            # 如果有换行就靠左对齐，否则居中
            if "\n" in self.display_text:
                align_flag = Qt.AlignLeft | Qt.AlignBottom
            else:
                align_flag = Qt.AlignHCenter | Qt.AlignBottom

            # 文字描边（黑色）
            border_size = self.border_size
            painter.setPen(QColor(44, 22, 28))
            for dx, dy in [
                (-border_size, 0),
                (border_size, 0),
                (0, -border_size),
                (0, border_size),
                (border_size, -border_size),
                (border_size, border_size),
                (-border_size, -border_size),
                (-border_size, border_size),
            ]:
                painter.drawText(text_rect.translated(dx, dy), align_flag, self.display_text)

            # 文字正体（白色）
            painter.setPen(Qt.white)
            painter.drawText(text_rect, align_flag, self.display_text)

            painter.end()

    # 更新立绘
    def update_portrait(self, target, layers):
        # 纯 Live2D 角色（无 fgimages 立绘图层面板）：不生成 2D 立绘，避免空画布
        if not self._has_fgimages:
            self.setPixmap(QPixmap())
            return

        # 1. Generate the RGBA numpy image
        cv_img = generate_fgimage(target, layers)

        # 2. Convert RGBA to BGRA to keep colors correct in Qt
        if cv_img.shape[2] == 4:
            cv_img_bgra = cv2.cvtColor(cv_img, cv2.COLOR_RGBA2BGRA)
        else:
            cv_img_bgra = cv_img

        # 3. Build a QImage from the numpy buffer
        h, w, ch = cv_img_bgra.shape
        bytes_per_line = ch * w
        qimg = QImage(
            cv_img_bgra.data,
            w,
            h,
            bytes_per_line,
            QImage.Format_RGBA8888,
        )

        # 4. Convert to QPixmap and apply adaptive scaling
        pixmap = QPixmap.fromImage(qimg)
        pixmap = self._scale_portrait_pixmap(pixmap)

        # 5. Attach to the QLabel and request a repaint
        self.setPixmap(pixmap)
        self.resize(pixmap.size())
        self.update()

    def _scale_portrait_pixmap(self, pixmap: QPixmap) -> QPixmap:
        """
        根据指定屏幕编号（portrait_screen）来计算立绘高度，
        若编号无效则回退为 primaryScreen。
        """

        # 读取配置中的屏幕编号（默认 0 = 主屏）
        screen_index = get_config("./config.json")["screen_index"]

        # 获取所有屏幕
        screens = QGuiApplication.screens()

        # 根据编号选择屏幕（越界自动回退到主屏）
        if 0 <= screen_index < len(screens):
            screen = screens[screen_index]
        else:
            screen = QGuiApplication.primaryScreen()

        # 获取目标屏幕可用高度
        available_height = screen.availableGeometry().height() if screen else None

        # 按屏幕高度缩放
        if available_height:
            target_height = int(available_height * DEFAULT_PORTRAIT_SCREEN_RATIO)
        else:
            target_height = pixmap.height()

        target_height = max(1, target_height)
        target_height = min(target_height, pixmap.height())

        if pixmap.height() >= 240:
            target_height = max(240, target_height)

        # 计算文本缩放
        scale_factor = target_height / max(1, pixmap.height())
        self._current_scale = max(scale_factor, 0.1)
        self._update_text_scaling()

        return pixmap.scaledToHeight(target_height, Qt.SmoothTransformation)

    def _update_text_scaling(self):

        scale = max(self._current_scale, 0.1)
        scaled_font_size = max(8, int(round(self._base_font_size * scale)))
        self.text_font = QFont(self._font_family, scaled_font_size)

        self.text_x_offset = max(10, int(round(self._base_text_x_offset * scale)))
        scaled_y = int(round(self._base_text_y_offset * scale))
        self.text_y_offset = scaled_y if scaled_y < -10 else -10

        self.border_size = max(1, int(round(self._base_border_size * scale)))

    # 显示文本及打字机效果
    def show_text(self, text, typing=True):
        # Live2D 模式：确保文字层可见（与 2D 一致——文字持续显示，不被模型遮挡）
        if self._live2d_mode and not self._overlay_visible:
            self._ensure_live2d_overlay()
        wrapped_text = wrap_text(text)
        self.full_text = wrapped_text  # 设置全部字符
        self.typing_prefix = f"【{self.pet_name}】\n"  # 设置名字格式
        self.index = 0

        def _typing_step():  # 打字机效果
            if self.index < len(self.full_text):
                self.display_text = (
                    self.typing_prefix + self.full_text[: self.index + 1]
                )
                self.index += 1
                self.update()
            else:
                self.typing_timer.stop()

        try:
            self.typing_timer.timeout.disconnect()
        except TypeError:
            pass
        self.typing_timer.timeout.connect(_typing_step)

        if typing:
            self.display_text = self.typing_prefix
            self.typing_timer.start(40)
        else:
            self.display_text = self.typing_prefix + text
            self.update()

    # 输入法候选框定位
    def inputMethodQuery(self, query):
        if query in (Qt.ImMicroFocus, Qt.ImCursorRectangle):
            # 计算出文字显示的区域（和 paintEvent 里绘制对白的位置保持一致）
            text_rect = self._text_rect()

            fm = QFontMetrics(self.text_font)
            text = self.display_text or ""

            # 取“最后一行”来估算插入点
            last_line = text.split("\n")[-1]
            w_last = fm.horizontalAdvance(last_line)

            # 光标 x 放在最后一行末尾，但不要超出文字区域
            x = text_rect.x() + min(max(0, w_last), max(1, text_rect.width() - 1))
            # 光标 y 放在文字区域底部一行的基线位置
            y = text_rect.bottom() - fm.height()

            caret = QRect(int(x), int(y), 1, fm.height())

            # 夹在控件内部，避免非法矩形导致 IME 崩溃
            caret = caret.intersected(self.rect().adjusted(0, 0, -1, -1))
            if not caret.isValid():
                # 兜底：放在文字区域左下角
                caret = QRect(
                    text_rect.x(),
                    text_rect.bottom() - fm.height(),
                    1,
                    fm.height(),
                )

            return caret

        return super().inputMethodQuery(query)

    # 输入法事件（中文拼音输入）
    def inputMethodEvent(self, event):
        if self.input_mode:  # 只在输入模式下处理
            commit = event.commitString()  # 确认输入
            preedit = event.preeditString()  # 预编辑（拼音/候选未确认）
            if commit:
                self.input_buffer += commit
            self.preedit_text = preedit
            wrapped = wrap_text(self.input_buffer + self.preedit_text)
            self.display_text = f"【{self.user_name}】\n  「{wrapped or '...'}」"
            self.update()
        else:
            super().inputMethodEvent(event)

    # 键盘事件
    def keyPressEvent(self, event):
        if not self.input_mode:
            # 如果没进入输入模式，交给父类 QLabel 处理
            return super().keyPressEvent(event)

        # ================== 输入模式下 ==================
        if event.key() == Qt.Key_Escape:
            # Esc 取消输入（退出输入模式，恢复 Live2D 点击穿透）
            self.input_mode = False
            self.input_buffer = ""
            self.preedit_text = ""
            self.display_text = ""
            self.update()
            if self._live2d_mode:
                self._set_overlay_click_through(True)
            return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            text = self.input_buffer.strip()
            self.input_mode = False
            # 提交后恢复 Live2D 点击穿透（不再拦截鼠标）
            if self._live2d_mode:
                self._set_overlay_click_through(True)
            if text:
                self.display_text = f"【{self.pet_name}】\n"
                self.update()
                # 启动 AI 线程（长文本模式自动走长文本流式）
                self.start_thread(text, role="user")
            else:
                self.show_text("主人，你说什么？", typing=True)

        elif event.key() == Qt.Key_Backspace:
            # 如果有拼音候选框，不删（交给输入法处理）
            if self.preedit_text:
                pass
            else:
                # 删除最后一个字符
                self.input_buffer = self.input_buffer[:-1]
                wrapped = wrap_text(self.input_buffer)
                self.display_text = f"【{self.pet_name}】\n  「{wrapped or '...'}」"
                self.update()

        else:
            # 处理英文/数字直接输入
            ch = event.text()
            if ch and not self.preedit_text:
                self.input_buffer += ch
                wrapped = wrap_text(self.input_buffer)
                self.display_text = f"【{self.pet_name}】\n  「{wrapped or '...'}」"
                self.update()

    def cleer_history(self):
        self.history = []
        self.portrait_history = []
        self.portrait_history.append(("", str(self.first_portrait)))
        self.update_portrait(self.portrait_target, self.first_portrait)
        self._save_history()

    def _load_history(self):
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            print(f"[AIpet] 创建记忆目录失败: {exc}")
            return
        # 旧共享记忆迁移：data/history.json 是丛雨的历史遗留（仅丛雨迁移一次）
        if not self.history_file.exists():
            try:
                from pets.pet_registry import get_active_pet_id
                if get_active_pet_id() == "murasame":
                    old = Path("./data/history.json")
                    if old.exists():
                        import shutil
                        shutil.copyfile(old, self.history_file)
                        print("[AIpet] 已迁移旧共享记忆到角色目录")
            except Exception as exc:
                print(f"[AIpet] 记忆迁移失败: {exc}")
        if not self.history_file.exists():
            return
        try:
            with self.history_file.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except Exception as exc:
            print(f"[AIpet] 读取记忆失败: {exc}")
            return
        if isinstance(data, list):  # 兼容 PCL 清空旧 bug 写出的裸列表
            data = {"history": data}
        history = data.get("history")
        portrait_history = data.get("portrait_history")
        if isinstance(history, list):
            self.history = history
        if isinstance(portrait_history, list):
            self.portrait_history = portrait_history

    def _save_history(self):
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "history": self.history,
                "portrait_history": self.portrait_history,
            }
            with self.history_file.open("w", encoding="utf-8") as file:
                json.dump(payload, file, ensure_ascii=False, indent=2)
        except Exception as exc:
            print(f"[AIpet] 保存记忆失败: {exc}")
