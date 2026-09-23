import io
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
from PyQt5.QtCore import Qt, QRect, QSize
from PyQt5.QtCore import QPropertyAnimation, QEasingCurve, QVariantAnimation, QPoint
from PyQt5.QtGui import QGuiApplication, QCursor, QImage
from PyQt5.QtGui import QPainter, QColor, QFont, QPixmap, QFontMetrics
from PyQt5.QtMultimedia import QSound
from PyQt5.QtWidgets import QLabel

from classes.Worker_class import ScreenWorker
from classes.Worker_class import qwen3_lora_Worker, cloud_API_Worker, CameraWorker
from tool.config import get_config
from tool.chat import (ollama_qwen25vl, describe_image,
                       vision_fast_size, vision_fast_tokens)
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


class PetQuickButton(QLabel):
    """立绘右上角的小按钮：只显示一个图标，悬停轻微放大变亮（自带 120ms 过渡）。

    为什么做成独立小控件而不是画在大窗口里：
      桌宠窗口是半透明 + 带描边文字的大窗口，在大窗口里做动画每帧都要重绘整窗
      → 又卡又有延迟；小控件只脏自己那几十像素，而且悬停用 enterEvent
      → 即时响应，不依赖鼠标移动事件或轮询。
    """

    clicked = pyqtSignal()

    def __init__(self, icon_name: str, size: int = 44, parent=None):
        super().__init__(parent)
        self._icon_name = str(icon_name)
        self._k = 0.0                 # 悬停进度 0~1
        self._pressed = False
        self._scaled_cache = {}
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(int(size), int(size))
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(120)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)
        self._src = self._load_icon()

    def _load_icon(self):
        try:
            from tool.paths import app_base_dir
            base = app_base_dir()
        except Exception:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        fp = os.path.join(base, "ui", "chat.png" if self._icon_name == "chat" else "menu.png")
        pm = QPixmap(fp) if os.path.isfile(fp) else QPixmap()
        if not pm.isNull() and pm.width() > 256:
            pm = pm.scaled(256, 256, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return pm

    def set_size(self, size: int):
        size = max(30, min(64, int(size)))
        if size != self.width():
            self.setFixedSize(size, size)
            self._scaled_cache.clear()
            self.update()

    def _scaled(self, size: int):
        pm = self._scaled_cache.get(size)
        if pm is None and not self._src.isNull():
            pm = self._src.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            if len(self._scaled_cache) > 24:
                self._scaled_cache.clear()
            self._scaled_cache[size] = pm
        return pm

    def _on_anim(self, v):
        try:
            self._k = float(v)
            self.update()
        except Exception:
            pass

    def _animate(self, target: float):
        try:
            self._anim.stop()
            self._anim.setStartValue(float(self._k))
            self._anim.setEndValue(float(target))
            self._anim.start()
        except Exception:
            pass

    def enterEvent(self, event):
        self._animate(1.0)
        try:
            return super().enterEvent(event)
        except Exception:
            pass

    def leaveEvent(self, event):
        self._animate(0.0)
        self._pressed = False
        try:
            return super().leaveEvent(event)
        except Exception:
            pass

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._pressed = True
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._pressed:
            self._pressed = False
            self.update()
            try:
                self.clicked.emit()
            except Exception:
                pass

    def paintEvent(self, event):
        # 只画图标、没有底板：悬停放大 + 更亮，按下略缩
        try:
            k = max(0.0, min(1.0, self._k))
            grow = 1.0 + 0.14 * k - (0.08 if self._pressed else 0.0)
            side = max(8, int(min(self.width(), self.height()) * grow))
            pm = self._scaled(side)
            pt = QPainter(self)
            pt.setRenderHint(QPainter.Antialiasing, True)
            pt.setRenderHint(QPainter.SmoothPixmapTransform, True)
            cx, cy = self.width() // 2, self.height() // 2
            if pm is not None and not pm.isNull():
                pt.setOpacity(0.86 + 0.14 * k)
                pt.drawPixmap(cx - pm.width() // 2, cy - pm.height() // 2, pm)
                pt.setOpacity(1.0)
            else:
                pt.setPen(QColor(255, 250, 245, 230))
                f = QFont(self.font())
                f.setPointSize(max(11, int(side * 0.5)))
                pt.setFont(f)
                pt.drawText(self.rect(), Qt.AlignCenter, "聊" if self._icon_name == "chat" else "≡")
            pt.end()
        except Exception as e:
            print(f"[桌宠] ⚠ 快捷按钮绘制失败: {e}")


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
    # 电脑操作真做完之后（Worker 线程发）→ 主线程让她说一句"我做了什么"
    _pc_done = pyqtSignal(str)
    # 任务循环（pc_task 后台线程）的状态与收尾 → 主线程显示/说话
    _task_status = pyqtSignal(str)
    _task_finish = pyqtSignal(str, bool)
    # 自主学习窗口刷新（后台线程 → 主线程；Qt 控件不能在别的线程碰）
    _learn_refresh = pyqtSignal()

    # 初始
    def __init__(self):
        super().__init__()
        self._request_dialog.connect(self.start_thread)
        self._pc_done.connect(self._on_pc_done)
        self._task_status.connect(self._on_worker_status)
        self._task_finish.connect(self._on_task_finish)
        self._learn_refresh.connect(self._do_refresh_learn_window)
        # 文字
        self.full_text = ""  # 打字机效果用到的整体字符串
        from pets.pet_registry import get_pet_config, get_fgimages_dir
        _pet_cfg = get_pet_config()
        self.pet_name = _pet_cfg.get("name", "丛雨")  # 宠物名称（从角色包读取）
        self._pet_display_name = _pet_cfg.get("display_name", self.pet_name)
        # 立绘前缀：model.fgimages_prefix → portrait.prefix → 角色ID（绝不为空）
        # ⚠ 老版本新建向导可能把前缀写成空串 → 这里会退回「ムラサメ」→ 找不到索引 →
        #   桌宠启动时合成立绘抛异常 → 窗口根本不出现。改为统一解析。
        try:
            from pets.pet_registry import get_fgimages_prefix
            self._fgimages_prefix = get_fgimages_prefix()
        except Exception:
            self._fgimages_prefix = _pet_cfg.get("model", {}).get("fgimages_prefix", "")
        self._fgimages_sets = _pet_cfg.get("model", {}).get("fgimages_sets", [])
        try:      # 自己的角色 ID（右键菜单/换装都按这个角色取选项表）
            from pets.pet_registry import get_active_pet_id as _self_pid
            self._pet_id = _self_pid()
        except Exception:
            self._pet_id = ""
        # 立绘类型：single（每个表情一张整图）/ layers（多图层合成，如丛雨）
        try:
            from pets.pet_registry import get_portrait_mode, get_portrait_default_layers
            self._portrait_mode = get_portrait_mode()
            self._single_default_layers = get_portrait_default_layers()
        except Exception:
            self._portrait_mode, self._single_default_layers = "layers", []
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
        # 对话框区域（归一化 0~1：x, y, w, h，相对窗口）——新建向导 / 桌宠设置里可视化调节；
        # 2D 与 Live2D 各自独立：text_box_2d / text_box_live2d（旧键 text_box 兼容）
        try:
            _inter = _pet_cfg.get("interaction", {}) or {}
            self._text_box_2d = _inter.get("text_box_2d") or _inter.get("text_box") or None
            self._text_box_lv = _inter.get("text_box_live2d") or _inter.get("text_box") or None
            _tb = (self._text_box_lv if getattr(self, "_default_display", "2d") == "live2d"
                   else self._text_box_2d)
            self._text_box = [float(v) for v in _tb] if (_tb and len(_tb) == 4) else None
        except Exception:
            self._text_box, self._text_box_2d, self._text_box_lv = None, None, None
        # 字号缩放（2D / Live2D 各自独立；旧的 text_font_scale 兼容）
        try:
            _inter = _pet_cfg.get("interaction", {}) or {}
            _fs2 = _inter.get("text_font_scale_2d", _inter.get("text_font_scale", 1.0))
            _fsl = _inter.get("text_font_scale_live2d", _inter.get("text_font_scale", 1.0))
            self._font_scale_2d = float(_fs2 or 1.0)
            self._font_scale_lv = float(_fsl or 1.0)
            self._text_font_scale_cfg = (self._font_scale_lv
                                         if getattr(self, "_default_display", "2d") == "live2d"
                                         else self._font_scale_2d)
        except Exception:
            self._text_font_scale_cfg = 1.0
        # 字体 = 文字区宽度 × 该比例（0.0295 ≈ 丛雨原值 12px/406px）→ 换角色不跑偏
        self._font_ratio = 0.0295

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
        self.setAttribute(Qt.WA_InputMethodEnabled, False)  # 输入法只在输入模式里开启（见 _set_ime）
        self.setFocus()
        # 鼠标事件
        self.touch_head = False  # 兼容旧字段（头部区域 = 触摸区域之一）
        self.head_press_x = None  # 按下头部时的横坐标，用来判断是否“晃动”
        self.offset = None  # 中键拖动时记录的偏移量
        # ── 触摸互动（头 / 胸口 / 小腹 / 下体 / 大腿 / 小腿 / 脚 / 胳膊 / 手掌）──
        # 区域是归一化矩形（0~1，相对桌宠窗口），可在「立绘工坊 / 新建向导 → 触摸互动」里
        # 自由拖动缩放；这里按同一套坐标做命中判定。
        try:
            from tool.touch_areas import get_pet_areas, touch_enabled
            from pets.pet_registry import get_active_pet_id as _act_pid
            _pid = _act_pid()
            self._touch_pid = _pid
            # 2D 与 Live2D 两套区域各自独立
            self._touch_sets = {"2d": get_pet_areas(_pid, "2d"),
                                "live2d": get_pet_areas(_pid, "live2d")}
            self._touch_disabled = {}
            from tool.touch_areas import get_disabled as _gd
            self._touch_disabled = {"2d": set(_gd(_pid, "2d")),
                                    "live2d": set(_gd(_pid, "live2d"))}
            self._touch_areas = self._touch_sets[self._touch_mode_key()]
            self._touch_enabled = touch_enabled(_pid)
        except Exception as _e:
            print(f"[桌宠] ⚠ 读取触摸区域失败（用默认）: {_e}")
            self._touch_sets = {"2d": {}, "live2d": {}}
            self._touch_disabled = {"2d": set(), "live2d": set()}
            self._touch_areas = {}
            self._touch_enabled = True
        self._touch_hit = ""          # 本次按下命中的区域
        self._touch_press = None      # 按下坐标（用来区分轻点 / 抚摸）
        self._touch_fired = False     # 本次按下是否已经触发过（每次按压只触发一次反应）

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
        # Qt 默认只在按住鼠标键时才送 mouseMoveEvent，不打开这一项，
        # 「鼠标移到对话框上给提示」永远不会触发（用户反馈没提示）
        try:
            self.setMouseTracking(True)
        except Exception:
            pass
        # ── 立绘右上角的两个快捷按钮（对话 / 菜单）──
        self._ui_hover = ""
        self._ui_press = ""
        self._ui_anim_v = 0.0          # 悬停动画进度 0~1
        self._ui_anim_obj = None
        self._ui_pix = {}
        self._ui_btn_rects = {}
        self._ui_enabled = self._quick_buttons_enabled()
        self._ui_btns = {}
        try:
            for _nm in ("chat", "menu"):
                _b = PetQuickButton(_nm, 44, self)
                _b.hide()
                self._ui_btns[_nm] = _b
            self._ui_btns["chat"].clicked.connect(self._toggle_input_mode)
            self._ui_btns["menu"].clicked.connect(lambda: self._show_outfit_menu(QCursor.pos()))
        except Exception as _e:
            print(f"[桌宠] ⚠ 创建快捷按钮失败: {_e}")
        self._sync_quick_buttons()
        # 悬停提示改用"全局轮询光标位置"：本窗口是 Tool + 半透明分层窗口，
        # 非激活状态下鼠标事件不可靠（用户反馈"必须先点一下桌宠才提示"）。
        # 轮询 QCursor.pos() 与窗口激活无关，任何时候都能提示。
        try:
            self._hover_timer = QTimer(self)
            self._hover_timer.setInterval(300)
            self._hover_timer.timeout.connect(self._poll_hover)
            self._hover_timer.start()
        except Exception:
            pass
        self.setAttribute(Qt.WA_TranslucentBackground, True)  # 让整个窗口支持透明区域
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)  # Live2D 文字层显示时不抢键盘焦点
        from pets.pet_registry import get_portrait_prompts
        _pp = get_portrait_prompts()
        self._portrait_sets = _pp.get("sets", {}) or {}
        # 启动用哪套立绘：以「立绘工坊 / 右键菜单」保存的 active 套为准（与 QQ 立绘一致）
        _disp = portrait_type
        try:
            from tool.portrait_outfit import active_set
            _disp = active_set() or portrait_type
        except Exception:
            pass
        # active 是全局设置（可能停在别的角色的 b 套）→ 角色没这成套素材时回落到自己有的一套，
        # 否则会去找 {prefix}b.txt（不存在）→ 立绘一直空白
        try:
            _avail = [str(s) for s in (self._fgimages_sets or [])]
            if self._has_fgimages:
                # ★ 声明可能过时：natsume 的 pet.json 只写了 ['a']，但 b 套素材（76 个图层）其实
                #   齐全 → 每次启动都被强制切到 a，而 AI/保存的装扮按 b 给 ID → 立绘缺图层。
                #   所以以磁盘上真实存在的清单文件为准做并集（谁在磁盘上有 {prefix}X.txt 谁就可用）。
                try:
                    _dir = get_fgimages_dir()
                    _disk = {f[len(self._fgimages_prefix):-4] for f in os.listdir(_dir)
                             if f.startswith(self._fgimages_prefix) and f.endswith(".txt")}
                    _disk = {d for d in _disk if d}
                    if _disk:
                        _avail = [s for s in dict.fromkeys(_avail + sorted(_disk))]
                except Exception:
                    pass
            if _avail and _disp not in _avail:
                print(f"[桌宠] ℹ 角色没有 {_disp} 套立绘（可用: {_avail}）→ 改用 {_avail[0]}")
                _disp = _avail[0]
        except Exception:
            pass
        if _disp != portrait_type:
            self._sync_config_portrait(_disp)
        _set_pp = self._portrait_sets.get(_disp, {})
        self.first_portrait = _set_pp.get("first_portrait", [1715, 1306, 1719])
        # ★ 启动优先用「立绘工坊保存的那套装扮」（服装/动作/装饰/表情都算），
        #   拿不到才退回角色包的 first_portrait（那只是素材里的第一件衣服，芦花会变成内衣）
        try:
            from tool.portrait_outfit import saved_layer_list
            _saved_layers = saved_layer_list(_disp, self._pet_id)
            if _saved_layers:
                print(f"[桌宠] 👗 启动立绘 = 保存的装扮 {_saved_layers}")
                self.first_portrait = list(_saved_layers)
        except Exception as _e:
            print(f"[桌宠] ⚠ 读取保存的装扮失败: {_e}")
        if self._portrait_mode == "single" and self._single_default_layers:
            # 单图模式（每个表情一张整图）：启动就显示角色的默认表情整图，
            # 不能用丛雨的 first_portrait（那些图层 ID 在新角色包里不存在 → 空白）
            self.first_portrait = list(self._single_default_layers)
        self.portrait_target = f"{self._fgimages_prefix}{_disp}"
        # 当前显示的立绘体系（a/b）—— 回复时可能按概率临时切换（灵动效果，不写配置）
        self._display_set = _disp
        self._fade_id = 0
        self._fade_state = None
        self._portrait_ready = not self._has_fgimages   # 无 2D 素材（纯 Live2D）直接算就绪
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
        # 顺带：她空闲时把攒下的状态文字（"正在操作电脑……"）显示出来 —— 用户要求
        # "等他说完话再显示正在进行某某操作"
        self.idle_timer.timeout.connect(self._flush_pending_status)
        self.idle_timer.start()

        # 自主学习 / 电脑近况：每 4 分钟看一眼（内部自己限速：≥20 分钟才动手、
        # 主人刚说完话或她正忙就跳过；都在后台线程，界面不会卡）
        self._last_user_ts = 0.0
        self._reply_active = False     # 整轮回复进行中（on_reply 开始→结束）
        self._pending_status = ""      # 攒下的状态文字（等她说完再显示）
        self._chatter_turn = False     # 当前这一轮是不是她自己发起的碎碎念
        self._last_pc_narrate = 0.0
        self._learn_timer = QTimer(self)
        self._learn_timer.setInterval(4 * 60 * 1000)
        self._learn_timer.timeout.connect(self._learn_tick)
        self._learn_timer.start()

        # 电脑操作"做完了说一句"：Worker 线程里发信号 → 主线程让她说一句
        try:
            from tool import pc_control as _pcn
            _pcn.set_narrator(lambda acts: self._pc_done.emit(_pcn.describe(acts)))
        except Exception as _en:
            print(f"[桌宠] ⚠ 注册操作完成回调失败: {_en}")
        # 性能：桌宠平时就跑在"低于正常"优先级，别和主人正在用的程序抢 CPU
        try:
            from tool import perf_guard as _pg0
            _pg0.set_process_priority(False)
        except Exception:
            pass
        # 任务循环（连着做完一件事）的状态与收尾 → 也走信号回主线程
        try:
            from tool import pc_task as _ptn
            _ptn.set_ui(status=lambda s: self._task_status.emit(str(s)),
                        finish=lambda s, ok=True: self._task_finish.emit(str(s), bool(ok)),
                        say=lambda s: self._say_progress(str(s)))
        except Exception as _etn:
            print(f"[桌宠] ⚠ 注册任务循环回调失败: {_etn}")
            print(f"[桌宠] ⚠ 注册游戏回调失败: {_egn}")

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
        """启动后是否自动进入 Live2D 模式。

        ① 角色 pet.json 写了 model.default=live2d → 是
        ② 设置里「启用 Live2D」(config.live2d_enabled=true) 且角色有模型 → 是
           （用户打开总开关就是希望桌宠用 Live2D，不该被 pet.json 的 default=2d 挡住）
        """
        if self._default_display == "live2d":
            return True
        try:
            if str(CONFIG.get("live2d_enabled", "false")).lower() == "true":
                from pets.pet_registry import get_live2d_model_json
                if get_live2d_model_json():
                    print("[Live2D] 设置里已启用 Live2D 且角色有模型 → 启动即进入 Live2D")
                    return True
        except Exception:
            pass
        return False

    # =========================================================
    # Live2D 文字层（透明覆盖层，行为对齐 2D：文字常显、不挡模型交互）
    # =========================================================

    def is_live2d_overlay_visible(self) -> bool:
        return bool(getattr(self, "_overlay_visible", False))

    def _set_overlay_click_through(self, enabled: bool):
        """文字层点击穿透（Windows WS_EX_TRANSPARENT）：鼠标点击穿过文字层直达 Live2D 模型

        ⚠ 只有 Live2D 模式才允许开：普通 2D 模式下开这个 = 把桌宠自己的窗口变成
          鼠标穿透，点它、点按钮全都没反应，而且没有路径会关回来
          （用户反馈"有时候点不了桌宠和按钮"，实测那时窗口扩展样式是 0x800A8）。
        """
        if enabled and not getattr(self, "_live2d_mode", False):
            return
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
        # 2D 立绘模式下锁过窗口尺寸 → 进 Live2D 前解开，否则这里 resize 不动
        try:
            self.setMinimumSize(0, 0)
            self.setMaximumSize(16777215, 16777215)
        except Exception:
            pass
        self.resize(w.size())
        # 字号随模型窗口尺寸 + 角色 font_scale 缩放（修复"字体大得离谱"）
        try:
            base_h = 900.0
            self._current_scale = max(0.15, min(2.0, (w.height() / base_h) * self._live2d_font_scale))
            # F9 调参改的是 _live2d_font_scale → 同步成实时字号，文字层跟着变（且不会被重算回去）
            if getattr(self, "_font_scale_live", None) is None:
                self._font_scale_live = float(self._live2d_font_scale or 1.0)
            self._update_text_scaling()
            self._rewrap_current_text()
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
            # 模型名/API Key 统一走 longtext.model_config（longtext_model + longtext_model_name）
            from longtext.model_config import get_longtext_model_config
            mcfg = get_longtext_model_config()
            if mcfg:
                api_key = mcfg["api_key"]
                chat_model = mcfg["model"]
            else:
                cfg = get_config("./config.json")
                api_key = cfg.get("APIKEY", {}).get("qwen", "")
                chat_model = "qwen-plus"
            self._longtext_manager = LongTextManager(api_key=api_key, chat_model=chat_model)
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
        self._show_thinking(role == "user")   # 只有主人发起才显示"思考中"
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
        if self.is_busy_reply():          # 她还在思考/说话 → 不接受新的对话
            self._show_busy_hint()
            self._set_ime(False)
            print("[桌宠] ⏳ 她还在思考/说话，先别插话（已忽略这次点击）")
            return
        if self.input_mode:
            # 已经在打字了：再点一下只是重新聚焦，别清掉已经打的字（用户反馈）
            self.setFocus()
            self.update()
            return
        self.input_mode = True
        self._set_ime(True)
        self.input_buffer = ""
        self.preedit_text = ""
        self.display_text = ("【" + str(self.user_name) + "】\n可以直接打字了，输入后按回车发送（Esc 取消）")

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
        # 配置里关掉 Live2D 时，任何入口（快捷键/AI 指令/启动器按钮）都不许打开：
        # ⚠ 个别机器上 Live2D 的 GL 初始化会直接把进程干掉（表现为「桌宠突然消失」）
        try:
            if str(get_config("./config.json").get("live2d_enabled", "false")).lower() != "true":
                self.show_text(f"Live2D 已在设置里关闭（想用请到启动器「设置 → 桌宠配置」打开）", typing=False)
                print("[Live2D] 配置 live2d_enabled=false → 拒绝切换（避免个别机器上 GL 初始化崩溃）")
                return
        except Exception:
            pass
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
                    # 安全解析：记忆/历史文件可能被改坏或被注入，绝不能用 eval（任意代码执行）
                    import ast
                    try:
                        saved = ast.literal_eval(saved)
                    except Exception:
                        saved = None
                if saved is None:
                    saved = self.first_portrait
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
        # stop_voice=False：不掐断正在念的句子（点她/点对话框/系统切焦点都会触发本事件）
        if not self.is_dnd_enabled():
            self.pause_all_ai(stop_voice=False)
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
                # 视觉模型统一走 longtext.model_config（vision_model_name + 对应 API Key）
                from longtext.model_config import get_vision_model_config
                vcfg = get_vision_model_config()
                if not vcfg:
                    return

                # AI 视觉描述
                payload = {
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": url}},
                            {"type": "text", "text": "请用简短的中文描述这张照片中的场景、人物和主要活动，不超过50个字。"},
                        ]
                    }],
                    "model": vcfg["model"],
                    "max_tokens": 256,
                    "stream": False,
                }
                headers = {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {vcfg['api_key']}",
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

    def on_screenshot_captured(self, image_path, shot_hash: int = 0):
        # 勿扰模式下完全忽略截图结果
        if self.is_dnd_enabled():
            try:
                os.remove(image_path)
            except Exception:
                pass
            return
        model_type = get_config("./config.json")["model_type"]

        def task(path, _hash):
            def _emit_reply(desc, reused: bool = False):
                """把描述发回主线程让她开口（reused=True 表示屏幕没变、复用上次描述）"""
                _tag = "（屏幕和上次一样，没有变化）" if reused else ""
                propmt = (
                    "【重要系统指令】你刚刚通过屏幕截图看到了主人当前的真实状态。"
                    "以下是对主人屏幕内容的描述，这是你亲眼所见的事实，你必须围绕这个内容展开对话：\n"
                    "=== 屏幕内容描述开始 ===\n"
                    f"{desc}\n"
                    "=== 屏幕内容描述结束 ===\n"
                    f"{_tag}"
                    f"（截图里那个桌宠窗口就是你本人，不是别人。）"
                    f"请以{self.pet_name}的身份，自然地观察并评论主人正在做什么。你的回复必须紧密围绕上述描述，"
                    "可以表达关心、好奇、或撒娇——但要让人感觉你真的看到了主人的屏幕。"
                    "如果屏幕和上次一样，就别说重复的话，可以聊点别的或者只是陪着。"
                    "只输出你自己要说的话（JSON 数组），不要写「主人：」也不要替主人说话，不要续写下一轮。"
                )
                try:                      # 记下"她最近聊过"，屏幕没变时用来避免连着复读
                    _h, _d, _t, _ = getattr(self, "_last_shot_info", (0, "", 0.0, 0.0))
                    self._last_shot_info = (_h or int(_hash or 0), _d or str(desc or ""), _t, time.time())
                except Exception:
                    pass
                self._request_dialog.emit(propmt, "system", True)

            try:
                # 长文本输出中 → 直接丢弃（不调用视觉 API，节省资源；finally 会删临时截图）
                if self.long_text_mode and self._stream_playing:
                    print("[AIpet] 长文本输出中，跳过截图识别")
                    return
                # ── 屏幕没变就别再跑一次视觉（省显卡、也省时间）──
                #   实测：每 150 秒重描述一遍没变的屏幕，视觉要占显卡 10 秒以上，
                #   还会和语音合成抢显卡（语音被拖到 25 秒）。指纹一样就复用上次描述：
                #   · 刚评论过（3 分钟内）→ 这轮什么都不做
                #   · 久没说话了 → 复用描述、正常评论（不用再识别）
                try:
                    from tool.screen_capture import hash_distance
                    _ph, _pdesc, _pts, _ptalk = getattr(self, "_last_shot_info", (0, "", 0.0, 0.0))
                    _same = (_hash and _ph and hash_distance(_hash, _ph) <= 12)
                    if _same:
                        _age = time.time() - float(_pts or 0)
                        _since_talk = time.time() - float(_ptalk or 0)
                        if _since_talk < 180:
                            print("[AIpet] 屏幕没变化，刚聊过 → 这轮不打扰（也没占用显卡）")
                            return
                        if _pdesc and _age < 900:
                            print(f"[AIpet] 屏幕没变化 → 复用上次描述（省一次视觉识别，{_age:.0f} 秒前看的）")
                            _emit_reply(_pdesc, reused=True)
                            return
                except Exception as _he:
                    print(f"[AIpet] ⚠ 画面比对失败（照常识别）: {_he}")

                # 正在思考/说话时先不识别：视觉要占显卡十几秒，而这一轮回复的语音合成
                # 同样要用显卡 → 抢起来会让回复变成等好几分钟。但**不丢弃**：让她稍后重试。
                try:
                    if self.is_busy_reply() or getattr(self, "_screen_look_busy", False):
                        print("[AIpet] 她正在回复中 → 本轮屏幕识别稍后重试（不丢）")
                        try:
                            if self._screenshot_worker is not None:
                                self._screenshot_worker.wake(delay=8.0)
                        except Exception:
                            pass
                        return
                except Exception:
                    pass
                # ── 开口时机打分（心情 / 多久没说话 / 这一小时说过几次 / 屏幕变化）──
                #    分数不够就连视觉识别都不跑：省显卡，也免得变成话痨。
                try:
                    from tool import attention as _att, screen_capture as _sc2
                    _dist = None
                    try:
                        _ph, _pd, _pt, _pk = getattr(self, "_last_shot_info", (0, "", 0.0, 0.0))
                        if _hash and _ph:
                            _dist = _sc2.hash_distance(_hash, _ph)
                    except Exception:
                        pass
                    _ok2, _sc3, _why2 = _att.should_speak(screen_change_bits=_dist)
                    try:
                        from tool import care as _c3
                        if _ok2 and _c3.quiet_now():
                            _ok2, _why2 = False, "会议/演示中，保持安静"
                    except Exception:
                        pass
                    print(f"[AIpet] 看屏幕后开口评分 {_sc3:.1f}（{_why2}）→ {'开口' if _ok2 else '安静陪着'}")
                    if not _ok2:
                        return
                except Exception as _ea2:
                    print(f"[AIpet] ⚠ 开口评分失败（照常）: {_ea2}")

                try:
                    # ★ 视觉走哪边由设置决定（视觉模型来源：本地服务 / 云端 API），
                    #   以前只看对话模型 model_type，装不了本地视觉就没得选。
                    if self.force_stop:
                        print("[vision] 已中断生成")
                        return
                    desc = describe_image(path, max_side=vision_fast_size(), max_new=vision_fast_tokens())
                    if self.force_stop:
                        print("屏幕回复 已中断生成")
                        return
                    # 记住这一屏的描述与指纹：屏幕没变时下次直接复用（省一次视觉识别）
                    try:
                        self._last_shot_info = (int(_hash or 0), str(desc or ""),
                                               time.time(), time.time())
                    except Exception:
                        pass
                    # 跨线程安全：发信号回主线程触发对话
                    _emit_reply(desc)
                except Exception as e:
                    print(f"[AIpet] 截图分析失败: {e}")
            finally:
                try:
                    os.remove(path)
                except Exception:
                    pass

        self._screenshot_executor.submit(task, image_path, int(shot_hash or 0))

    def pause_all_ai(self, stop_voice: bool = True):
        """用户输入/点击桌宠时：停止截图线程；stop_voice=True 时一并中断语音播放。

        ★ stop_voice=False 用于「窗口获得焦点」这类被动触发：只暂停自动行为
          （截图/空闲检测），不掐断正在念的那句话。
          以前一律 QSound.stop()：点她、点对话框、系统把焦点切过来都会走到这里
          → 正在念的句子被半路掐掉，而句子队列照常往下走，听起来就是
          「有的句子/几个字没声」，而且是随机的（用户反馈）。
        """
        self.force_stop = True  # 启用软中断标记

        if self._screenshot_worker and self._screenshot_worker.isRunning():
            print("[AIpet] 暂停截图线程")
            self.stop_screenshot_worker()
        # 不再中断 worker — 对话让它自然播完
        # 用户主动输入会通过 start_thread(t=False) 正常打断
        if stop_voice:
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

    def _file_read_and_reply(self, request, user_text):
        """真的去翻她要看的东西，然后把内容交给她接着说（后台线程，别卡界面）"""
        try:
            from tool import file_access as _fa
            content = _fa.run([request])
            if not str(content or "").strip():
                content = "（没看到什么东西）"
            print(f"[桌宠] 📂 翻完了（{len(str(content))} 字）→ 带着内容回答主人")
            prompt = ("【系统指令】你刚刚真的翻开了主人电脑里的东西，下面是你亲眼看到的："
                      + chr(10) + "=== 看到的内容开始 ===" + chr(10)
                      + str(content)[:3500] + chr(10) + "=== 看到的内容结束 ===" + chr(10)
                      + f"主人刚才说：「{user_text}」。请用你自己的口吻自然地跟他说说你看到了什么，"
                        "挑重点说、别念条目、别说'文件显示'、别提系统提示，回答简短一些。")
            self._request_dialog.emit(prompt, "user", False)
        except Exception as e:
            print(f"[桌宠] ⚠ 看文件失败（{type(e).__name__}: {e}）→ 退回普通回答")
            try:
                self._request_dialog.emit(str(user_text), "user", False)
            except Exception:
                pass

    def _music_and_reply(self, request):
        """真的去网易云点歌（搜索+播放+标题校验），再把结果交给她说给主人听（后台线程）"""
        try:
            from tool import music as _mu
            result = _mu.run(str(request or "")) or "唔……我没看懂要放哪首。"
            print(f"[桌宠] 🎵 点歌结果：{result}")
            self._request_dialog.emit(
                "（系统提示：你刚才去网易云点歌，真实结果是——" + str(result) +
                "。用你自己的口吻把结果说给主人听，只输出你要说的那一两句，"
                "别念坐标、别提系统提示。）", "user", False)
        except Exception as e:
            print(f"[桌宠] ⚠ 点歌失败（{type(e).__name__}: {e}）")
            try:
                self._request_dialog.emit("唔……我点歌的时候卡住了，你再试一次？", "user", False)
            except Exception:
                pass

    def _plugin_and_reply(self, marker, arg):
        """跑一个插件（后台线程），把结果交给她用自己的话讲"""
        try:
            from tool import plugins as _plg
            res = _plg.run_one(str(marker), str(arg))
            if not res:
                res = f"（插件「{marker}」没给我结果，可能没装或出错了）"
            print(f"[桌宠] 🧩 插件结果：{str(res)[:70]}")
            self._request_dialog.emit(
                "（系统提示：你刚才用插件「" + str(marker) + "」做了件事，结果是——"
                + str(res)[:1200] +
                "。用你自己的口吻讲给主人听，一两句话，别说'插件'两个字，也别提系统提示。）",
                "user", False)
        except Exception as e:
            print(f"[桌宠] ⚠ 插件执行失败（{type(e).__name__}: {e}）")
            try:
                self._request_dialog.emit("唔……我那个小工具好像坏了。", "user", False)
            except Exception:
                pass

    def _notify(self, title, text):
        """弹一条 Windows 系统通知（托盘气泡）。

        为什么要有：她说话只在对话框里，主人切到别的窗口（或全屏）就看不见了。
        提醒、久坐关怀这类"该被看见"的事，顺手弹一条系统通知。
        config 的 system_notify 可以关（设成 false）。
        """
        try:
            from tool.config import get_config
            v = str(get_config("./config.json").get("system_notify", "true")).lower()
            if v in ("false", "0", "off", "no"):
                return
            t = getattr(self, "_tray", None)
            if t is None or not t.isVisible():
                return
            from PyQt5.QtWidgets import QSystemTrayIcon
            t.showMessage(str(title)[:40], str(text)[:180], QSystemTrayIcon.Information, 6000)
        except Exception as e:
            print(f"[桌宠] ⚠ 系统通知失败: {e}")

    def _search_and_reply(self, query, user_text):
        """真的去搜（后台线程），再把结果交给她用自己的话讲"""
        try:
            from tool import web_search as _wsm
            ctx = _wsm.context_text(str(query), limit=5)
            if not ctx:
                print("[桌宠] 🔍 没搜到结果 → 如实告诉她")
                self._request_dialog.emit(
                    "（系统提示：你刚想上网查「" + str(query)[:40] + "」，但没搜到结果。"
                    "如实跟主人说没查到，别编。）", "user", False)
                return
            print(f"[桌宠] 🔍 搜到 {ctx.count(chr(10) + '1. ') or 1} 组结果 → 带着它回答主人")
            self._request_dialog.emit(
                ctx + chr(10) + f"主人刚才说：「{user_text}」。"
                "请用你自己的口吻把查到的讲给他听：挑重点、说人话，"
                "别说'根据搜索结果'，别提系统提示；不确定的地方就说没查到。", "user", False)
        except Exception as e:
            print(f"[桌宠] ⚠ 搜索失败（{type(e).__name__}: {e}）")
            try:
                self._request_dialog.emit(str(user_text), "user", False)
            except Exception:
                pass

    def _cycle_autonomy(self):
        """菜单：切自主活跃度（安静 → 适中 → 活跃）"""
        try:
            from tool import desire as _dz3
            nxt = _dz3.next_level()
            if _dz3.set_level(nxt):
                self.show_text("唔……那我自己看着办的程度调成「%s」了。" % _dz3.level_label(),
                               typing=False)
        except Exception as e:
            print(f"[桌宠] ⚠ 切换活跃度失败: {e}")

    def _show_learned(self):
        """菜单：看看她的状态 / 记忆 / 提醒（剧情模式风格的独立窗口，不占对话框）"""
        try:
            from classes.status_window import show_status_window
            # parent 传 None：这扇窗是独立的（不跟着桌宠窗口一起最小化/置顶，
            # 任务栏里有自己的条目）；模块里持有单例，不会被回收。
            show_status_window(None, on_study=lambda: self._study_now(silent=True))
            try:
                from tool import self_learn as _sl
                print(f"[学习] 记忆窗口已打开（{_sl._store_path()}）")
            except Exception:
                pass
        except Exception as e:
            print(f"[学习] ⚠ 打开记忆窗口失败: {e}")

    def _study_now(self, silent: bool = False):
        """菜单/窗口：让她现在学点什么（立刻自习一次）"""
        try:
            from tool import self_learn as _sl
            if not _sl.enabled():
                print("[学习] 自主学习没开 → 先去菜单打开")
                if not silent:
                    self.show_text("先打开「自主学习」我才能自己学哦。", typing=True)
                return
            if not silent:
                self.show_text("唔……那我去看看书。", typing=True)
            import threading as _thl
            _thl.Thread(target=self._learn_cycle, kwargs={"force": True}, daemon=True).start()
        except Exception as e:
            print(f"[学习] ⚠ 立即自习失败: {e}")

    def _on_worker_status(self, text):
        """Worker/任务循环报告"正在操作电脑……" → 在对话框显示一行状态（她不是哑巴）。

        ★ 用户要求：「应该等他说完话再显示正在进行某某操作」——
          她正在说话/思考时，状态文字**先存起来**，等她这一轮说完再显示；
          否则那句话会把她的台词直接挤掉（实测就是这样）。
        """
        try:
            t = str(text or "").strip()
            if not t:
                # ★ 空状态 = 循环结束了 → 把对话框还给她上一句话
                #   （用户反馈："游戏都没了对话框还显示正在玩游戏"）
                try:
                    if not self.is_busy_reply():
                        self.show_text(str(getattr(self, "full_text", "") or ""), typing=False)
                except Exception:
                    pass
                return
            if self.is_busy_reply():
                self._pending_status = t
                return
            self.show_text(t, typing=False)
        except Exception:
            pass

    def _flush_pending_status(self):
        """（主线程定时器调用）她空闲了、且有攒下的状态文字 → 显示出来"""
        try:
            t = getattr(self, "_pending_status", "")
            if not t:
                return
            if self.is_busy_reply():
                return
            self._pending_status = ""
            self.show_text(str(t), typing=False)
        except Exception:
            pass

    def _say_progress(self, text):
        """玩游戏 / 操控电脑的过程中**时不时说一句**（用户要求：别当哑巴）。

        流程：循环里她顺口写的那句（游戏/任务的规划器会给一个【说】标记）→
        走一遍正常对话管线（有台词、有立绘、有语音），但**只让她说这一句**。
        注意提示词以「（系统提示：」开头 —— start_thread 会据此认定"这不是主人开口"，
        不会把她自己发起的这句当成主人说话、把游戏停下来。
        """
        try:
            text = str(text or "").strip()
            if not text:
                return
            print(f"[桌宠] 💬 过程中的一句：{text[:50]}")
            self._chatter_turn = True      # 标记：这条是她自己发起的（主人说话要优先打断它）
            self._request_dialog.emit(
                "（系统提示：你正在替主人玩游戏/操作电脑，刚刚做到：" + text +
                "。顺手用你自己的口吻**很短**地说一句（十个字左右就行，别念这句提示、"
                "别提坐标、别停下手里的事）。）", "system", True)
        except Exception as e:
            print(f"[桌宠] ⚠ 过程说话失败: {e}")

    def _on_task_finish(self, text, ok):
        """任务循环结束 → 让她把那句总结说出口（有语音、有台词，不是哑巴）"""
        try:
            text = str(text or "").strip()
            if not text:
                return
            print(f"[桌宠] 🏁 任务结束（{'完成' if ok else '没做完'}）：{text[:70]}")
            # 主人可能不在电脑前（超过 2 分钟没说话）→ 顺手弹个系统通知，他回来能看见
            try:
                if time.time() - float(getattr(self, "_last_user_ts", 0.0) or 0.0) > 120.0:
                    self._notify("她说", text)
            except Exception:
                pass
            self._request_dialog.emit(
                "（系统提示：你刚刚亲手把这件事做到这里——" + text +
                "。现在用你自己的口吻把结果说给主人听：只输出你要说的那一句（一两句就好），"
                "别念坐标、别提系统提示、别再说要动手了。）", "user", False)
        except Exception as e:
            print(f"[桌宠] ⚠ 任务收尾失败: {e}")

    # 主人叫停用的关键词（只有短句才算叫停，长句里出现「停」是别的意思）
    _STOP_WORDS = ("停", "停下", "停止", "别动", "别点了", "别弄了", "别操控", "算了",
                   "不用了", "收手", "回来吧", "别点了", "停吧", "停下吧")

    def _is_stop_command(self, text) -> bool:
        try:
            t = str(text or "").strip()
            if not t or len(t) > 14:
                return False
            return any(w in t for w in self._STOP_WORDS)
        except Exception:
            return False

    def _on_pc_done(self, desc):
        """她真的把电脑操作做完了 → 让她用一句话说说自己干了什么 / 接下来想干什么

        ⚠ 任务循环在跑的时候不汇报：那一批是任务中间的一步，说早了会打断她，
        而且任务结束时本来就会统一收尾（否则每步都插一轮对话，又慢又吵）。
        """
        try:
            desc = str(desc or "")
            if not desc:
                return
            print(f"[桌宠] ✅ 电脑操作完成：{desc}")
            try:
                from tool import pc_task as _pt3
                if _pt3.running():
                    print("[桌宠] （任务进行中，这一批不单独汇报）")
                    return
            except Exception:
                pass
            import time as _t3
            if _t3.time() - float(getattr(self, "_last_pc_narrate", 0) or 0) < 8:
                return                       # 别连着刷（同一批动作只汇报一次）
            self._last_pc_narrate = _t3.time()
            # ⚠ 这一轮按「主人派下来的活」算（role="user"）：用 system 会被当成自主行动，
            #   她接着想再动一步就会被 1 分钟的自主间隔拦住（"事情做到一半做不下去"）。
            self._request_dialog.emit(
                "（系统提示：你刚刚真的把电脑操作做完了——" + desc +
                "。用你自己的口吻跟主人说一句：说你做了什么、或者接下来还想干什么。"
                "一句话就够，别念坐标、别提系统提示、别重复刚才已经说过的话。"
                "如果这件事还没做完，现在可以接着做。）", "user", False)
        except Exception as e:
            print(f"[桌宠] ⚠ 操作完成汇报失败: {e}")

    def _model_ready(self) -> bool:
        """现在有可用的对话模型吗（自主学习要用）"""
        try:
            from tool.config import get_config
            mt = str(get_config("./config.json").get("model_type", "deepseek")).strip().lower()
            if mt == "local":
                return True
            from longtext.model_config import get_short_model_config
            return bool(get_short_model_config())
        except Exception:
            return False

    def _learn_cycle(self, force: bool = False):
        """后台跑一次自主学习（归纳 / 自习 / 日记）。force=True 忽略间隔。"""
        try:
            from tool import self_learn as _sl
            if not _sl.enabled():
                return
            if force:
                _sl._last_cycle[0] = 0.0
            what = _sl.maybe_cycle(self.history, getattr(self, "pet_name", "桌宠"),
                                   last_user_ts=float(getattr(self, "_last_user_ts", 0.0) or 0.0),
                                   has_model=self._model_ready())
            if not what:
                return
            print(f"[学习] 这一轮：{what}")
            # 结果只显示在「她的记忆与自学」窗口里，不占用对话框（用户要求）
            self._refresh_learn_window()
        except Exception as e:
            print(f"[学习] ⚠ 学习循环失败（{type(e).__name__}: {e}）")

    def _refresh_learn_window(self):
        """记忆窗口开着的话刷新一下内容

        ⚠ 这个方法会被后台线程调用（自主学习跑在线程里），所以**绝不能直接碰控件**：
          Qt 的控件只能在主线程访问，从别的线程去 isVisible()/setPlainText() 轻则乱码
          重则整个进程崩掉（实测有这种"桌宠凭空消失"）。这里只发个信号，让主线程去做。
        """
        try:
            self._learn_refresh.emit()
        except Exception:
            pass

    def _do_refresh_learn_window(self):
        """主线程里真正刷新窗口（由 _learn_refresh 信号触发）"""
        try:
            from classes.status_window import _window as _sw
            if _sw is not None and _sw.isVisible():
                _sw.refresh()
        except Exception:
            pass

    def _pc_info_tick(self):
        """采一次电脑近况，写进她的「观察」——她聊到相关话题时自然用得上（后台线程）"""
        try:
            from tool import pc_info as _pi
            # ★ 记录主人的习惯（常用软件）：只记"窗口标题出现次数"，不读内容，
            #   所以**不受**「允许读取电脑文件」开关影响（用户要求：自主学习要记习惯）。
            try:
                from tool import habits as _hb
                _hb.note_apps_block(_pi._running_apps())
            except Exception:
                pass
            from tool import file_access as _fa
            if not _fa.enabled():
                return
            txt = _pi.sample()
            if not txt:
                return
            print("[桌宠] " + txt[:140])
            self.history.append({
                "role": "system",
                "content": (txt + "（这些只是背景信息，主人没问起时不用特意汇报；"
                                   "聊到相关话题可以自然提一句。）"),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "priority": "high",
            })
            # 只留最近 2 条电脑近况，别把历史撑大
            old = [i for i, m in enumerate(self.history)
                   if isinstance(m, dict) and str(m.get("content", "")).startswith("【电脑近况】")]
            for i in old[:-2][::-1]:
                try:
                    self.history.pop(i)
                except Exception:
                    pass
        except Exception as e:
            print(f"[桌宠] ⚠ 电脑近况采集失败: {e}")

    def _learn_tick(self):
        """定时器：自主学习 + 电脑近况 + 主动关怀（都在后台线程，界面不卡）"""
        try:
            # ── 动机层：她自己"想做什么"（无聊/想说话/精力）──
            try:
                from tool import desire as _dz, state as _st8, care as _c8
                _talked = _st8.last_talk_ago() < 300
                _sh_changed = True
                try:
                    _ph, _pd, _pt, _pk = getattr(self, "_last_shot_info", (0, "", 0.0, 0.0))
                    _sh_changed = (time.time() - float(_pt or 0)) < 900
                except Exception:
                    pass
                _dz.tick(talked=_talked, screen_changed=_sh_changed)
                if not _c8.quiet_now() and not self.is_busy_reply():
                    _mp = None
                    try:
                        from tool import music as _mu8
                        if _mu8.uia_ready():
                            _mp = _mu8.is_playing(_mu8.find_window() or 0) if _mu8.find_window() else None
                    except Exception:
                        _mp = None
                    try:
                        _idle = get_idle_seconds()
                    except Exception:
                        _idle = None
                    _w = _dz.wants(music_playing=_mp, user_idle_sec=_idle)
                    if _w:
                        print(f"[桌宠] 💭 她自己想：{_w.get('text')}")
                        self._request_dialog.emit(_w.get("prompt") or "", "system", True)
                        return
            except Exception as _ed:
                print(f"[桌宠] ⚠ 动机检查失败: {_ed}")

            # 主动关怀：深夜/久坐（带冷却，不会唠叨）
            try:
                from tool import care as _care
                import time as _t4
                _now = _t4.time()
                if not getattr(self, "_session_start", 0):
                    self._session_start = _now
                _active = _now - float(self._session_start or _now)
                _why = _care.check(now_ts=_now, active_sec=_active)
                if _why:
                    print(f"[桌宠] 💗 主动关怀：{_why}")
                    self._notify("她说", _why)
                    self._request_dialog.emit(_care.nudge_prompt(_why, self.pet_name), "system", True)
            except Exception as _ec:
                print(f"[桌宠] ⚠ 关怀检查失败: {_ec}")
            # 连续使用时长：离开超过 10 分钟就重新计时
            try:
                import time as _t5
                if get_idle_seconds() > 600:
                    self._session_start = _t5.time()
            except Exception:
                pass
            if self.is_busy_reply() or getattr(self, "input_mode", False):
                return
            import threading as _th
            _th.Thread(target=self._learn_cycle, daemon=True).start()
            _th.Thread(target=self._pc_info_tick, daemon=True).start()
        except Exception:
            pass

    def check_idle_state(self):
        """检查系统空闲时间并在阈值上触发对话"""
        idle_seconds = get_idle_seconds()

        # ── 到点提醒：每 20 秒看一眼（1 秒一次太频繁，读文件不值当）──
        try:
            _n = int(getattr(self, "_rm_tick", 0) or 0) + 1
            self._rm_tick = _n
            if _n % 20 == 0:
                from tool import reminder as _rm2
                _due = _rm2.take_due()
                if _due:
                    _w = "；".join(str(x.get("what")) for x in _due[:3])
                    print(f"[桌宠] ⏰ 到点提醒：{_w}")
                    self._notify("提醒", _w)
                    self._request_dialog.emit(
                        "（系统提示：到点了，你该提醒主人这些事——" + _w +
                        "。用你自己的口吻说出来（一句话），可以顺便关心一句，别念标记。）",
                        "system", True)
        except Exception as _em:
            print(f"[桌宠] ⚠ 提醒检查失败: {_em}")

        # ── 游戏/全屏：只降优先级（主人要求屏幕识别与主动搭话都不许动）──
        try:
            from tool import perf_guard as _pg
            _g = _pg.game_mode()
            if _g != getattr(self, "_game_mode", None):
                self._game_mode = _g
                _pg.note_state(_g)
                if _g:
                    self._enter_game_mode()
                else:
                    self._exit_game_mode()
        except Exception as _eg:
            pass

        # ── 自愈①：非 Live2D 模式绝不该保持"点击穿透"（那会把整只桌宠变成点不到）──
        #    只要有任何一条路径误开了它，这里每秒都会把它关回来。
        try:
            if not self._live2d_mode and getattr(self, "_overlay_click_through", False):
                print("[桌宠] 🔧 检测到非 Live2D 模式还在点击穿透 → 已关闭（否则点不了桌宠）")
                self._set_overlay_click_through(False)
        except Exception:
            pass

        # ── 自愈②：没有在跑的线程、也没在放语音，却还挂着"她在说话" → 释放对话锁 ──
        #    否则点她只会得到"她还在说话/思考"，看起来就是"点不了"。
        try:
            _w = getattr(self, "worker", None)
            if ((_w is None or not _w.isRunning())
                    and self._talking and not getattr(self, "_stream_playing", False)):
                _since = float(getattr(self, "_busy_since", 0) or 0)
                if not _since:
                    self._busy_since = time.time()
                elif time.time() - _since > 30:
                    print("[桌宠] ⏱ 卡在「她还在说话」超过 30 秒 → 释放对话锁（点击恢复可用）")
                    self._busy_since = 0
                    self._clear_thinking_if_stuck()
            else:
                self._busy_since = 0
        except Exception:
            pass

        # 游戏/全屏期间也照常搭话、照常看屏幕（主人明确要求不改），这里不做任何跳过

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
                    "★ 这一轮只是寒暄：不要输出任何操作指令（【键鼠】等）。"
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
            # 开口时机打分（心情、多久没说话、屏幕变化、这一小时说过几次…）
            try:
                from tool import attention as _att, perf_guard as _pg
                _ok, _sc, _why = _att.should_speak(user_idle_sec=idle_seconds,
                                                   fullscreen=_pg.game_mode())
                try:
                    from tool import care as _c2
                    if _ok and _c2.quiet_now():
                        _ok = False
                        _why = "会议/演示中，保持安静"
                except Exception:
                    pass
                print(f"[AIpet] 空闲搭话评分 {_sc:.1f}（{_why}）→ {'开口' if _ok else '这次先不说'}")
                if not _ok:
                    self.idle_thinking_triggered = False   # 下次再评
                    return
            except Exception as _ea:
                print(f"[AIpet] ⚠ 开口评分失败（照常说）: {_ea}")
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
        # ★ 整轮回复进行中：这期间算"忙"（句与句之间的停顿也不算闲着），
        #   否则状态文字会在停顿里挤进来，把她还没说完的对话顶掉（用户反馈）。
        self._reply_active = True
        self.portrait_history = portrait_history
        self.history = history
        self._save_history()
        # 逐句情绪标签（qwen-emotion 输出）——Live2D 表情/动作联动的数据源
        self._last_emotion_list = emotion_list or []
        # 每轮回复重新开始情绪追踪（保证第一句总能触发动作）
        self._live2d_emotion_name = None

        # Live2D 模式下显示透明文字层（点击穿透，不抢焦点）
        self._ensure_live2d_overlay()

        # ── 她自己要求看屏幕（提示词里教她：需要画面时只输出【看屏幕】）──
        try:
            from tool.screen_intent import SCREEN_LOOK_MARK
            _joined = "".join(str(x) for x in (reply or []))
            if SCREEN_LOOK_MARK in _joined:
                import time as _t2
                if _t2.time() - float(getattr(self, "_last_self_look", 0)) > 20:
                    self._last_self_look = _t2.time()
                    print("[桌宠] 👀 她自己要求看屏幕 → 抓屏识别后重新回答")
                    self._talking = False
                    self.show_text("正在观看屏幕……", typing=True)
                    self._screen_look_busy = True
                    import threading as _th2
                    _th2.Thread(target=self._look_screen_and_reply,
                                args=(getattr(self, "_last_user_text", "") or "看看我屏幕上是什么",),
                                daemon=True).start()
                    return
                print("[桌宠] ⏭ 她又要求看屏幕（刚看过，忽略）")
                # ⚠ 忽略这次看屏幕，但**必须把标记从要显示的词里去掉**：
                #   以前这里直接往下走，标记就跟着台词一起显示到对话框里了
                #   ——用户看到的「对话框出现看屏幕」就是这个分支漏的（用户反馈）。
                try:
                    _stripped = []
                    for _it in (reply or []):
                        if SCREEN_LOOK_MARK in str(_it):
                            _tail = str(_it).replace(SCREEN_LOOK_MARK, "").strip()
                            if _tail:
                                _stripped.append(_tail)
                            continue
                        _stripped.append(_it)
                    reply = _stripped
                except Exception:
                    pass
        except Exception as _e2:
            print(f"[桌宠] ⚠ 自主要求看屏幕判断失败: {_e2}")

        # ── 插件（主人自己装的能力，标记长这样：【插件:天气】北京）──
        try:
            from classes.Worker_class import _pl_pending
            from tool import plugins as _plg
            _joined = "".join(str(x) for x in (reply or []))
            if "【插件】" in _joined or "【插件:" in _joined:
                _preq = _pl_pending.pop(0) if _pl_pending else ""
                _pl_pending[:] = []
                _lst = _plg.parse(str(_preq or ""))
                if _lst:
                    _mk, _arg = _lst[0]
                    print(f"[桌宠] 🧩 她要用插件「{_mk}」（参数：{_arg[:20]}）")
                    self._talking = False
                    self.show_text("唔……我看看。", typing=True)
                    import threading as _thp
                    _thp.Thread(target=self._plugin_and_reply, args=(_mk, _arg),
                                daemon=True).start()
                    return
                if not _lst:
                    print("[桌宠] 🧩 插件标记没解析出标记名 → 当普通回复处理")
                    reply = [_plg.clean_for_speech(_joined)] if _joined else reply
        except Exception as _ep:
            print(f"[桌宠] ⚠ 插件处理失败: {_ep}")

        # ── 她要上网查东西（提示词里教她：【搜索】关键词）──
        try:
            from tool.web_search import SEARCH_MARK
            from tool import web_search as _wsm
            from classes.Worker_class import _ws_pending
            if SEARCH_MARK in "".join(str(x) for x in (reply or [])):
                _wq = _ws_pending.pop(0) if _ws_pending else ""
                _ws_pending[:] = []
                _qs = _wsm.parse(str(_wq or ""))
                if _qs:
                    print(f"[桌宠] 🔍 她要搜：{_qs[0][:30]}")
                    self._talking = False
                    self.show_text("唔……我上网查查。", typing=True)
                    import threading as _thw
                    _thw.Thread(target=self._search_and_reply,
                                args=(_qs[0], getattr(self, "_last_user_text", "") or _qs[0]),
                                daemon=True).start()
                    return
        except Exception as _ew:
            print(f"[桌宠] ⚠ 搜索意图判断失败: {_ew}")

        # ── 她帮主人记提醒（提示词里教她：【提醒】30分钟后 喝水）──
        try:
            from tool.reminder import REMIND_MARK
            from tool import reminder as _rm
            from classes.Worker_class import _rm_pending
            if REMIND_MARK in "".join(str(x) for x in (reply or [])):
                _rreq = _rm_pending.pop(0) if _rm_pending else ""
                _rm_pending[:] = []
                _txt = _rm.clean_for_speech(str(_rreq or ""))
                _acts = _rm.parse(_txt)
                _res = ""
                for _k, _arg in _acts:
                    if _k == "list":
                        _res = _rm.list_text()
                    elif _k == "cancel":
                        _n = _rm.cancel(str(_arg))
                        _res = f"取消了 {_n} 条提醒。" if _n else "没找到要取消的提醒。"
                    elif _k == "pomodoro":
                        _res = _rm.pomodoro(int(_arg or 25))
                    elif _k in ("once", "daily"):
                        try:
                            _rm.add(float(_arg.get("at")), str(_arg.get("what")),
                                    daily=(_k == "daily"))
                            _res = ("记下了：%s%s。到点我叫你。"
                                    % ("每天 " if _k == "daily" else "",
                                       _rm._fmt_ts(_arg.get("at"))))
                        except Exception as _e1:
                            _res = f"提醒没记上（{type(_e1).__name__}）。"
                if _res:
                    print("[桌宠] ⏰ 提醒操作：" + str(_res)[:60])
                    self._request_dialog.emit(
                        "（系统提示：你刚才帮主人记/查了提醒，结果：" + str(_res) +
                        "。用你自己的口吻跟他说一声，一两句话，别念标记。）", "user", False)
                    return
                if _txt:
                    reply = [_txt] + [x for x in (reply or []) if REMIND_MARK not in str(x)]
        except Exception as _er:
            print(f"[桌宠] ⚠ 提醒处理失败: {_er}")

        # ── 她想看看电脑里的文件（提示词里教她：需要时输出【文件】列出 桌面）──
        #    和【看屏幕】一个套路：真去翻，翻完把内容交回给她接着说。
        #    请求内容由 Worker 解析标记时暂存在 file_access.set_pending 里。
        try:
            from tool.file_access import FILE_MARK
            from tool import file_access as _fa
            if FILE_MARK in "".join(str(x) for x in (reply or [])):
                _req = _fa.take_pending()
                if not _fa.enabled():
                    print("[桌宠] 📂 她想看文件，但「允许读取电脑文件」没开 → 跳过这轮")
                    return
                if _req:
                    print("[桌宠] 📂 她想看文件 → 去翻一下再回答")
                    self._talking = False
                    self.show_text("正在查看电脑文件……", typing=True)
                    import threading as _thf
                    _thf.Thread(target=self._file_read_and_reply,
                                args=(_req[0], getattr(self, "_last_user_text", "")
                                      or "看看我电脑里的东西"),
                                daemon=True).start()
                    return
        except Exception as _e3:
            print(f"[桌宠] ⚠ 文件意图判断失败: {_e3}")

        # ── 她要点歌（提示词里教她：需要点歌就输出【音乐】播放 歌名）──
        #    真的去网易云搜索并播放，然后用标题校验；结果交回给她说给主人听。
        try:
            from tool.music import MUSIC_MARK
            from tool import music as _mu
            from classes.Worker_class import _mu_pending
            if MUSIC_MARK in "".join(str(x) for x in (reply or [])):
                _mreq = _mu_pending.pop(0) if _mu_pending else ""
                if _mreq:
                    _mu_pending[:] = []          # 一次只处理一个
                    print("[桌宠] 🎵 她要点歌 → 去网易云搜索并播放")
                    self._talking = False
                    # 文案用中性的"正在点歌"：
                    #   用户反馈让她放**她自己**喜欢的歌时，对话框写「正在**帮你**点歌」很矛盾 ✗
                    self.show_text("正在点歌……", typing=True)
                    import threading as _thm
                    _thm.Thread(target=self._music_and_reply, args=(_mreq,), daemon=True).start()
                    return
        except Exception as _e4:
            print(f"[桌宠] ⚠ 点歌意图判断失败: {_e4}")

        # ⚠ 云端请求失败时 worker 拿到的是空串 → 切句后是 [""] → 以前会一路跳过，
        #   对话框什么都不显示（用户反馈"摸了没反应 / 聊天没回复"）。这里明确提示。
        try:
            if not any(str(_x).strip() for _x in (reply or [])):
                print("[桌宠] ⚠ 本轮回复为空（云端请求失败/超时？）→ 显示兜底提示")
                self.show_text("唔……信号好像不太好，等下再说一次好不好？", typing=True)
                self._talking = False
                return
        except Exception as _e:
            print(f"[桌宠] ⚠ 空回复判定失败: {_e}")

        # ⚠ 每轮回复一个「代号」：新回复一出现，旧回复剩下的句子链立刻作废。
        #   以前旧链里的 QTimer 回调会继续 show_text，把新回复（比如第二次摸头/摸身体
        #   触发的回复）的文字盖掉 → 看起来像"只有第一次有反应，后面就不回复了"。
        try:
            self._reply_gen = int(getattr(self, "_reply_gen", 0)) + 1
        except Exception:
            self._reply_gen = 1
        _gen = self._reply_gen
        try:      # 记下这轮说了什么（判断"它自己说要换衣服"用）
            self._last_reply_text = " ".join(str(x) for x in (reply or []))
        except Exception:
            self._last_reply_text = ""

        def show_next_sentence(index=0):
            if _gen != getattr(self, "_reply_gen", _gen):
                print(f"[桌宠] 旧回复链已作废（第 {_gen} 轮，当前第 {getattr(self, '_reply_gen', 0)} 轮）→ 停止")
                return
            def get_audio_length_wave(audio_file_path):
                """音频时长（毫秒）。wave 解析不了就按文件大小估（32k/16bit/单声道）。

                以前解析失败直接返回 0 → 下面会「跳过播放」+ 用纯文字时长当间隔 →
                句子被下一句的开播打断，听感就是"这几个字没声"。现在解析失败也给个估值，
                并且绝不用 0 去挡住播放。
                """
                try:
                    with wave.open(audio_file_path, "rb") as wave_file:
                        frames = wave_file.getnframes()  # 获取音频的帧数
                        rate = wave_file.getframerate()  # 获取音频的帧速率
                        return frames / float(rate or 1) * 1000
                except Exception:
                    try:
                        n = os.path.getsize(audio_file_path)
                        # GPT-SoVITS 输出固定 32kHz/16bit/单声道 → 每毫秒 64 字节
                        return max(300.0, n / 64.0)
                    except Exception:
                        return 300.0

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
                # ★ 只要文件在、不是空壳就播（以前按「解析出的时长 > 0」当开关，
                #   解析一失败就整句不出声 —— 音频格式/文件状态稍有不同就会静音）
                try:
                    if os.path.getsize(os.path.abspath(voice_path)) > 2000:
                        # 用绝对路径：QSound 用相对路径时依赖进程工作目录，换目录启动就会找不到文件
                        QSound.play(os.path.abspath(voice_path))
                except Exception as _e:
                    print(f"[桌宠] ⚠ 语音播放失败: {_e}")

            self.show_text(sentence, typing=True)
            # 计算打字机需要的时间（40ms * 每个字）
            # 音频间隔多留 600ms：QSound 起播有延迟，间隔太紧会被下一句开播打断（"没声"）
            delay = max(40 * len(sentence) + 800, voice_length + 600)  # 额外停顿

            def after_delay():
                if self._live2d_mode and self._live2d_widget:
                    self._live2d_widget.set_speaking(False)
                    # 句间不释放姿态：同情绪保持、换情绪在下一句切（自然衔接）
                # ★ 这里不再删 wav：同一句话重复出现时（同一轮里说两遍、或下一轮又说同一句）
                #   文件名是一样的，先播的那次删掉文件会把后一次的声音一起弄没（"有的句子没声"）。
                #   临时文件改由每轮开场统一清理陈旧文件。
                show_next_sentence(index + 1)

            QTimer.singleShot(int(delay), after_delay)

        # 开场：清掉上次遗留的临时语音（超过 3 分钟的），避免 tmp/ 越积越多
        try:
            _td = os.path.abspath("./tmp")
            if os.path.isdir(_td):
                _old = time.time() - 180
                for _f in os.listdir(_td):
                    if _f.lower().endswith(".wav"):
                        _p = os.path.join(_td, _f)
                        try:
                            if os.path.getmtime(_p) < _old:
                                os.remove(_p)
                        except Exception:
                            pass
        except Exception:
            pass

        show_next_sentence(index=0)
        self.worker = None  # 线程结束后清空引用
        try:      # 记一笔"跟她说过话"，开口评分与心情基线都要用
            from tool import state as _st2, attention as _att2
            _st2.note_talk()
            if str(getattr(self, "_last_turn_role", "")) == "system":
                _att2.note_spoke()          # 她自己主动搭的话才算"她开口"
        except Exception:
            pass

        # 整轮结束了 → 解除"忙"标记（之后状态文字才能显示）
        self._reply_active = False
        # 这一轮播完了 → 继续处理排队中的消息
        try:
            _q2 = getattr(self, "_pending_msgs", None) or []
            if _q2:
                _t2, _r2 = _q2.pop(0)
                print(f"[桌宠] ▶ 这一轮说完了，继续回排队的消息（剩 {len(_q2)}）：{str(_t2)[:20]}")
                self._replaying = True          # 标记"这是队列回放"，不要再塞回队列
                QTimer.singleShot(400, lambda: self.start_thread(_t2, _r2))
        except Exception as _e:
            print(f"[桌宠] ⚠ 处理排队消息失败: {_e}")

        # 说话/回复时的灵动效果：按概率在两套立绘之间切换（透明渐变过渡）
        self._maybe_crossfade_set()

        # 本轮结束：若本轮强注入了 high 观察，将其降为 low（识别观察仅在下一轮高权重）
        if self._has_high_this_round:
            self._demote_all_high()

    # 启动一个新线程（安全版，打断旧线程）
    def is_busy_reply(self) -> bool:
        """她是不是正在思考 / 正在说话（这期间不接受新的对话）。

        ★ 2026-09-24 用户反馈"有的对话还没结束就被顶掉了"：
          整轮回复在**句子之间**会有短暂停顿（上一句放完、下一句还没开始），
          那时 `_talking` 是 False → 状态文字就挤进来了 ✗。
          所以额外用一个 `_reply_active` 标记**整轮**（on_reply 开始到结束），
          这期间一律算忙。
        """
        try:
            if self.worker is not None and self.worker.isRunning():
                return True
        except Exception:
            pass
        if getattr(self, "_reply_active", False):
            return True
        return bool(getattr(self, "_talking", False) or getattr(self, "_stream_playing", False))

    def _set_ime(self, on: bool):
        """输入法只在"真正等主人打字"时开启。

        ⚠ 以前启动就把 WA_InputMethodEnabled 打开 → 点一下窗口（哪怕她正在说话、
          根本不能输入）系统也会切到中文输入状态（用户反馈）。
        """
        try:
            self.setAttribute(Qt.WA_InputMethodEnabled, bool(on))
        except Exception:
            pass

    def _show_busy_hint(self):
        """她正在说话/思考时，主人点对话框/身体 → **静默忽略**。

        不动对话框内容、不弹提示（用户要求"直接不让点击，不要有提示"）；
        只在日志里记一行，方便排查。
        """
        try:
            print("[桌宠] 她还在说话/思考 → 本次点击已静默忽略（不改对话框）")
        except Exception:
            pass

    def _clear_thinking_if_stuck(self):
        """「思考中」卡住时恢复上一句（网络失败时回复永远不来）"""
        try:
            # 线程已经结束、可 finished 信号一直没回来（以前某一步抛异常就会这样）：
            # 主动释放对话锁，否则 _talking 一直是 True，点她只会被当成「她还在说话」忽略，
            # 整只桌宠就变成「点了没反应」（用户反馈"点击对不了话"）。
            _w = getattr(self, "worker", None)
            if _w is not None and not _w.isRunning():
                print("[桌宠] ⏱ 上一轮回复没有正常收尾 → 释放对话锁（点击恢复可用）")
                self.worker = None
                self._talking = False
                self._stream_playing = False
                self._thinking_on = False
                self._busy_hint_on = False
                self.display_text = getattr(self, "_last_real_text", "") or ""
                self.update()
        except Exception:
            pass
        try:
            if getattr(self, "_thinking_on", False) and "思考中" in str(self.display_text or ""):
                self.display_text = getattr(self, "_last_real_text", "") or ""
                self._thinking_on = False
                print("[桌宠] ⏱ 思考提示超时 → 恢复上一句显示")
                self.update()
        except Exception:
            pass

    def _show_thinking(self, user_asked: bool = True):
        """在对话框里显示「思考中...」

        只有主人主动找她时才显示；屏幕评论 / 空闲搭话这类自动回复不刷这个提示，
        否则对话框会一直停在"思考中"（用户反馈"老是进入思考中"）。
        """
        if not user_asked:
            return
        try:
            self._thinking_on = True
            _nm = str(getattr(self, "pet_name", "") or "桌宠")
            self.display_text = "【" + _nm + "】" + "\n" + "思考中..."
            self.update()
            # 兜底：万一回复始终没来（请求失败/被拦），90 秒后自动恢复上一句，
            # 免得对话框一直停在"思考中"（用户反馈"没思考也显示思考中"）
            QTimer.singleShot(90000, self._clear_thinking_if_stuck)
        except Exception:
            pass

    def start_thread(self, text, role, t=False, no_act=False):
        """发起一轮对话。

        no_act=True：这一轮只是寒暄/系统提示（比如开机问候）→ 不许解析、执行任何
        操作指令，也不开「连着做完」的任务循环（实测 bug：问候那一轮她多写了一句
        【键鼠】移动，结果整个问候被当成电脑操控任务跑了一遍）。

        另外：提示词里只要写了「只是寒暄」，就自动按 no_act 处理 —— 各处系统提示
        （问候/关怀/久没输入/摸头/摄像头…）都带上这句，省得一个个传参数
        （经 _request_dialog 信号进来的那些传不了第 4 个参数）。
        """
        try:
            if not no_act and "只是寒暄" in str(text or ""):
                no_act = True
        except Exception:
            pass
        try:
            self._last_turn_role = str(role)
        except Exception:
            pass
        # ★「这条到底是不是主人真的开口了？」—— 桌宠自己发的**内部提示**也走 role="user"
        #   （例如「（系统提示：你刚接下了陪主人玩游戏…说一句）」），以前一律按"主人开口"处理，
        #   于是她刚接手玩游戏、转头就被自己的内部提示当成主人说话 → 立刻停手 ✗
        #   （实测日志：[游戏] 开始玩「ATRI」→ [游戏] ⛔ 停止（主人开口说话了）→ 游戏零进展）。
        #   这些提示有统一前缀「（系统提示：」，据此区分。
        _is_internal = str(text or "").lstrip().startswith("（系统提示")
        if not _is_internal:
            self._chatter_turn = False     # 主人（或她自己发起之外）真的开口 → 清掉 marker
        if role == "user" and not _is_internal:
            self._last_user_ts = time.time()   # 自主学习用它判断"主人是不是刚说过话"
            try:      # ★ 记一次活跃：作息（每天起止）、活跃时段（小时分布）
                from tool import habits as _hb
                _hb.note_active()
            except Exception:
                pass
            # 心情/好感：被夸会高兴、被凶会难过（人设里她在意的词）
            try:
                from tool import state as _st3
                _t = str(text or "")
                if any(w in _t for w in ("可爱", "厉害", "喜欢你", "乖", "谢谢", "好看", "聪明")):
                    _st3.feel(6, 0.5, "主人夸了她")
                if any(w in _t for w in ("飞机场", "搓衣板", "锉刀", "幼刀", "钝刀", "幽灵",
                                         "笨蛋", "蠢", "烦人", "闭嘴", "滚")):
                    _st3.feel(-12, -0.8, "主人说了她在意的坏话")
                else:
                    _st3.feel(0.6, 0.06, "")     # 正常聊天慢慢升温
            except Exception:
                pass
            # ── 主人叫停：她正在操控电脑时，立刻停手 + 回一句话 ──
            try:
                from tool import pc_task as _pt2
                from tool import pc_control as _pc2
                if self._is_stop_command(text):
                    _was = _pt2.running()
                    _pt2.stop("主人叫停")
                    _pc2.set_abort("主人叫停")
                    if _was or _pc2.abort_requested():
                        print("[桌宠] ⛔ 主人叫停 → 已停止操控，让她回一句")
                        self._request_dialog.emit(
                            "（系统提示：主人刚让你停手，你已经立刻停下来了，什么都不要再操作。"
                            "用你自己的口吻回他一句（一句就够），例如「好，停了。」）", "user", False)
                        return
            except Exception as _es:
                print(f"[桌宠] ⚠ 叫停判断失败（照常继续）: {_es}")
        # ★ 主人正在打字时，系统自动接话（打招呼/空闲搭话/触摸）一律不发起：
        #   一起话就会把她切到"思考/说话"状态，正在打的字就被吃掉（用户反馈）。
        try:
            if role == "system" and getattr(self, "input_mode", False):
                print("[桌宠] ⌨ 主人正在打字 → 暂不接话（避免打断输入）")
                return
        except Exception:
            pass
        # ★ 她正在思考或正在说的时候，新消息先排队，等这一轮说完再回
        #   （用户反馈：对话会被另一段回复打断；"对话没说完之前不允许和桌宠对话"）。
        try:
            _busy = self.is_busy_reply()
            if _busy and role == "user" and self._debug_obey():
                print("[桌宠] 🛠 调试模式：主人优先 → 立即打断当前回复")
                _busy = False
            # ★ 用户要求：「玩游戏/控制电脑/屏幕识别时应该能进行对话」——
            #   她干活时每几轮会自己顺口说一句，那一轮会把对话管线占住 → 主人的话只能排队。
            #   主人真的开口时**优先**：把她自己发起的那一轮（chatter/播报）打断，
            #   立刻回主人（她自己的碎碎念不重要）。
            if (_busy and role == "user"
                    and getattr(self, "_chatter_turn", False)):
                print("[桌宠] 🎤 主人说话优先 → 打断她自己的那一句（干活时不耽误对话）")
                try:
                    if self.worker is not None and self.worker.isRunning():
                        self.worker.stop_all()
                except Exception:
                    pass
                for _fn in (getattr(self, "_stop_stream", None),):
                    try:
                        if _fn:
                            _fn()
                    except Exception:
                        pass
                try:
                    QSound.stop()
                except Exception:
                    pass
                self._talking = False
                self._stream_playing = False
                self._chatter_turn = False
                _busy = False
            if _busy:
                if role == "user":
                    _q = getattr(self, "_pending_msgs", None)
                    if getattr(self, "_replaying", False):
                        # ★ 这条是从队列里回放的：她还忙着（多半在朗读）→ 过一会儿重试，
                        #   绝不能又塞回队列。以前就是"取出 → 发现还忙 → 又排回去"来回打转，
                        #   队列只涨不消、她永远显示忙碌，点她全被忽略（用户反馈"点不了桌宠"）。
                        _try = int(getattr(self, "_replay_tries", 0) or 0)
                        if _try < 15:
                            self._replay_tries = _try + 1
                            print(f"[桌宠] ⏳ 排队的消息等她说完再回（第 {_try + 1} 次等）")
                            QTimer.singleShot(1200, lambda: self.start_thread(text, role))
                            return
                        self._replay_tries = 0
                        print("[桌宠] ⚠ 排队的消息等太久 → 直接放行")
                    if _q is None:
                        _q = []
                        self._pending_msgs = _q
                    # ★ 去重（2026-09-24 实测：玩游戏时"你做完了一次操作"这类系统消息
                    #   会把队列堆到 6 条，她一直在"回排队的消息"，看起来就像没在好好玩）。
                    #   同一类系统提示只留最新的一条；主人的话永远保留。
                    _t = str(text or "")
                    _kind = _t[:_14]
                    if role != "user" and _q:
                        for _i in range(len(_q) - 1, -1, -1):
                            if str(_q[_i][0])[:_14] == _kind:
                                _q.pop(_i)
                                print("[桌宠] 🧹 队列里同类的系统提示已合并（只留最新一条）")
                    if len(_q) < 8:
                        _q.append((text, role))
                        print(f"[桌宠] ⏳ 她还在说话/思考，这条先排队（队列 {len(_q)}）：{str(text)[:20]}")
                else:
                    print(f"[桌宠] ⏭ 她正忙，跳过这条系统观察：{str(text)[:20]}")
                return
        except Exception as _e:
            print(f"[桌宠] ⚠ 排队判断失败（照常继续）: {_e}")
        # 这条消息被接受了 → 清掉队列回放的标记
        try:
            self._replaying = False
            self._replay_tries = 0
        except Exception:
            pass
        # 长文本模式下：识别触发（t=True）在流式输出中自动跳过，空闲时走长文本流式
        # ── 主人让我看屏幕 → 当场抓屏识别 ──
        # 以前只有「定时抓屏」和「截图按钮」会调用视觉模型；直接问她
        # 「我屏幕上是什么」「我在干嘛」时根本不抓屏，她只能拿之前自动识别留下的
        # 记忆凑答案，或者干脆说看不到（用户反馈）。这里先判断意图，命中就抓一张
        # 新图识别，再把描述和主人的问题一起送进对话流程。
        try:
            if role == "user" and not t and not getattr(self, "_screen_look_busy", False):
                from tool.screen_intent import needs_screen_look
                if needs_screen_look(text):
                    self._screen_look_busy = True
                    print("[桌宠] 👀 主人让我看屏幕 → 当场抓屏识别")
                    self.show_text("正在观看屏幕……", typing=False)
                    import threading as _th
                    _th.Thread(target=self._look_screen_and_reply,
                               args=(text,), daemon=True).start()
                    return
        except Exception as _e:
            self._screen_look_busy = False
            print(f"[桌宠] ⚠ 屏幕意图判断失败（照常对话）: {_e}")

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

        if role == "user" and text:
            self._last_user_text = str(text)     # 她自己要求看屏幕时，带着这句重新回答
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
        self._show_thinking(role == "user")   # 只有主人发起才显示"思考中"

        # 启动新线程
        # ★ 把「当前画面上显示的那一套立绘」一起交给 AI：
        #   以前 AI 读的是 config.json 里的套，和实际渲染的套不一致时会跨套换算，
        #   表情/装饰被丢掉 → 立绘看起来"没有表情"（用户反馈）。
        _ptype = str(getattr(self, "_display_set", "") or "") or None
        if model_type == "local":
            self.worker = qwen3_lora_Worker(
                self.history, self.portrait_history, text, role, t=t,
                portrait_type=_ptype, no_act=bool(no_act),
            )
        else:
            self.worker = cloud_API_Worker(
                self.history, self.portrait_history, text, role, t=t,
                portrait_type=_ptype, no_act=bool(no_act),
            )

        self.worker.finished.connect(self.on_reply)
        try:
            # Worker 报告"正在操作电脑……/正在查看电脑文件……" → 对话框显示一行状态
            self.worker.status.connect(self._on_worker_status)
        except Exception:
            pass
        self.worker.start()

    def _ensure_window_fits_pixmap(self, pm):
        """兜底：窗口至少要和立绘一样大，否则图会被裁掉一半。

        立绘宽度会随衣服/表情变化，任何"窗口比图窄"的情况（键变了、换了张更宽的图、
        渐变收尾时用了别的尺寸……）都在这里被纠正。
        """
        try:
            if pm is None or pm.isNull():
                return
            w, h = self.width(), self.height()
            nw, nh = max(w, pm.width()), max(h, pm.height())
            if (nw, nh) != (w, h):
                self.setFixedSize(nw, nh)
                try:
                    self._portrait_max_w = max(int(getattr(self, "_portrait_max_w", 0) or 0), nw)
                except Exception:
                    pass
                print(f"[桌宠] 窗口放大到 {nw}x{nh}（原 {w}x{h}）以完整显示立绘")
        except Exception as e:
            print(f"[桌宠] ⚠ 窗口尺寸兜底失败: {e}")

    def _clamp_to_screen(self, size=None):
        """把窗口挪回屏幕内。

        ⚠ 默认**不挪**：主人要求"位置即使在屏幕外面也不要改变位置"（他想把桌宠停在
          屏幕边缘/外面）。以前每次回复都会按尺寸重新算一遍，位置还会来回跳（用户反馈）。
          想要旧的"自动挪回屏幕内"行为，右键菜单 →「界面」→「自动挪回屏幕内」打开即可。

        size：调用方按"将要生效的尺寸"传进来（Qt 的 setFixedSize 是**异步**生效的，
              紧接着读 self.height() 往往是旧值——以前就在这里读旧高度，
              算出"最多只能放到 y=615"，于是先放到 615、下一轮又拉回 216，位置乱跳）。
        """
        try:
            from PyQt5.QtGui import QGuiApplication
            scr = QGuiApplication.screenAt(self.frameGeometry().center()) or QGuiApplication.primaryScreen()
            g = scr.availableGeometry()
            if size is not None:
                w, h = int(size.width()), int(size.height())
            else:
                w, h = self.width(), self.height()
            x, y = self.x(), self.y()
            nx = min(max(x, g.x()), max(g.x(), g.x() + g.width() - w))
            ny = min(max(y, g.y()), max(g.y(), g.height() - h))
            if (nx, ny) == (x, y):
                return
            if not self._auto_clamp_enabled():
                # 主人说了不要动 → 只记一行日志（方便排查），绝不改位置
                if not getattr(self, "_offscreen_logged", False):
                    self._offscreen_logged = True
                    print(f"[桌宠] 📌 位置 ({x},{y}) 有一部分在屏幕外，但你要求不改位置 → 保持不动")
                return
            self.move(nx, ny)
            print(f"[桌宠] 立绘尺寸变化 → 挪回屏幕内 ({x},{y}) → ({nx},{ny})（按 {w}x{h} 算）")
            # ★ 启动自检：把关键几何打进日志，万一还出现"立绘只显示一半"，
            #   这一行就能看出是窗口、立绘还是屏幕对不上。
            if not getattr(self, "_geom_logged", False):
                self._geom_logged = True
                _pm = self.pixmap()
                print("[桌宠] 📏 立绘自检：窗口 %dx%d | 立绘 %s | 记忆画布宽 %s | 屏幕可用 %dx%d | 位置 (%d,%d)"
                      % (self.width(), self.height(),
                         ("%dx%d" % (_pm.width(), _pm.height())) if (_pm and not _pm.isNull()) else "无",
                         getattr(self, "_portrait_max_w", 0),
                         g.width(), g.height(), self.x(), self.y()))
        except Exception as e:
            print(f"[桌宠] ⚠ 位置校正失败: {e}")

    def _look_screen_and_reply(self, user_text):
        """当场抓一张屏 → 交给视觉模型 → 把描述和主人的问题一起送进对话流程。

        跑在后台线程里（视觉识别要 30~50 秒，不能在界面线程做）。
        任何一步失败都退回「只用主人原话」的正常对话，不会让她卡住不说话。
        """
        tmp_name = ""
        try:
            import tempfile
            from tool.screen_capture import capture_qimage, is_blank as _is_blank_img
            from tool.chat import describe_image, vision_fast_size, vision_fast_tokens
            from tool.screen_intent import build_screen_prompt
            # ⚠ 用 Win32 抓屏（tool.screen_capture）：这里跑在后台线程，
            #   Qt 的 QScreen.grabWindow 只能 GUI 线程用，在这里调会崩进程。
            _img = capture_qimage(self._screen_index_now())
            if _img is None or _is_blank_img(_img):
                print("[桌宠] ⚠ 屏幕是黑的（锁屏/显示器休眠）→ 如实告诉主人，不带屏幕内容")
                self._request_dialog.emit(
                    "【系统提示】主人让你看屏幕，但此刻抓不到画面（可能锁屏或显示器休眠）。"
                    "请简短如实地告诉主人你看不到，并问他是不是锁屏了。"
                    "只输出你自己要说的话（JSON 数组）。", "user", False)
                return
            fd = tempfile.NamedTemporaryFile(delete=False, suffix=".png", dir="tmp")
            tmp_name = fd.name
            fd.close()
            _img.save(tmp_name, "PNG")
            # 主人正在等 → 用快速档（896px：编码约 6~8 秒，比 1280px 快一倍多）
            desc = describe_image(tmp_name, max_side=vision_fast_size(), max_new=vision_fast_tokens())
            if not str(desc or "").strip():
                print("[桌宠] ⚠ 视觉识别没返回内容 → 退回普通回答")
                self._request_dialog.emit(user_text, "user", False)
                return
            prompt = build_screen_prompt(desc, user_text, getattr(self, "pet_name", "桌宠"))
            print(f"[桌宠] 👀 屏幕识别完成（{len(str(desc))} 字）→ 带着描述回答主人")
            self._request_dialog.emit(prompt, "user", False)
        except Exception as e:
            print(f"[桌宠] ⚠ 看屏幕失败（{type(e).__name__}: {e}）→ 退回普通回答")
            try:
                self._request_dialog.emit(user_text, "user", False)
            except Exception:
                pass
        finally:
            self._screen_look_busy = False
            if tmp_name:
                try:
                    os.remove(tmp_name)
                except Exception:
                    pass

    # 鼠标按下事件
    def mousePressEvent(self, event):
        # ⓪ 立绘右上角的快捷按钮优先（对话 / 菜单）
        try:
            if event.button() == Qt.LeftButton:
                _b = self._ui_button_at(event.x(), event.y())
                if _b:
                    self._ui_press = _b
                    self.update()
                    QTimer.singleShot(120, self._ui_press_clear)
                    if _b == "menu":
                        self._show_outfit_menu(event.globalPos())
                    else:
                        self._enter_input_mode()
                    return
        except Exception as _e:
            print(f"[桌宠] ⚠ 快捷按钮点击失败: {_e}")

        # ★ 她正在思考 / 正在说话时，鼠标整体不响应：
        #   点对话框（文字区）会命中"触摸互动"→ 触发一段反应，看起来就像插话；
        #   点下半身会进键盘输入。这两种都在她说的时候禁掉，只保留"思考中..."。
        if event.button() == Qt.LeftButton and self.is_busy_reply():
            self._show_busy_hint()
            self._touch_hit = None
            self._touch_fired = True          # 标记已处理，松开时不再触发
            print("[桌宠] ⏳ 她还在思考/说话，先别插话（本次点击已忽略）")
            return
        if event.button() == Qt.LeftButton:
            # ① 先做「触摸区域」命中判定（头 / 胸口 / 小腹 / 下体 / 腿 / 脚 / 胳膊 / 手掌）
            _area = self._touch_area_at(event.x(), event.y())
            if _area:
                self._touch_hit = _area
                self._touch_press = (event.x(), event.y())
                self._touch_fired = False
                if _area == "head":
                    self.touch_head = True          # 兼容旧逻辑
                    self.head_press_x = event.x()
                self.setCursor(Qt.OpenHandCursor)
                return
            self._touch_hit = ""
            self._touch_press = None
            # ② 没命中触摸区域：维持原有行为（上方=可摸头区域/下方=键盘输入）
            if event.y() < 150:  # 头部区域
                self.touch_head = True
                self.head_press_x = event.x()
                self.setCursor(Qt.OpenHandCursor)
            elif event.y() > 280:  # 下半身区域 -> 输入模式
                if self.is_busy_reply():      # 她还在思考/说话 → 不接受新的对话
                    self._show_busy_hint()
                    self._set_ime(False)      # 输入法也别切过来
                    print("[桌宠] ⏳ 她还在思考/说话，先别插话（已忽略这次点击）")
                elif self.input_mode:
                    # 已经在打字 → 只重新聚焦，不清空已打的字（否则会"消失重置"）
                    self.setFocus()
                    self.update()
                else:
                    self.input_mode = True
                    self._set_ime(True)
                    self.input_buffer = ""
                    self.preedit_text = ""
                    self.display_text = ("【" + str(self.user_name) + "】\n可以直接打字了，输入后按回车发送（Esc 取消）")
                    self.update()
            # ③ 兜底：点在对话框上 → 进入打字模式
            #    触摸区域 / 摸头 / 下半身键盘输入都优先，所以放最后。
            #    放最前面会挡住摸头摸身，导致触摸不触发对话。
            elif self._in_text_box(event.x(), event.y()):
                if self.is_busy_reply():
                    self._show_busy_hint()
                    self._set_ime(False)
                    print("[桌宠] 她还在思考/说话，点击对话框已忽略")
                else:
                    self.input_mode = True
                    self._set_ime(True)
                    self.input_buffer = ""
                    self.preedit_text = ""
                    self.display_text = ("【" + str(self.user_name) +
                                         "\n可以直接打字了，输入后按回车发送（Esc 取消）")
                    self.setFocus()
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

        elif event.button() == Qt.RightButton:
            # 右键：快速换装菜单（同步 QQ 立绘与下次启动）
            self._show_outfit_menu(event.globalPos())

    def _show_outfit_menu(self, global_pos):
        """右键菜单：切换服装 / 动作（写共享配置 → QQ 立绘与桌宠同时生效并持久化）。

        弹出时做一段淡入 + 轻微上浮的过渡（菜单这类原生弹窗只能动 windowOpacity/pos）。
        """
        # ★ 菜单已经开着 → 再点一次就关掉（用户要求：同一个按钮切换开关）
        try:
            _m = getattr(self, "_outfit_menu", None)
            if _m is not None and _m.isVisible():
                _m.close()
                self._outfit_menu = None
                try:
                    self._ui_press = None
                    self.update()
                except Exception:
                    pass
                print("[桌宠] 菜单已关闭（再点「菜单」可重新打开）")
                return
        except Exception:
            pass
        try:
            menu = self._build_outfit_menu()
            if menu is None or menu.isEmpty():
                return
            self._outfit_menu = menu
            try:                                  # 菜单消失时清掉引用，下次点击是"打开"
                menu.aboutToHide.connect(lambda: setattr(self, "_outfit_menu", None))
            except Exception:
                pass
            self._popup_menu_animated(menu, global_pos)
        except Exception as e:
            print(f"[桌宠] ⚠ 打开换装菜单失败: {e}")

    def _popup_menu_animated(self, menu, global_pos):
        """菜单过渡动画：淡入（180ms）+ 从下方 10px 处上浮到最终位置。"""
        try:
            menu.setWindowOpacity(0.0)
            menu.popup(global_pos)
            a = QPropertyAnimation(menu, b"windowOpacity", menu)
            a.setDuration(150)
            a.setStartValue(0.0)
            a.setEndValue(1.0)
            a.setEasingCurve(QEasingCurve.OutCubic)
            self._menu_fade_anim = a          # 保引用，别被回收
            a.start()
            try:
                g = menu.geometry()
                end = g.topLeft()
                start = end + QPoint(0, 7)
                m = QPropertyAnimation(menu, b"pos", menu)
                m.setDuration(140)
                m.setStartValue(start)
                m.setEndValue(end)
                m.setEasingCurve(QEasingCurve.OutCubic)
                self._menu_pos_anim = m
                menu.move(start)
                m.start()
            except Exception:
                pass
            try:                              # 菜单开着时按钮保持"按下"高亮
                self._ui_press = "menu"
                menu.aboutToHide.connect(self._ui_press_clear)
            except Exception:
                pass
        except Exception as e:
            print(f"[桌宠] ⚠ 菜单动画失败（直接弹出）: {e}")
            menu.exec_(global_pos)

    def _build_outfit_menu(self):
        """构造右键换装菜单（单独拆出来便于测试）。

        a / b 两套立绘素材各自独立，菜单里改的是【当前显示那套】；
        服装/动作按【当前桌宠自己的选项表】取，不会串到别的角色。
        没有服装素材的角色（例如「每个表情一张整图」）不显示换装项。"""
        try:
            from PyQt5.QtWidgets import QMenu
            from tool.pet_menu import StoryMenu, section, item, submenu, separator
            from tool.portrait_outfit import SETS, load_outfit
            # ⚠ 服装/动作必须按【这个桌宠自己的表】取：以前这里用的是内置的丛雨表，
            #   于是任何角色右键看到的都是丛雨的 制服/睡衣/私服/刀服。
            from qq.qq_portrait import clothes_for, actions_for
            _pid = self._pet_id or None
            cur_set = self._current_set()
            cur = load_outfit(cur_set)
            cur_name = cur.get("cloth") or ""
            cur_act = cur.get("action") or ""
            # ★ 菜单必须"跟着画面走"：优先用身上这件（实时图层）的名字，保存值只做兜底。
            #   否则 AI 换过衣服后菜单还显示上一件（用户反馈"菜单没跟随变动"）。
            try:
                from tool.portrait_outfit import (cloth_name as _cn2, resolve_cloth as _rc2,
                                                  describe_layers as _dl2)
                _live2 = int(self._current_body_layer(cur_set) or 0)
                if _live2:
                    _ln, _la = str(_cn2(_live2) or ""), ""
                    for _n, _a, _o in actions_for(cur_set, _pid):
                        if int(_a or 0) == _live2:
                            _la = str(_n)
                            _ln = _ln or str(_rc2(_n) or "")
                            break
                    if not _ln or not _la:
                        _d2 = _dl2([_live2], cur_set, _pid) or ""
                        if not _ln and "衣服：" in _d2:
                            _ln = _d2.split("衣服：")[-1].split("；")[0].strip()
                        if not _la and "姿势：" in _d2:
                            _la = _d2.split("姿势：")[-1].strip()
                    if _ln:
                        cur_name = _ln
                    if _la:
                        cur_act = _la
            except Exception as _e:
                print(f"[桌宠] ⚠ 菜单当前穿着读取失败: {_e}")
            try:
                cloths = [(n, int(c), int(h)) for n, c, h in clothes_for(cur_set, _pid)]
            except Exception:
                cloths = []
            # ★ 素材被删掉的衣服不列出来（正式版删了裸体素材，但表里可能还留着）：
            #   否则点了会合成出空图 → 桌宠变透明（用户反馈过）。
            try:
                from pets.pet_registry import get_fgimages_dir, get_fgimages_prefix
                _fg = get_fgimages_dir(_pid)
                if _fg:
                    _pfx = get_fgimages_prefix(_pid)
                    _keep = []
                    for _n, _c, _h in cloths:
                        _png = os.path.join(_fg, "%s%s_%d.png" % (_pfx, cur_set, _c))
                        if os.path.exists(_png):
                            _keep.append((_n, _c, _h))
                        else:
                            print(f"[桌宠] 服装「{_n}」素材不存在 → 菜单里不显示")
                    cloths = _keep
            except Exception as _e:
                print(f"[桌宠] ⚠ 服装可用性检查失败: {_e}")
            try:
                acts = [(n, int(a), int(b)) for n, a, b in actions_for(cur_set, _pid)]
                # 只列当前这件衣服的姿势
                _cur_cid = int(cur.get("cloth_id") or 0)
                cur_acts = [x for x in acts if not _cur_cid or x[2] == _cur_cid]
            except Exception:
                cur_acts = []
            menu = StoryMenu(self)
            # ★ 顶层只放三个分类，具体开关收进子菜单（以前十几项平铺，菜单太长）
            # ── ① 换装与立绘 ▸ ──
            _dress = submenu(menu, "换装与立绘")
            if cloths:
                _cloth_sub = submenu(_dress, "切换服装（当前：%s）" % (cur_name or "默认"))
                for name, cid, _h in cloths:
                    # 勾号要能对上：菜单名和"当前穿着"可能一个叫"刀装"一个叫"刀服"，
                    # 先各自归一化再比（用户反馈勾号不见了）
                    try:
                        from tool.portrait_outfit import resolve_cloth as _rc
                        _same = (_rc(name) or name) == (_rc(cur_name) or cur_name)
                    except Exception:
                        _same = (name == cur_name)
                    act = item(_cloth_sub, name, checked=_same)
                    act.triggered.connect(lambda checked=False, n=name: self._switch_cloth(n))
            if cur_acts:
                _acts_sub = submenu(_dress, "切换动作（手臂姿势）")
                act0 = item(_acts_sub, "默认姿势", checked=not cur_act)
                act0.triggered.connect(lambda checked=False: self._switch_action(0))
                for name, aid, _b in cur_acts:
                    a2 = item(_acts_sub, name, checked=(name == cur_act))
                    a2.triggered.connect(lambda checked=False, n=name: self._switch_action(n))
            # 装饰：单独一页（可滚动）——装饰多了不会把菜单撑得满屏
            try:
                from qq.qq_portrait import decors_for
                _decs = [(str(n), int(i)) for n, i in decors_for(cur_set, _pid)]
            except Exception:
                _decs = []
            if _decs:
                _decor_sub = submenu(_dress, "装饰（可多选）")
                self._fill_decor_menu(_decor_sub, cur_set, _decs, cur)
            # a / b 切换：只有这个角色确实有两套素材时才给
            _avail = [x for x in SETS if self._has_fgimages_set(x)]
            if len(_avail) >= 2:
                _set_sub = submenu(_dress, "切换立绘类型（a / b）")
                for s in SETS:
                    if s not in _avail:
                        continue
                    act = item(_set_sub, f"{s} 立绘", checked=(s == cur_set))
                    act.triggered.connect(lambda checked=False, ss=s: self._switch_portrait_set(ss))
            try:
                separator(_dress)
                act_auto = item(_dress, "自动切换立绘类型", checked=self._auto_switch_enabled())
                act_auto.triggered.connect(self._toggle_auto_switch)
            except Exception:
                pass
            # 调试模式：无条件服从（仅开发版显示；正式版不提供）
            if self._debug_available():
                try:
                    separator(_dress)
                    act_dbg = item(_dress, "调试模式（无条件服从）", checked=self._debug_obey())
                    act_dbg.setToolTip("开启后她无条件听你的：换装不再要求明确指令、"
                                       "AI 挑的服装与姿势一律照做、不再保持同款连贯。仅调试用。")
                    act_dbg.triggered.connect(self._toggle_debug_obey)
                except Exception:
                    pass

            # ── ② 电脑与学习 ▸ ──
            # 电脑操作：她能移动/点击鼠标、滚轮、输入、组合键；坐标必须在屏幕内，
            #           不做数量限制（限制会让她做到一半停下），所有操作写 data/pc_control.log。
            # 读取文件：只读（不写不改不删），只允许用户目录与桌面/文档/下载这些地方，
            #           系统目录一律拒绝；日志在 data/file_access.log。
            # 自主学习：她自己归纳长期记忆、空闲自习、写日记，存在
            #           pets/<角色>/memory/learned.json（「看看她学到了什么」可以直接看）。
            try:
                from tool import pc_control as _pc
                from tool import file_access as _fa
                from tool import self_learn as _sl
                _ai = submenu(menu, "电脑与学习")
                _act_pc = item(_ai, "允许操控电脑（键鼠）", checked=_pc.enabled())
                _act_pc.setToolTip(
                    "开启后她可以自己操作键鼠：点击 / 双击 / 右键 / 滚轮 / 输入文字 / 组合键（Ctrl+S 等）/ 等待。" + chr(10) +
                    "要连续操作时她可以写多条指令，不限条数（不会做到一半停下）。" + chr(10) +
                    "她看不到画面时可以自己输出「【看屏幕】」先看一眼再动手（移动鼠标→看清楚→点击）。" + chr(10) +
                    "坐标必须在屏幕内；操作时对话框会显示「正在操作电脑……」，做完会把做了什么说出来；" + chr(10) +
                    "所有操作都记到 data/pc_control.log。随时可以在这里关掉（关掉后立刻停止执行）。")
                _act_pc.triggered.connect(lambda on=False: _pc.set_enabled(bool(on)))
                _act_auto = item(_ai, "自主操作（不用主人开口）", checked=_pc.auto_enabled())
                _act_auto.setToolTip(
                    "开启后她会自己判断要不要动手（看你屏幕上的情况），不必每次等你吩咐。" + chr(10) +
                    "有最小间隔（默认 1 分钟一次，config 的 pc_auto_minutes 可调），避免她自己反复点；" + chr(10) +
                    "只是移动鼠标不算做事、也不占用间隔；你明确让她做事时不受这个间隔限制。" + chr(10) +
                    "所有操作都记在 data/pc_control.log（她没做成的原因也写在那里）。")
                _act_auto.triggered.connect(lambda on=False: _pc.set_auto_enabled(bool(on)))
                separator(_ai)
                _act_fa = item(_ai, "允许读取电脑文件", checked=_fa.enabled())
                _act_fa.setToolTip(
                    "开启后她能看看你电脑里的文件（只读，不会改动、删除任何东西）。" + chr(10) +
                    "你能这样用：「我桌面上有什么」「下载里那个笔记写了啥」；" + chr(10) +
                    "她也会自己偶尔了解一下电脑近况（磁盘、桌面、开着的窗口）当聊天话题。" + chr(10) +
                    "只看桌面／文档／下载／图片／音乐／视频和桌宠自己的目录，系统目录一律拒绝；" + chr(10) +
                    "名字里带密码/密钥/token 这类字样的文件不读；记录在 data/file_access.log。")
                _act_fa.triggered.connect(lambda on=False: _fa.set_enabled(bool(on)))
                _act_learn = item(_ai, "自主学习（自己记东西）", checked=_sl.enabled())
                _act_learn.setToolTip(
                    "开启后她会自己学东西：" + chr(10) +
                    "① 聊完一段自己归纳「关于主人的事」和心情，存成长期记忆（聊天时会自动用上）；" + chr(10) +
                    "② 你不在的时候挑个话题自己补课（约 20 分钟一次，你刚说过话就不打扰）；" + chr(10) +
                    "③ 每天写一段日记。全部存在 pets/角色/memory/learned.json。")
                _act_learn.triggered.connect(lambda on=False: _sl.set_enabled(bool(on)))
                separator(_ai)
                _act_seen = item(_ai, "她的状态 / 记忆 / 提醒")
                _act_seen.setToolTip("单独开一个小窗口，显示她记住的事、学到的东西和最近的日记。")
                _act_seen.triggered.connect(self._show_learned)
                # 「允许她玩游戏」菜单项已去掉（2026-09-24 用户要求）：
                # 玩游戏属于「自主控制」的一部分 —— 主人开口随时能玩，
                # 她自己想玩由「自主操作」开关决定，不再单独设开关。
                try:
                    from tool import plugins as _plg2
                    _act_pl = item(_ai, "启用插件", checked=_plg2.enabled())
                    _act_pl.setToolTip("插件放在项目根目录的 plugins\ 里：每个文件夹一个 plugin.json + main.py，"
                                       "她就能多一项本事（比如内置的「系统信息」）。")
                    _act_pl.triggered.connect(lambda on=False: _plg2.set_enabled(bool(on)))
                    _act_pldir = item(_ai, "打开插件目录")
                    _act_pldir.triggered.connect(lambda: __import__("os").startfile(_plg2._root()))
                except Exception:
                    pass
                try:
                    from tool import web_search as _ws3
                    _act_ws = item(_ai, "允许联网搜索", checked=_ws3.enabled())
                    _act_ws.setToolTip("开启后她能上网查东西：你问「今天天气」「最新公告」这类，"
                                       "她会去搜（cn.bing.com 优先，百度备用，只读取标题与摘要）。")
                    _act_ws.triggered.connect(lambda on=False: _ws3.set_enabled(bool(on)))
                except Exception:
                    pass
                try:
                    from tool import desire as _dz2
                    _act_lv = item(_ai, "自主活跃度：%s（点击切换）" % _dz2.level_label())
                    _act_lv.setToolTip(
                        "安静：不主动开口、不主动动手（只回应你，提醒照常）。" + chr(10) +
                        "适中：现在的节奏。" + chr(10) +
                        "活跃：更愿意开口、间隔更短、更常自己找事做（想放歌、想看看你在忙什么）。" + chr(10) +
                        "写进 config.json 的 autonomy_level。")
                    _act_lv.triggered.connect(self._cycle_autonomy)
                except Exception:
                    pass
                _act_study = item(_ai, "让她现在学点什么")
                _act_study.setToolTip("立刻让她自习一次，结果显示在小窗口里（要先打开上面的「自主学习」）。")
                _act_study.triggered.connect(self._study_now)
            except Exception as _epc:
                print(f"[桌宠] ⚠ 电脑与学习菜单项失败: {_epc}")

            # ── ③ 界面 ▸ ──
            try:
                _ui = submenu(menu, "界面")
                _act_qb = item(_ui, "显示快捷按钮（对话 / 菜单）", checked=self._quick_buttons_enabled())
                _act_qb.setToolTip("关掉后立绘右上角那两个小按钮会隐藏；右键菜单和点对话框打字照旧可用。")
                _act_qb.triggered.connect(self._toggle_quick_buttons)
                _act_pos = item(_ui, "自动挪回屏幕内", checked=self._auto_clamp_enabled())
                _act_pos.setToolTip(
                    "默认关闭——桌宠位置完全由你说了算，即使有一部分在屏幕外也不会被挪动。" + chr(10) +
                    "打开后：立绘尺寸变化时她会自己挪回屏幕内（旧版行为）。")
                _act_pos.triggered.connect(lambda on=False: self._toggle_auto_clamp(bool(on)))
            except Exception:
                pass
            return menu
        except Exception as e:
            print(f"[桌宠] ⚠ 构造换装菜单失败: {e}")
            return None

    def _has_fgimages_set(self, set_name: str) -> bool:
        """角色是否有某套立绘素材（决定要不要给「切换立绘类型」入口）"""
        try:
            from pets.pet_registry import get_fgimages_dir, get_fgimages_prefix
            d = get_fgimages_dir()
            if not d:
                return False
            p = os.path.join(d, f"{get_fgimages_prefix()}{set_name}.txt")
            return os.path.exists(p)
        except Exception:
            return False

    def _current_set(self):
        """当前显示的立绘体系（a/b）"""
        s = str(getattr(self, "_display_set", "") or "")
        if s in ("a", "b"):
            return s
        t = str(self.portrait_target or "")
        return t[-1] if t[-1:] in ("a", "b") else (portrait_type or "a")

    def _sync_config_portrait(self, set_name):
        """同步 config.json 的 portrait：AI 选层/情绪立绘也按当前立绘体系生成"""
        try:
            _p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "config.json")
            with open(_p, encoding="utf-8") as f:
                _cfg = json.load(f)
            if _cfg.get("portrait") == set_name:
                return
            _cfg["portrait"] = set_name
            with open(_p, "w", encoding="utf-8") as f:
                json.dump(_cfg, f, ensure_ascii=False, indent=4)
            print(f"[桌宠] 🧩 立绘体系配置同步为 {set_name}（AI 选层同套）")
        except Exception as e:
            print(f"[桌宠] ⚠ 同步 portrait 配置失败: {e}")

    def _target_for(self, set_name):
        prefix = self._fgimages_prefix or "ムラサメ"
        return f"{prefix}{set_name}"

    def _first_portrait_for(self, set_name):
        """某套的默认图层。

        - 单图模式（每个表情一张整图）：固定用角色自己的默认表情整图
        - 图层模式：角色包 portrait_prompts.json 的 first_portrait（如丛雨）"""
        if self._portrait_mode == "single" and self._single_default_layers:
            return list(self._single_default_layers)
        try:
            fp = ((self._portrait_sets or {}).get(set_name) or {}).get("first_portrait")
            if fp:
                return list(fp)
        except Exception:
            pass
        return list(self.first_portrait or [])

    def _current_body_layer(self, set_name=None) -> int:
        """当前正穿着的身体层（服装或换臂动作）——AI 某句没给身体层时沿用它"""
        try:
            s = set_name if set_name in ("a", "b") else self._current_set()
            from tool.portrait_outfit import body_layers_of
            body = body_layers_of(s)
            for x in (getattr(self, "_last_portrait_layers", None) or []):
                try:
                    xi = int(x)
                except Exception:
                    continue
                if xi in body:
                    return xi
            # 实时图层里找不到身体层（AI 那句只给了表情/装饰）→ 按保存的装扮兜底，
            # 与实际显示的兜底逻辑一致，避免上层拿到 0 之后误判"现在没穿衣服"。
            try:
                from tool.portrait_outfit import load_outfit
                _of = load_outfit(s)
                _b = int(_of.get("action_id") or 0) or int(_of.get("cloth_id") or 0)
                if _b:
                    return _b
            except Exception:
                pass
        except Exception:
            pass
        return 0

    def _current_expr_layer(self, set_name=None) -> int:
        """当前正显示的表情层——AI 某句没给表情时沿用它，免得这张脸突然变回基础脸"""
        try:
            s = set_name if set_name in ("a", "b") else self._current_set()
            from tool.portrait_outfit import _tables_for
            emos = set(int(v) for v in _tables_for(s, getattr(self, "_pet_id", None))["emotion"].keys())
            body = set()
            try:
                from tool.portrait_outfit import body_layers_of, _decor_ids_of
                body = body_layers_of(s) | _decor_ids_of(s)
            except Exception:
                pass
            for x in reversed(list(getattr(self, "_last_portrait_layers", None) or [])):
                try:
                    xi = int(x)
                except Exception:
                    continue
                if xi in emos and xi not in body:
                    return xi
        except Exception:
            pass
        return 0

    def _switch_cloth(self, cloth_name):
        """换装：保存到【当前显示那套】的配置（QQ/桌宠共用）→ 立即重新合成桌宠立绘"""
        try:
            from tool.portrait_outfit import save_outfit, clothes_of
            cur_set = self._current_set()
            # ★ 先确认这件衣服的素材还在：缺失就直接拒绝（否则会合成空图 → 桌宠透明）
            try:
                from pets.pet_registry import get_fgimages_dir, get_fgimages_prefix
                _fg = get_fgimages_dir(self._pet_id)
                _cid = next((int(c) for n, c, _h in clothes_of(cur_set) if n == cloth_name), 0)
                if _fg and _cid:
                    _png = os.path.join(_fg, "%s%s_%d.png" % (get_fgimages_prefix(self._pet_id),
                                                              cur_set, _cid))
                    if not os.path.exists(_png):
                        print(f"[桌宠] ⚠ 「{cloth_name}」的立绘素材不存在（正式版已移除）→ 保持当前服装")
                        return
            except Exception as _e:
                print(f"[桌宠] ⚠ 换装素材检查失败（继续尝试）: {_e}")
            if not save_outfit(cloth_name, set_name=cur_set):
                return
            print(f"[桌宠] 👗 {cur_set} 立绘已换装: {cloth_name}（QQ 立绘同步生效）")
            from tool.portrait_outfit import swap_body, load_outfit
            _of = load_outfit(cur_set)
            layers = getattr(self, "_last_portrait_layers", None) or self._first_portrait_for(cur_set)
            layers = swap_body(layers, cur_set, _of.get("cloth_id") or 0)   # 立刻换成新衣服
            # ⚠ 先把"当前图层"设成新图层：这是主人主动换的，
            #   不然 update_portrait 里的「服装粘性」会把它当成 AI 乱换而改回去
            self._last_portrait_layers = list(layers)
            self._last_outfit_ts = time.time()
            if self._has_fgimages:
                self.update_portrait(self.portrait_target, list(layers))
        except Exception as e:
            print(f"[桌宠] ⚠ 换装失败: {e}")

    def _fill_decor_menu(self, sub, cur_set, decs, cur):
        """把「装饰」放进一个可滚动的页面：装饰多时限制高度、支持滚轮，不会撑大菜单"""
        try:
            from PyQt5.QtWidgets import (QScrollArea, QWidget, QVBoxLayout, QCheckBox,
                                         QWidgetAction, QLabel)
            from PyQt5.QtCore import Qt
            from tool.pet_menu import item as _menu_item
            from tool.pet_menu import style_decor_page as _style_page
            box = QWidget()
            lay = QVBoxLayout(box)
            lay.setContentsMargins(8, 6, 8, 6)
            lay.setSpacing(4)
            chosen = set(int(x) for x in (cur.get("decor") or []))
            for name, did in decs:
                cb = QCheckBox(name)
                cb.setChecked(did in chosen)
                cb.stateChanged.connect(
                    lambda _s, d=did, c=cb: self._toggle_decor(d, c.isChecked()))
                lay.addWidget(cb)
            btn_row = QWidget()
            from PyQt5.QtWidgets import QHBoxLayout, QPushButton
            br = QHBoxLayout(btn_row)
            br.setContentsMargins(0, 0, 0, 0)
            b_clear = QPushButton("全部取消")
            b_clear.clicked.connect(lambda: self._toggle_decor(0, False, clear_all=True))
            br.addWidget(b_clear)
            lay.addWidget(btn_row)
            area = QScrollArea()
            area.setWidgetResizable(True)
            area.setFrameShape(QScrollArea.NoFrame)
            area.setWidget(box)
            area.setMinimumWidth(240)
            try:
                _style_page(area, box)
            except Exception:
                pass
            # 高度上限：装饰再多也只显示这么高，用滚轮看剩下的
            area.setMaximumHeight(min(300, 34 + 26 * max(1, len(decs))))
            area.setMinimumHeight(min(120, area.maximumHeight()))
            area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            wa = QWidgetAction(sub)
            wa.setDefaultWidget(area)
            sub.addAction(wa)
            sub.addSeparator()
            sub.addAction("↑↓ 用滚轮查看全部装饰").setEnabled(False)
        except Exception as e:
            print(f"[桌宠] ⚠ 构造装饰页失败: {e}")
            for name, did in decs:      # 兜底：退化成普通勾选项
                act = _menu_item(sub, name, checked=(int(did) in set(int(x) for x in (cur.get("decor") or []))))
                act.triggered.connect(lambda checked=False, d=did: self._toggle_decor(d, checked))

    def _toggle_decor(self, decor_id, checked, clear_all=False):
        """勾选/取消装饰：写共享配置并立刻重画（装饰不改变衣服，按情绪随时增减）"""
        try:
            from tool.portrait_outfit import save_outfit, load_outfit
            cur_set = self._current_set()
            cur = set(int(x) for x in (load_outfit(cur_set).get("decor") or []))
            if clear_all:
                cur = set()
            elif decor_id:
                cur.add(int(decor_id)) if checked else cur.discard(int(decor_id))
            if not save_outfit(None, set_name=cur_set, decor=sorted(cur)):
                return
            print(f"[桌宠] 🎀 {cur_set} 装饰已更新: {sorted(cur)}")
            from tool.portrait_outfit import swap_body
            layers = list(getattr(self, "_last_portrait_layers", None) or [])
            if not layers:
                layers = self._first_portrait_for(cur_set)
            from tool.portrait_outfit import _decor_ids_of
            dec_ids = _decor_ids_of(cur_set)
            layers = [x for x in layers if int(x) not in dec_ids] + sorted(cur)
            self._last_portrait_layers = list(layers)
            if self._has_fgimages:
                self.update_portrait(self.portrait_target, layers)
        except Exception as e:
            print(f"[桌宠] ⚠ 切换装饰失败: {e}")

    def _switch_action(self, action_name):
        """换动作（手臂姿势）：保存到当前那套的配置 → 立即重新合成"""
        try:
            from tool.portrait_outfit import save_outfit
            cur_set = self._current_set()
            if not save_outfit(None, set_name=cur_set,
                               action=action_name if action_name else 0):
                return
            print(f"[桌宠] 🤸 {cur_set} 立绘动作已切换: {action_name or '默认姿势'}")
            from tool.portrait_outfit import swap_body, load_outfit
            _of = load_outfit(cur_set)
            layers = getattr(self, "_last_portrait_layers", None) or self._first_portrait_for(cur_set)
            layers = swap_body(layers, cur_set, _of.get("action_id") or _of.get("cloth_id") or 0)
            self._last_portrait_layers = list(layers)
            self._last_outfit_ts = time.time()
            if self._has_fgimages:
                self.update_portrait(self.portrait_target, list(layers))
        except Exception as e:
            print(f"[桌宠] ⚠ 切换动作失败: {e}")

    def _debug_available(self) -> bool:
        """调试模式是否可用：**只有开发版有**。

        判定方式：正式版已移除剧情（story/ 目录不存在），开发版保留 → 用它当版本标记。
        """
        try:
            import os as _os
            _b = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
            return _os.path.isdir(_os.path.join(_b, "story"))
        except Exception:
            return False

    def _debug_obey(self) -> bool:
        """调试模式：无条件服从（换装不需要"明确指令"、AI 选什么就是什么）

        ⚠ 直接读 config.json 文件（不走任何封装/缓存）——菜单里一勾选就立即生效。
        ⚠ 正式版没有调试模式（_debug_available() 为假时一律按关闭处理）。
        """
        if not self._debug_available():
            return False
        try:
            import json as _json
            with io.open("./config.json", encoding="utf-8") as f:
                return str(_json.load(f).get("debug_obey", "false")).strip().lower() in (
                    "true", "1", "yes", "on")
        except Exception:
            return False

    def _toggle_debug_obey(self, checked=None):
        """右键菜单切换到调试模式（写回 config.json，立即生效）"""
        try:
            from tool.config import get_config
            cfg = get_config("./config.json")
            want = (not self._debug_obey()) if checked is None else bool(checked)
            cfg["debug_obey"] = "true" if want else "false"
            import json as _json
            with io.open("./config.json", "w", encoding="utf-8") as f:
                _json.dump(cfg, f, ensure_ascii=False, indent=2)
            print(f"[桌宠] 🛠 调试模式：{'开启（无条件服从）' if want else '关闭'}")
        except Exception as e:
            print(f"[桌宠] ⚠ 切换调试模式失败: {e}")

    def _toggle_auto_switch(self, checked=None):
        """右键菜单：切换「自动切换立绘类型」并写入 config.json（立即生效）"""
        try:
            import json as _json
            from tool.config import get_config
            cfg = get_config("./config.json")
            if checked is None:
                val = "false" if self._auto_switch_enabled() else "true"
            else:
                val = "true" if checked else "false"
            cfg["portrait_auto_switch"] = val
            with open("./config.json", "w", encoding="utf-8") as f:
                _json.dump(cfg, f, ensure_ascii=False, indent=2)
            print(f"[桌宠] 🔁 自动切换立绘类型已{'开启' if val == 'true' else '关闭'}（已写入 config.json）")
        except Exception as e:
            print(f"[桌宠] ⚠ 保存自动切换开关失败: {e}")

    def _switch_portrait_set(self, new_set):
        """手动切换立绘体系（a/b）：持久保存 + 透明过渡动画。

        ⚠ 只换画法，不换衣服：把当前装扮（服装/动作/装饰）按名字搬到目标套，
          否则 b 套会用自己那套默认装扮 → 看起来像"切类型把衣服换了"。"""
        try:
            if new_set == self._current_set():
                return
            try:
                from tool.portrait_outfit import set_active, carry_layers, carry_outfit
                # 优先按【画面上正穿着的】搬；没有画面记录才退回"存档那套"
                _cur = list(getattr(self, "_last_portrait_layers", None) or [])
                _moved = carry_layers(self._current_set(), new_set, _cur,
                                      getattr(self, "_pet_id", None)) if _cur else []
                if not _moved:
                    carry_outfit(self._current_set(), new_set, getattr(self, "_pet_id", None))
                set_active(new_set)
            except Exception as _e:
                print(f"[桌宠] ⚠ 搬运装扮失败: {_e}")
            self._sync_config_portrait(new_set)
            self._crossfade_to(new_set)
        except Exception as e:
            print(f"[桌宠] ⚠ 切换立绘类型失败: {e}")

    # ── a/b 立绘灵动切换（回复/说话时概率触发，透明渐变过渡）──
    _CROSSFADE_PROB = 0.35

    def _maybe_crossfade_set(self):
        """回复/说话时按概率换成另一套立绘（仅当同款服装两套都有时），
        带透明过渡动画：先渐隐当前立绘，再渐显新立绘。"""
        try:
            if not self._has_fgimages or self.is_live2d_mode():
                return
            # ★ 自动切换开关（config.json: portrait_auto_switch，默认开）
            if not self._auto_switch_enabled():
                return
            # ★ 过渡动画进行中不重复触发（否则两段动画互相覆盖 → 视觉上像两套立绘叠在一起）
            if getattr(self, "_fade_state", None):
                return
            import random
            from tool.portrait_outfit import (load_outfit, common_cloths, resolve_cloth,
                                               carry_layers, actions_of)
            cur = self._current_set()
            other = "b" if cur == "a" else "a"
            # ⚠ 存下来的衣服名可能是别名（"刀装"/"刀装（换臂姿势）"），共通表里写的是"刀服" →
            #   不归一化就永远判"两套没有同款" → 这个功能一直是死的（用户反馈"从没见过"）。
            _cloth = str((load_outfit(cur) or {}).get("cloth") or "")
            try:
                _cloth = resolve_cloth(_cloth) or _cloth
            except Exception:
                pass
            if _cloth not in common_cloths():
                return
            # 能不能"换套不换衣服"：先按当前装扮整套搬过去；
            # 搬不过去（最常见的是"换臂姿势"另一套没有同款）就退一步，
            # 只搬「衣服+发型+表情」，丢掉手臂姿势层 —— 衣服保持不变，只换立绘视角/姿势。
            _cur_layers = list(getattr(self, "_last_portrait_layers", None) or [])
            _carried = []
            try:
                if _cur_layers:
                    _carried = carry_layers(cur, other, _cur_layers,
                                            getattr(self, "_pet_id", None), save=False) or []
                if not _carried and _cur_layers:
                    # ⚠ 必须按"衣服名字"找这一套里的身体层，不能用动作层自己的
                    #   "所属服装层"字段：裸（无衣着）标的是 1948，压根不在服装表里，
                    #   拿去搬运会被兜底成便服 → 裸体一换视角就穿上便衣（实测踩过）。
                    #   名字不在表里（裸体 / 内衣这类）→ 直接不切，保持原样。
                    from tool.portrait_outfit import clothes_of
                    _body_cur = 0
                    try:
                        _tb = {n: c for n, c, _h in clothes_of(cur)}
                        _body_cur = int(_tb.get(_cloth) or 0)
                    except Exception:
                        _body_cur = 0
                    # 她现在是不是裸体/内衣这类"非常规衣服"？是的话一律不换视角：
                    # b 套没有裸体层，一换就会被兜底穿上便服（用户反馈的问题）。
                    _nude_now = False
                    try:
                        from tool.portrait_outfit import describe_layers as _dl
                        _live_body = int(self._current_body_layer(cur) or 0)
                        _dd = _dl([_live_body], cur, getattr(self, "_pet_id", None)) if _live_body else ""
                        _nude_now = any(k in (_dd or "") for k in ("裸", "内衣", "无衣着"))
                    except Exception:
                        _nude_now = False
                    if _body_cur and not _nude_now:
                        _acts_cur = {int(a) for _n, a, _o in
                                     actions_of(cur, getattr(self, "_pet_id", None)) if a}
                        _plain, _seen = [], set()
                        for x in _cur_layers:
                            _v = int(x) if str(x).isdigit() else None
                            _v2 = _body_cur if (_v is not None and _v in _acts_cur) else _v
                            if _v2 is not None:
                                if _v2 in _seen:
                                    continue
                                _seen.add(_v2)
                            _plain.append(_v2 if _v2 is not None else x)
                        if _plain and _plain != _cur_layers:
                            _carried = carry_layers(cur, other, _plain,
                                                    getattr(self, "_pet_id", None), save=False) or []
                            if _carried:
                                print("[桌宠] 🧩 自动切换：手臂姿势另一套没有 → 只换视角，衣服不变")
            except Exception as _e:
                print(f"[桌宠] ⚠ 自动切换的装扮搬运失败: {_e}")
                _carried = []
            if not _carried:
                return
            if random.random() > self._CROSSFADE_PROB:
                return
            self._crossfade_to(other, layers=_carried)
        except Exception as e:
            print(f"[桌宠] ⚠ 立绘灵动切换失败: {e}")

    def _start_layer_fade(self, new_pm, target, ms=320, steps=8):
        """同一套立绘内换衣服：旧图渐隐 → 新图渐显（复用 _fade_tick 的动画）"""
        try:
            old = QPixmap(self.pixmap())
            from PyQt5.QtCore import QSize
            w = max(old.width(), new_pm.width(), 1)
            h = max(old.height(), new_pm.height(), 1)
            canvas = QSize(w, h)
            self._fade_id += 1
            self._fade_state = {"id": self._fade_id,
                                "pm_out": self._pad_pixmap(old, canvas),
                                "pm_in": self._pad_pixmap(new_pm, canvas),
                                "target": str(target or ""),
                                "n": max(1, int(steps)), "i": 0,
                                "step_ms": max(16, int(ms) // (2 * max(1, int(steps))))}
            self._fade_tick()
        except Exception as e:
            print(f"[桌宠] ⚠ 换装渐隐失败（直接切换）: {e}")
            try:
                self.setPixmap(new_pm)
            except Exception:
                pass

    def _crossfade_to(self, new_set, ms=320, steps=8, layers=None):
        """透明过渡切换立绘体系：先渐隐当前立绘 → 再渐显新立绘（窗口透明，透出桌面）"""
        try:
            # 注意：QLabel.pixmap() 返回的是内部对象的包装（非独立副本），
            # 直接跨帧持有会在下一次 setPixmap 后变成悬空对象 → 必须先深拷贝
            old = QPixmap(self.pixmap())
            target = self._target_for(new_set)
            # 用「这套保存的装扮」（已按名字从另一套搬好）→ 换类型不换衣服
            try:
                from tool.portrait_outfit import carry_layers, saved_layer_list
                _cur = list(getattr(self, "_last_portrait_layers", None) or [])
                _layers = list(layers or [])
                if not _layers:
                    _layers = carry_layers(self._current_set(), new_set, _cur,
                                           getattr(self, "_pet_id", None), save=False) if _cur else []
                if not _layers:
                    _layers = saved_layer_list(new_set, getattr(self, "_pet_id", None),
                                               like_layers=_cur)
            except Exception:
                _layers = []
            if not _layers:
                _layers = self._first_portrait_for(new_set)
            new_pm = self._compose_pixmap(target, _layers)
            if new_pm is None or new_pm.isNull():
                return
            # ★ 两套立绘尺寸不同：统一到同一画布（小的补透明），并把窗口先调到该尺寸，
            #   否则过渡帧会只覆盖一部分 → 看起来像两套立绘重叠/残留
            from PyQt5.QtCore import QSize
            w = max(old.width(), new_pm.width(), 1)
            h = max(old.height(), new_pm.height(), 1)
            canvas = QSize(w, h)
            old = self._pad_pixmap(old, canvas)
            new_pm = self._pad_pixmap(new_pm, canvas)
            try:
                self.resize(canvas)
            except Exception:
                pass
            self._display_set = new_set
            self.portrait_target = target
            self._last_portrait_layers = list(_layers)
            self.first_portrait = self._first_portrait_for(new_set)
            print(f"[桌宠] 🧩 立绘类型切换 → {new_set} 套（透明过渡）")
            self._fade_id += 1
            self._fade_state = {"id": self._fade_id, "pm_out": old.copy(),
                                "pm_in": QPixmap(new_pm),
                                "target": str(target or ""),      # 记录目标套：目标变了要立刻结束旧淡入
                                "n": max(1, int(steps)), "i": 0,
                                "step_ms": max(16, int(ms) // (2 * max(1, int(steps))))}
            self._fade_tick()
        except Exception as e:
            self._fade_state = None
            print(f"[桌宠] ⚠ 立绘过渡切换失败: {e}")

    def _fade_tick(self):
        """渐变一帧：前半段渐隐旧立绘，后半段渐显新立绘"""
        try:
            st = getattr(self, "_fade_state", None)
            if not st or st.get("id") != self._fade_id:
                return
            # ★ 看门狗：渐变正常 320ms 结束；万一某一帧丢了（系统卡顿/异常），
            #   状态会在 2.5 秒后强制收尾，绝不把立绘长时间留在半透明状态。
            import time as _tf
            st.setdefault("t0", _tf.time())
            if _tf.time() - float(st.get("t0") or 0) > 2.5:
                fin = st.get("pm_in")
                self._fade_state = None
                if fin is not None and not fin.isNull():
                    self.setPixmap(fin)
                    self.update()
                print("[桌宠] ⚠ 立绘渐变超时 → 强制收尾（防止半透明卡住）")
                return
            i, n = st["i"], st["n"]
            pm = st["pm_out"] if i < n else st["pm_in"]
            a = (1.0 - i / float(n)) if i < n else ((i - n) / float(n))
            if pm is not None and not pm.isNull():
                faded = self._alpha_pixmap(pm, a)
                self.setPixmap(faded if faded is not None else pm)
                self.update()
            st["i"] = i + 1
            if st["i"] <= 2 * n:
                QTimer.singleShot(st["step_ms"], self._fade_tick)
            else:
                fin = st.get("pm_in")
                self._fade_state = None
                if fin is not None and not fin.isNull():
                    self.setPixmap(fin)
                    self._ensure_window_fits_pixmap(fin)
                    self.resize(fin.size())
                    self.update()
        except Exception as e:
            self._fade_state = None
            print(f"[桌宠] ⚠ 立绘渐变帧失败: {e}")

    @staticmethod
    def _pad_pixmap(pm, size, center_x=False):
        """把 pixmap 画到指定尺寸的透明画布上，尺寸已一致则原样返回。

        默认左上对齐；center_x=True 时水平居中 —— 用于"同一套立绘只放宽不放窄"：
        角色保持在中间，不会被补出来的透明边挤到一边。"""
        try:
            if pm is None or pm.isNull():
                return pm
            # ★ 画布只放大、绝不裁切：源图比目标宽时，原来的
            #   drawPixmap(max(0, 负偏移)) 会把立绘右半边切掉（用户反馈"立绘只显示一半"）。
            w = max(int(size.width()), pm.width(), 1)
            h = max(int(size.height()), pm.height(), 1)
            if pm.width() == w and pm.height() == h:
                return pm
            out = QPixmap(w, h)
            out.fill(Qt.transparent)
            p = QPainter(out)
            if p.isActive():
                _dx = int((w - pm.width()) / 2) if center_x else 0
                p.drawPixmap(max(0, _dx), 0, pm)
                p.end()
            return out
        except Exception:
            return pm

    # 换装的"正当理由"关键词（主人这句话里出现 → 允许换衣服）
    _FIT_KW = ("换衣", "换件", "换套", "换上", "换了", "换身", "穿上", "脱", "睡衣", "睡袍", "寝衣",
               "校服", "制服", "便服", "私服", "巫女服", "和服", "刀服", "泳装", "体操服", "裸",
               "洗澡", "去睡", "该睡", "睡觉", "出门", "祭典", "下雨", "太热", "好冷")
    _FIT_COOLDOWN = 900          # 秒：距上次换装不足这个时间，就不因为"时间流逝"自己换

    def _outfit_change_allowed(self) -> bool:
        """现在允许换衣服吗：**只有主人这条消息里明确要求**才允许。

        ⚠ 以前还有两条"自己换"的口子：① 距上次换装超过 15 分钟（_FIT_COOLDOWN）
          就放行「时间流逝自然换衣」；② 进程刚启动时 _last_outfit_ts 为 0 也一路放行。
        结果就是主人正常聊天时，桌宠自己换上便服/便衣（用户反馈"对话时还是会变成
        便服"）。现在一律以主人的要求为准：没提换衣服，就一直穿着身上这件。
        """
        try:
            # 调试模式：无条件服从（换装不再要求明确指令）
            if self._debug_obey():
                return True
            txt = ""
            for m in reversed(getattr(self, "history", []) or []):
                if isinstance(m, dict) and m.get("role") == "user":
                    txt = str(m.get("content") or "")
                    break
            # ★ 必须是"明确的换装指令"才算：光提到衣服、天气、出门、睡觉不算。
            #   否则主人正常聊天（"今天好冷""我出门了""该睡了"）AI 就会顺手换一身
            #   ——用户反馈的"还是会突然变成便服"就是这么来的。
            _VERBS = ("换衣", "换件", "换套", "换上", "换了", "换身", "换个衣", "去换", "给我换",
                      "穿上", "穿件", "脱掉", "脱了", "脱下来", "脱", "裸", "别穿了", "别穿")
            return any(v in txt for v in _VERBS)
        except Exception:
            return False

    # 主人点名要的衣服（调试模式下必须照做）
    _CMD_CLOTH = (
        ("睡衣", ("睡衣", "睡袍", "寝衣", "寝間着", "睡衣裤", "睡衣吧")),
        ("制服", ("制服", "校服")),
        ("私服", ("私服", "便服", "便衣")),
        ("刀服", ("刀服", "刀装", "和装")),
        ("裸", ("裸", "全裸", "脱光", "脱掉", "脱了", "别穿", "不穿", "无衣着")),
    )

    def _commanded_cloth(self):
        """返回主人这句点名的服装在【当前这套】里的 (名字, 身体层id)，没点名返回 ("", 0)"""
        try:
            txt = ""
            for m in reversed(getattr(self, "history", []) or []):
                if isinstance(m, dict) and m.get("role") == "user":
                    txt = str(m.get("content") or "")
                    break
            if not txt:
                return ("", 0)
            from tool.portrait_outfit import clothes_of, body_layers_of, load_outfit
            s = self._current_set()
            tbl = {str(n): int(c) for n, c, _h in clothes_of(s)}
            bodies = set(body_layers_of(s))
            for canon, keys in self._CMD_CLOTH:
                if not any(k in txt for k in keys):
                    continue
                if canon == "裸":                       # 裸体：找不带衣服的那层
                    for lid in sorted(bodies):
                        try:
                            from tool.portrait_outfit import describe_layers
                            d = describe_layers([lid], s, getattr(self, "_pet_id", None)) or ""
                        except Exception:
                            d = ""
                        if any(k in d for k in ("裸", "无衣着", "下着", "内衣")):
                            return ("裸", int(lid))
                    return ("", 0)
                for name, cid in tbl.items():
                    if canon in name or name in canon:
                        return (name, int(cid))
            return ("", 0)
        except Exception as e:
            print(f"[桌宠] ⚠ 解析主人点名的服装失败: {e}")
            return ("", 0)

    def _sticky_outfit(self, target, layers):
        try:
            if self._debug_obey():
                # ★ 主人点名的衣服 → 直接换上（不依赖 AI 是否挑对）
                try:
                    _cname, _cid = self._commanded_cloth()
                    if _cid:
                        from tool.portrait_outfit import (apply_outfit, load_outfit, swap_body,
                                                          save_outfit)
                        _s = str(target or "")[-1:]
                        _s = _s if _s in ("a", "b") else self._current_set()
                        _out = swap_body(list(layers or []), _s, _cid)
                        print(f"[桌宠] 🛠 调试模式：按主人命令换装 → {_cname}({_cid})")
                        try:
                            save_outfit(_cname, set_name=_s)
                        except Exception:
                            pass
                        self._last_outfit_ts = time.time() if hasattr(self, "_last_outfit_ts") else 0
                        return _out
                except Exception as _ce:
                    print(f"[桌宠] ⚠ 调试模式按命令换装失败（走 AI 选择）: {_ce}")
            if self._debug_obey():            # 调试模式：AI 挑什么穿什么（不再强制同款连贯）
                print("[桌宠] 🛠 调试模式：按 AI 给的图层显示（不强制同款）")
                from tool.portrait_outfit import apply_outfit, load_outfit
                _s = str(target or "")[-1:]
                _s = _s if _s in ("a", "b") else self._current_set()
                return apply_outfit(layers, _s, load_outfit(_s),
                                    fallback_body=self._current_body_layer(_s),
                                    fallback_expr=self._current_expr_layer(_s))
        except Exception as _e:
            print(f"[桌宠] ⚠ 调试模式换装失败（走常规逻辑）: {_e}")
        """同一段对话里衣服不要突然变：AI 每句都可能挑不同的服装，
        只有「主人要求 / 它自己说要换 / 隔了很久」才真的换，否则沿用当前这件
        （表情、动作、装饰照旧随情绪变）。"""
        try:
            s = str(target or "")[-1:]
            s = s if s in ("a", "b") else self._current_set()
            from tool.portrait_outfit import body_layers_of, swap_body
            body = body_layers_of(s)
            if not body:
                return layers
            _ids = [int(x) for x in (layers or [])
                    if str(x).strip().lstrip("-").isdigit()]
            new_body = next((x for x in _ids if x in body), 0)
            cur = [int(x) for x in (getattr(self, "_last_portrait_layers", None) or [])
                   if str(x).strip().lstrip("-").isdigit()]
            if not cur:
                # 首帧（还没有"当前衣服"）：直接用 AI 给的，并记下时间戳，
                # 免得紧接着的第一句又无理由换一次（那就是"衣服突然变了"）
                if new_body:
                    self._last_outfit_ts = time.time()
                return layers
            cur_body = next((x for x in cur if x in body), 0)
            if not cur_body or not new_body or cur_body == new_body:
                if new_body and new_body != cur_body:
                    self._last_outfit_ts = time.time()
                return layers
            if self._outfit_change_allowed():
                self._last_outfit_ts = time.time()
                print(f"[桌宠] 👗 换装：{new_body}")
                # ★ 把这次换装写回"保存的装扮"。不写回会连环出错：
                #   ① 右键菜单的「当前：X」和勾选读的是保存值 → 换装后菜单还显示上一件
                #     （用户反馈"便装后右键菜单却还是显示裸体"）；
                #   ② 之后某句 AI 没给身体层时的兜底、a/b 换视角的搬运也读保存值
                #     → 裸体聊两句就被兜底穿回便服（用户反馈"裸体对话还是会变成便服"）。
                try:
                    from tool.portrait_outfit import (save_outfit, cloth_name,
                                                      resolve_cloth, describe_layers, actions_of)
                    _nm, _act_name = "", ""
                    try:
                        _nm = str(cloth_name(int(new_body)) or "")
                    except Exception:
                        _nm = ""
                    try:
                        for _n, _a, _o in actions_of(s, getattr(self, "_pet_id", None)):
                            if int(_a or 0) == int(new_body):
                                _act_name = str(_n)
                                _nm = _nm or str(resolve_cloth(_n) or "")
                                break
                    except Exception:
                        pass
                    if not _nm:
                        _d = describe_layers([int(new_body)], s, getattr(self, "_pet_id", None)) or ""
                        if "衣服：" in _d:
                            _nm = _d.split("衣服：")[-1].split("；")[0].strip()
                    if _nm:
                        save_outfit(_nm, set_name=s, action=_act_name or 0)
                        print(f"[桌宠] 👗 已记录当前穿着：{_nm}{(' · ' + _act_name) if _act_name else ''}")
                except Exception as _e:
                    print(f"[桌宠] ⚠ 记录换装失败（不影响显示）: {_e}")
                return layers
            print(f"[桌宠] 👗 保持当前服装（本句想换 {new_body} → 沿用 {cur_body}）")
            return swap_body(layers, s, cur_body)
        except Exception as e:
            print(f"[桌宠] ⚠ 服装粘性处理失败: {e}")
            return layers

    def _auto_switch_enabled(self) -> bool:
        """立绘类型自动切换开关（config.json: portrait_auto_switch）

        ⚠ 默认必须与启动器界面一致（界面默认「开」）。之前这里写的 "false"，
          而界面滑块默认 "true"、配置里又常常没这个键 → 界面显示开着、实际不生效，
          用户反馈「从没见过 a/b 自动切换」就是这个。
          不想要这个效果：设置里关掉，或右键菜单取消勾选「自动切换立绘类型」。"""
        try:
            from tool.config import get_config
            v = get_config("./config.json").get("portrait_auto_switch", "true")
            return str(v).strip().lower() in ("true", "1", "on", "yes")
        except Exception:
            return False

    @staticmethod
    def _alpha_pixmap(pm, alpha):
        """返回带整体透明度的 pixmap（用于立绘渐变过渡）；失败时返回原图（直接切换）"""
        try:
            a = max(0.0, min(1.0, float(alpha)))
            if a >= 0.999 or pm is None or pm.isNull():
                return pm
            out = QPixmap(pm.size())
            if out.isNull():
                return pm
            out.fill(Qt.transparent)
            p = QPainter(out)
            if not p.isActive():
                return pm
            p.setOpacity(a)
            p.drawPixmap(0, 0, pm)
            p.end()
            return out
        except Exception:
            return pm

    def _open_fgimages_dir(self):
        try:
            from pets.pet_registry import get_fgimages_dir
            import subprocess as _sp
            d = get_fgimages_dir()
            if d and os.path.isdir(d):
                _sp.Popen(["explorer", os.path.normpath(d)],
                          creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0))
        except Exception as e:
            print(f"[桌宠] ⚠ 打开立绘素材位置失败: {e}")

    # 鼠标移动事件
    def _in_text_box(self, x, y) -> bool:
        """这个点是不是落在对话框（文字区）里"""
        try:
            return self._text_rect().contains(int(x), int(y))
        except Exception:
            return False

    def _poll_hover(self):
        """轮询光标是否落在对话框上（与窗口是否激活无关）"""
        try:
            from PyQt5.QtGui import QCursor as _QC
            pos = self.mapFromGlobal(_QC.pos())
            inside = self.rect().contains(pos) and self._in_text_box(pos.x(), pos.y())
            self._set_hover_box(bool(inside))
        except Exception:
            pass

    def _set_hover_box(self, on: bool):
        """切换"鼠标在对话框上"的状态（提示画在框里，不只靠 tooltip）"""
        try:
            if bool(on) == bool(getattr(self, "_hover_box", False)):
                return
            self._hover_box = bool(on)
            print("[桌宠] " + ("🖱 鼠标在对话框上 → 提示「点这里打字」"
                              if on else "🖱 鼠标离开对话框 → 恢复显示对话内容"))
            if on:
                self.setCursor(Qt.IBeamCursor)
                self.setToolTip("点这里打字（可以直接和我说话）")
            else:
                self.setCursor(Qt.ArrowCursor)
                self.setToolTip("")
            self.update()
        except Exception:
            pass

    def enterEvent(self, event):
        # 从别的窗口移回来也要重新判断（否则提示会一直不显示）
        try:
            super().enterEvent(event)
        except Exception:
            pass
        try:
            _p = self.mapFromGlobal(self.cursor().pos())
            if not self.is_busy_reply() and self._in_text_box(_p.x(), _p.y()):
                self._set_hover_box(True)
        except Exception:
            pass

    def leaveEvent(self, event):
        try:
            super().leaveEvent(event)
        except Exception:
            pass
        self._set_hover_box(False)

    def mouseMoveEvent(self, event):
        # ⓪ 悬停在快捷按钮上 → 平滑高亮
        try:
            self._ui_hover_to(self._ui_button_at(event.x(), event.y()))
        except Exception:
            pass

        # ⓪ 悬停在对话框上 → 提示"这里是打字的地方"（否则老是点到身体区域，
        #    触发了摸头/摸身反应、把她带进"思考"状态 —— 用户反馈）
        try:
            self._set_hover_box(not self.is_busy_reply() and
                                self._in_text_box(event.x(), event.y()))
        except Exception:
            pass

        # ① 触摸区域：按住拖动超过阈值 → 判定为“抚摸”，触发一次反应
        if self._touch_hit and self._touch_press is not None and not self._touch_fired:
            _dx = abs(event.x() - self._touch_press[0])
            _dy = abs(event.y() - self._touch_press[1])
            if (_dx + _dy) > 18:
                self._fire_touch(self._touch_hit, "stroke")
                self._touch_fired = True

        # ② 兼容旧的“摸头”：在头部区域左右晃 ≥50px 也算抚摸
        if self.touch_head and self.head_press_x is not None and not self._touch_fired:
            if abs(event.x() - self.head_press_x) > 50:
                self._fire_touch("head", "stroke")
                self._touch_fired = True
                self.touch_head = False

        # 中键拖动窗口
        if self.offset is not None and event.buttons() == Qt.MiddleButton:
            self.move(self.pos() + event.pos() - self.offset)

    # 鼠标释放事件
    def mouseReleaseEvent(self, event):
        # 她还在思考/说话 → 松开也不触发任何触摸反应（避免"点了就有反应"）
        try:
            if self.is_busy_reply():
                self._touch_hit = None
                self._touch_fired = True
                self.touch_head = False
                self.setCursor(Qt.ArrowCursor)
                return
        except Exception:
            pass
        if event.button() == Qt.LeftButton:
            # 触摸区域：按住没怎么动 → 判定为“轻点”
            if self._touch_hit and not self._touch_fired:
                self._fire_touch(self._touch_hit, "tap")
            self._touch_hit = ""
            self._touch_press = None
            self._touch_fired = False
            self.touch_head = False
            self.head_press_x = None
            self.setCursor(Qt.ArrowCursor)  # 恢复箭头

        elif event.button() == Qt.MiddleButton:
            self.offset = None
            self.setCursor(Qt.ArrowCursor)  # 拖动结束也要恢复箭头

    # ── 触摸互动 ────────────────────────────────────────
    def _touch_area_at(self, x, y, w=None, h=None):
        """像素坐标 → 命中的触摸区域键（未启用触摸时返回空）

        w/h：坐标所属控件的宽高（Live2D 模式下是模型控件；不传就用桌宠窗口的）。
        """
        try:
            if not getattr(self, "_touch_enabled", True) or not self._touch_areas:
                return ""
            from tool.touch_areas import hit_area
            self._use_touch_set()          # 显示模式可能刚被切换 → 用对应那一套
            areas = {k: v for k, v in (self._touch_areas or {}).items()
                     if k not in (getattr(self, "_touch_disabled_set", set()) or set())}
            _w = max(1, int(w or self.width()))
            _h = max(1, int(h or self.height()))
            return hit_area(areas, x / _w, y / _h)
        except Exception as e:
            print(f"[桌宠] ⚠ 触摸命中判定失败: {e}")
            return ""

    # ── Live2D 模式的触摸：事件来自模型控件（文字层是点击穿透的）──
    def _l2d_touch_pressed(self, x, y):
        try:
            wid = getattr(self, "_live2d_widget", None)
            w = wid.width() if wid is not None else None
            h = wid.height() if wid is not None else None
            area = self._touch_area_at(x, y, w, h)
            self._touch_hit = area or ""
            self._touch_press = (x, y)
            self._touch_fired = False
            if area:
                print(f"[桌宠] 👆 Live2D 触摸按下命中: {area}")
        except Exception as e:
            print(f"[桌宠] ⚠ Live2D 触摸按下处理失败: {e}")

    def _l2d_touch_moved(self, x, y):
        try:
            if not getattr(self, "_touch_hit", "") or self._touch_press is None:
                return
            if getattr(self, "_touch_fired", False):
                return
            if abs(x - self._touch_press[0]) + abs(y - self._touch_press[1]) > 18:
                self._fire_touch(self._touch_hit, "stroke")
                self._touch_fired = True
        except Exception as e:
            print(f"[桌宠] ⚠ Live2D 触摸拖动处理失败: {e}")

    def _l2d_touch_released(self, x, y):
        try:
            if getattr(self, "_touch_hit", "") and not getattr(self, "_touch_fired", False):
                self._fire_touch(self._touch_hit, "tap")
            self._touch_hit = ""
            self._touch_press = None
            self._touch_fired = False
        except Exception as e:
            print(f"[桌宠] ⚠ Live2D 触摸松开处理失败: {e}")

    def _fire_touch(self, key, gesture):
        # 注意：这里**不再**因为她正忙就不反应 —— 触摸是主人的动作，应当照常有反应，
        # 她的接话由 start_thread 的队列负责（说完再回），所以没必要把触摸丢掉。
        try:
            pass
        except Exception:
            pass
        """触发触摸反应：把「主人摸了摸你的XX」交给模型（与摸头同一条通路）"""
        try:      # 心情/好感：被摸头/被摸都会高兴（长期状态）
            from tool import state as _stt
            _up = 3.0 if str(key) == "head" else 2.0
            _af = 0.3 if str(key) == "head" else 0.15
            _stt.feel(_up, _af, "主人摸了摸她（%s）" % key)
        except Exception:
            pass
        try:
            from tool.touch_areas import reaction
            from pets.pet_registry import get_active_pet_id as _ap
            line = reaction(key, gesture, _ap())
            if not line:
                return
            print(f"[桌宠] 👆 触摸 {key}({gesture}) → {line}")
            # 只走模型的正式回应（对话框显示的就是云端生成的那句话）
            # 触摸是主人的动作 → 按"主人发起"处理：
            # 会显示「思考中…」、忙碌时会排队（而不是被当作系统观察直接跳过）
            self.start_thread(line, role="user")
        except Exception as e:
            print(f"[桌宠] ⚠ 触摸反应失败: {e}")

    def _touch_mode_key(self) -> str:
        """当前该用哪一套触摸区域（2D / Live2D 各自独立）"""
        try:
            return "live2d" if getattr(self, "_live2d_mode", False) else "2d"
        except Exception:
            return "2d"

    def _use_touch_set(self):
        """按当前显示模式切换到对应那一套区域 + 禁用表"""
        k = self._touch_mode_key()
        try:
            self._touch_areas = (self._touch_sets or {}).get(k) or {}
            self._touch_disabled_set = (self._touch_disabled or {}).get(k) or set()
        except Exception:
            pass

    def reload_touch_areas(self):
        """重新读取该角色的触摸区域（编辑器保存后立刻生效；两套一起刷新）"""
        try:
            from tool.touch_areas import get_pet_areas, touch_enabled, get_disabled
            from pets.pet_registry import get_active_pet_id
            pid = get_active_pet_id()
            self._touch_pid = pid
            self._touch_sets = {"2d": get_pet_areas(pid, "2d"),
                                "live2d": get_pet_areas(pid, "live2d")}
            self._touch_disabled = {"2d": set(get_disabled(pid, "2d")),
                                    "live2d": set(get_disabled(pid, "live2d"))}
            self._touch_enabled = touch_enabled(pid)
            self._use_touch_set()
            k = self._touch_mode_key()
            print(f"[桌宠] 🔄 触摸区域已刷新（{k}：{len(self._touch_areas)} 个，"
                  f"禁用 {len(getattr(self, '_touch_disabled_set', set()) or set())} 个）")
        except Exception as e:
            print(f"[桌宠] ⚠ 刷新触摸区域失败: {e}")

    # 文字区域矩形（按「角色配置的对话框区域」优先，其次按立绘/模式自动算）
    def _text_rect(self):
        rect = self._text_rect_raw()
        # ⚠ 归一化并夹回窗口内：F9 调参调出来的偏移可能是负的（或很大），
        #   经 adjusted() 之后会出现「右边界跑到左边界左边 / 下边界跑到上边界上面」的
        #   无效矩形 → drawText 什么都不画（用户看到的就是"文字消失/被遮挡"）。
        try:
            r = self.rect()
            w, h = max(1, r.width()), max(1, r.height())
            left = max(0, min(rect.left(), w - 40))
            top = max(0, min(rect.top(), h - 24))
            right = min(w, max(rect.right(), left + 40))
            bottom = min(h, max(rect.bottom(), top + 24))
            return QRect(left, top, right - left, bottom - top)
        except Exception:
            return rect

    def _text_rect_raw(self):
        """未夹取的文字区域（按配置/模式算出来，可能越界）"""
        r = self.rect()
        live2d = bool(getattr(self, "_live2d_mode", False))
        ox = int(getattr(self, "_text_offset_x", 0) or 0)
        oy = int(getattr(self, "_text_offset_y", 0) or 0)
        # ① 向导/桌宠设置里可视化调好的对话框区域（归一化 → 任意窗口尺寸都自适应）
        box = getattr(self, "_text_box", None)
        if box and len(box) == 4:
            w, h = max(1, r.width()), max(1, r.height())
            x0 = int(round(w * float(box[0]))) + ox
            y0 = int(round(h * float(box[1]))) + oy
            bw = max(60, int(round(w * float(box[2]))))
            bh = max(28, int(round(h * float(box[3]))))
            x0 = max(0, min(x0, max(0, w - 40)))
            y0 = max(0, min(y0, max(0, h - 20)))
            return QRect(x0, y0, min(bw, w - x0), min(bh, h - y0))
        # ② 旧布局（未配置对话框区域的老角色）
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

    # ══════════ 立绘右上角：对话 / 菜单 快捷按钮 ══════════
    def _enter_game_mode(self):
        """游戏/全屏时：只把桌宠自己的进程优先级降到最低。

        ⚠ 主人明确要求：**不要动屏幕识别，也要继续主动搭话**。
          所以这里不暂停截屏/摄像头线程、不卸载视觉模型——只降优先级，
          让调度器优先伺候游戏，她该看屏幕、该搭话都照旧。
        """
        try:
            from tool import perf_guard as _pg
            _pg.set_process_priority(True)      # Idle：永远排在游戏后面
            print("[桌宠] 🎮 游戏/全屏中：桌宠进程优先级降到最低（识别与搭话照常）")
        except Exception as e:
            print(f"[桌宠] ⚠ 进入游戏模式失败: {e}")

    def _exit_game_mode(self):
        """游戏结束：优先级回到"低于正常"（其余本来就没改）"""
        try:
            from tool import perf_guard as _pg
            _pg.set_process_priority(False)
            print("[桌宠] ▶ 游戏结束：优先级恢复（低于正常）")
        except Exception as e:
            print(f"[桌宠] ⚠ 退出游戏模式失败: {e}")

    def _screen_index_now(self) -> int:
        """当前配置里选的显示器序号（抓屏用）"""
        try:
            from tool.config import get_config
            return int(get_config("./config.json").get("screen_index") or 0)
        except Exception:
            return 0

    def _screen_interval_seconds(self) -> float:
        """定时截屏的间隔（config 的 screen_interval，秒）"""
        try:
            from tool.config import get_config
            return max(10.0, float(get_config("./config.json").get("screen_interval") or 150))
        except Exception:
            return 150.0

    def _auto_clamp_enabled(self) -> bool:
        """是否允许"自动把桌宠挪回屏幕内"（config.json 的 auto_clamp_position）

        ⚠ 默认**关**：主人明确要求"位置即使在屏幕外面也不要改变位置"
          （他想把桌宠停在屏幕边缘或外面）。想恢复旧行为就在右键菜单里打开。
        """
        try:
            from tool.config import get_config
            v = get_config("./config.json").get("auto_clamp_position", "false")
            return str(v).strip().lower() in ("true", "1", "on", "yes")
        except Exception:
            return False

    def _toggle_auto_clamp(self, on: bool = False):
        """菜单开关：自动挪回屏幕内"""
        try:
            from tool.config import get_config
            import json as _json
            cfg = dict(get_config("./config.json") or {})
            cfg["auto_clamp_position"] = "true" if on else "false"
            import os as _os
            p = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "config.json")
            tmp = p + ".tmp"
            with io.open(tmp, "w", encoding="utf-8") as f:
                _json.dump(cfg, f, ensure_ascii=False, indent=2)
            _os.replace(tmp, p)
            self._offscreen_logged = False
            print(f"[桌宠] 自动挪回屏幕内 → {'已开启' if on else '已关闭（位置保持不动）'}")
        except Exception as e:
            print(f"[桌宠] ⚠ 写入开关失败: {e}")

    def _quick_buttons_enabled(self) -> bool:
        """快捷按钮是否显示（config.json 的 pet_quick_buttons，可在菜单里关）"""
        try:
            v = get_config("./config.json").get("pet_quick_buttons", True)
            if isinstance(v, str):
                return v.strip().lower() not in ("false", "0", "no", "off")
            return bool(v)
        except Exception:
            return True

    def _toggle_quick_buttons(self):
        """菜单里开关这两个按钮（写入 config.json，立即生效）"""
        try:
            on = not self._quick_buttons_enabled()
            try:
                from tool.config import get_config as _gc
                cfg = dict(_gc("./config.json") or {})
            except Exception:
                cfg = {}
            cfg["pet_quick_buttons"] = "true" if on else "false"
            import json as _json
            with open("./config.json", "w", encoding="utf-8") as f:
                _json.dump(cfg, f, ensure_ascii=False, indent=2)
            self._ui_enabled = on
            self._sync_quick_buttons()
            self.update()
            print("[桌宠] 快捷按钮（对话 / 菜单）%s" % ("已显示" if on else "已隐藏"))
        except Exception as e:
            print(f"[桌宠] ⚠ 切换快捷按钮失败: {e}")

    def _ui_icon(self, name: str):
        """按钮图标（ui/chat.png / ui/menu.png），按尺寸缓存"""
        try:
            key = str(name)
            if key in self._ui_pix:
                return self._ui_pix[key]
            pm = QPixmap()
            try:
                from tool.paths import app_base_dir
                base = app_base_dir()
            except Exception:
                base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            fp = os.path.join(base, "ui", "chat.png" if key == "chat" else "menu.png")
            if os.path.isfile(fp):
                src = QPixmap(fp)
                # 1170×1170 的源图先缩到 256 存着：动画逐帧缩放时几乎不耗时
                if not src.isNull() and src.width() > 256:
                    src = src.scaled(256, 256, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                pm = src
            self._ui_pix[key] = pm
            return pm
        except Exception:
            return QPixmap()

    def _sync_quick_buttons(self):
        """把两个小按钮摆到立绘右上角（竖排），并按开关显示/隐藏"""
        try:
            btns = getattr(self, "_ui_btns", None)
            if not btns:
                return
            on = bool(getattr(self, "_ui_enabled", True))
            size = max(34, min(62, int(self.width() * 0.11)))
            gap = max(6, int(size * 0.22))
            m = max(8, int(size * 0.30))
            x = max(4, self.width() - m - size)
            for idx, nm in enumerate(("chat", "menu")):
                b = btns.get(nm)
                if not b:
                    continue
                b.set_size(size)
                b.move(x, m + idx * (size + gap))
                b.setVisible(on)
        except Exception as e:
            print(f"[桌宠] ⚠ 摆放快捷按钮失败: {e}")

    def _ui_layout(self):
        """两个按钮的位置：立绘右上角，竖着排"""
        size = max(34, min(62, int(self.width() * 0.11)))
        gap = max(6, int(size * 0.24))
        m = max(8, int(size * 0.30))
        x = max(4, self.width() - m - size)
        self._ui_btn_rects = {
            "chat": QRect(x, m, size, size),
            "menu": QRect(x, m + size + gap, size, size),
        }
        return self._ui_btn_rects

    def _ui_button_at(self, x, y) -> str:
        if not getattr(self, "_ui_enabled", True):
            return ""
        try:
            for name, r in self._ui_layout().items():
                if r.contains(int(x), int(y)):
                    return name
        except Exception:
            pass
        return ""

    def _ui_anim_to(self, target: float):
        """悬停/按下的平滑过渡（180ms，OutCubic）"""
        try:
            a = self._ui_anim_obj
            if a is None:
                a = QVariantAnimation(self)
                a.setDuration(150)
                a.setEasingCurve(QEasingCurve.OutCubic)
                a.valueChanged.connect(self._ui_anim_step)
                self._ui_anim_obj = a
            a.stop()
            a.setStartValue(float(getattr(self, "_ui_anim_v", 0.0)))
            a.setEndValue(float(target))
            a.start()
        except Exception:
            pass

    def _ui_btn_repaint_rect(self):
        """两个按钮合起来的那一小块（含放大余量）——动画只重画这里，省掉整窗重绘"""
        try:
            rs = self._ui_btn_rects or self._ui_layout()
            r = QRect()
            for x in rs.values():
                r = r.united(x.adjusted(-12, -12, 12, 12))
            return r if not r.isNull() else None
        except Exception:
            return None

    def _ui_anim_step(self, v):
        try:
            self._ui_anim_v = float(v)
            r = self._ui_btn_repaint_rect()
            if r is not None:
                self.update(r)
            else:
                self.update()
        except Exception:
            pass

    def _ui_hover_to(self, name: str):
        if name != getattr(self, "_ui_hover", ""):
            self._ui_hover = name
            self._ui_anim_to(1.0 if name else 0.0)
            try:
                if name:
                    self.setCursor(Qt.PointingHandCursor)
            except Exception:
                pass

    def _ui_press_clear(self):
        self._ui_press = ""
        r = self._ui_btn_repaint_rect()
        self.update(r) if r is not None else self.update()

    def _enter_input_mode(self):
        """点「对话」：直接进入打字模式（不用去点对话框）"""
        try:
            self._trigger_input_mode()          # 内含"她还在忙"的判断与提示
            if getattr(self, "input_mode", False):
                self.setFocus()
                try:
                    self._set_ime(True)
                except Exception:
                    pass
                self.update()
        except Exception as e:
            print(f"[桌宠] ⚠ 进入输入模式失败: {e}")

    def _exit_input_mode(self):
        """退出打字模式（和按 Esc 一样的收尾；再点一次「对话」按钮也能退出）"""
        try:
            self.input_mode = False
            self.input_buffer = ""
            self.preedit_text = ""
            self._set_ime(False)
            try:
                # ⚠ 只有 Live2D 模式才该恢复"点击穿透"（那是给模型上层的文字层用的）。
                #   普通 2D 模式下执行这句 = 把**桌宠自己的窗口**整个变成鼠标穿透，
                #   点它、点按钮全都没反应，而且没有别的路径会把它关回来
                #   （用户反馈"有时候点不了桌宠和按钮"，实测窗口扩展样式确实是 0x800A8，
                #   含 WS_EX_TRANSPARENT）。
                if self._live2d_mode:
                    self._set_overlay_click_through(True)
            except Exception:
                pass
            self.display_text = getattr(self, "_last_real_text", "") or ""
            self.update()
            print("[桌宠] ⌨ 已退出输入模式（再点「对话」可重新进入）")
        except Exception as e:
            print(f"[桌宠] ⚠ 退出输入模式失败: {e}")

    def _toggle_input_mode(self):
        """「对话」按钮：没在输入就进入，已经在输入就退出（用户要求）"""
        try:
            if getattr(self, "input_mode", False):
                self._exit_input_mode()
            else:
                self._enter_input_mode()
        except Exception as e:
            print(f"[桌宠] ⚠ 切换输入模式失败: {e}")

    def _ui_pair_pixmap(self, hover, press, step):
        """把「两个按钮当前状态」预渲染成一张图，动画每帧只要一次 drawPixmap。

        之前每帧都要重新缩放图标 + 分批绘制，转场就掉帧（用户反馈卡）。
        """
        rects = self._ui_layout()
        union = QRect()
        for x in rects.values():
            union = union.united(x.adjusted(-12, -12, 12, 12))
        ck = (hover, press, int(step), union.width(), union.height(),
              int(rects["chat"].width()))
        cache = getattr(self, "_ui_pair_cache", None)
        if cache is None:
            cache = {}
            self._ui_pair_cache = cache
        pm = cache.get(ck)
        if pm is not None:
            return pm, union
        pm = QPixmap(union.size())
        pm.fill(Qt.transparent)
        pt = QPainter(pm)
        pt.setRenderHint(QPainter.Antialiasing, True)
        pt.setRenderHint(QPainter.SmoothPixmapTransform, True)
        k = max(0.0, min(1.0, float(step) / 10.0))
        for name, r in rects.items():
            _h = (hover == name)
            _p = (press == name)
            kk = k if (_h or _p) else 0.0
            grow = 1.0 + 0.10 * kk - (0.07 if _p else 0.0)
            size = int(r.width() * grow)
            cx, cy = r.center().x() - union.x(), r.center().y() - union.y()
            rr = QRect(cx - size // 2, cy - size // 2, size, size)
            ipm = self._ui_icon(name)
            if ipm is not None and not ipm.isNull():
                sc = ipm.scaled(rr.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                pt.setOpacity(0.88 + 0.12 * kk)
                pt.drawPixmap(rr.center().x() - sc.width() // 2,
                              rr.center().y() - sc.height() // 2, sc)
                pt.setOpacity(1.0)
            else:
                pt.setPen(QColor(255, 250, 245, 230))
                f = QFont(self.text_font)
                f.setPointSize(max(11, int(rr.width() * 0.36)))
                pt.setFont(f)
                pt.drawText(rr, Qt.AlignCenter, "聊" if name == "chat" else "≡")
        pt.end()
        if len(cache) > 48:
            cache.clear()
        cache[ck] = pm
        return pm, union

    def _draw_ui_buttons(self, painter):
        """（已停用：按钮改成独立小控件 PetQuickButton，见 _sync_quick_buttons）"""
        return
        try:
            _upd = painter.clipBoundingRect()
            _u = QRect()
            for _r in (self._ui_btn_rects or self._ui_layout()).values():
                _u = _u.united(_r.adjusted(-14, -14, 14, 14))
            if not _u.isNull() and not _upd.intersects(_u):
                return          # 这次重绘跟按钮无关（比如文字变了）→ 不画
        except Exception:
            pass
        _hover = getattr(self, "_ui_hover", "")
        _press = getattr(self, "_ui_press", "")
        _k = max(0.0, min(1.0, float(getattr(self, "_ui_anim_v", 0.0))))
        _step = int(round(_k * 10))
        pm, union = self._ui_pair_pixmap(_hover, _press, _step)
        if pm is not None and not pm.isNull():
            painter.drawPixmap(union.topLeft(), pm)
        return

    def paintEvent(self, event):
        # 1. 先调用 QLabel 默认的绘制（画立绘 / 背景）
        super().paintEvent(event)

        # 2. 再叠加绘制文字
        # 记录最后一句真实文字；并做状态自检：
        # 只要文字是思考中而她其实并不忙（思考已结束 / 回复失败没产生文字），
        # 就立刻恢复上一句 —— 不管是哪条代码路径写进去的，都不会一直卡着。
        try:
            _t = str(getattr(self, "display_text", "") or "")
            if ("思考中" in _t) or getattr(self, "_busy_hint_on", False):
                if not self.is_busy_reply():
                    self.display_text = getattr(self, "_last_real_text", "") or ""
                    self._thinking_on = False
                    self._busy_hint_on = False
                    print("[桌宠] 并不在思考 -> 自动恢复上一句（思考提示自愈）")
                    self.update()
            elif _t.strip() and "思考中" not in _t:
                self._last_real_text = _t
                self._thinking_on = False
        except Exception:
            pass
        _draw_text = str(getattr(self, "display_text", "") or "")
        # ★ 性能：按钮动画每帧只要求重画右上角一小块 —— 若这块不碰文字区，
        #   就整段跳过文字绘制（带描边+自动换行的文字是全窗口最贵的一笔）。
        try:
            _upd = event.rect()
            _trect = self._text_rect()
            if _draw_text and not _upd.intersects(_trect):
                _draw_text = ""
        except Exception:
            pass
        # ★ 输入模式提示常显：她的回复会把 display_text 覆盖掉，之前提示就没了
        #   （用户反馈"明明可以输入文字，对话框却没有提示"）
        if getattr(self, "input_mode", False):
            try:
                _r = self._text_rect()
                if _r.width() > 40 and _r.height() > 12:
                    _p2 = QPainter(self)
                    _p2.setRenderHint(QPainter.TextAntialiasing, True)
                    _f2 = QFont(self.text_font)
                    try:
                        _f2.setPointSizeF(max(8.0, self.text_font.pointSizeF() * 0.82))
                    except Exception:
                        pass
                    _p2.setFont(_f2)
                    _p2.setPen(QColor(255, 232, 140, 240))
                    _n = len(str(getattr(self, "input_buffer", "") or "") +
                             str(getattr(self, "preedit_text", "") or ""))
                    _hint = "✎ 正在输入…（回车发送 · Esc 取消）" + (f"  已输入 {_n} 字" if _n else "")
                    _hr = QRect(_r.left(), _r.bottom() - int(_r.height() * 0.24),
                                _r.width(), int(_r.height() * 0.24))
                    _p2.drawText(_hr, Qt.AlignHCenter | Qt.AlignBottom, _hint)
                    _p2.end()
            except Exception as _e2:
                pass

        if _draw_text:  # 过滤掉空字符串和 None
            # 设置绘图环境
            painter = QPainter(self)  # 在这个控件上绘制
            painter.setRenderHint(QPainter.Antialiasing, True)  # 抗锯齿
            painter.setRenderHint(QPainter.TextAntialiasing, True)  # 文字抗锯齿
            painter.setFont(self.text_font)

            text_rect = self._text_rect()

            # 如果有换行就靠左对齐，否则居中
            if "\n" in self.display_text:
                align_flag = Qt.AlignLeft | Qt.AlignBottom | Qt.TextWordWrap
            else:
                align_flag = Qt.AlignHCenter | Qt.AlignBottom | Qt.TextWordWrap

            # 文字描边（黑色）：细笔画描边 —— 小字号只用 1px 笔 + 4 方向，
            # 否则 8 次偏移会把小字糊成一圈「糊边」
            border_size = max(1, int(getattr(self, "border_size", 1) or 1))
            _px = int(getattr(self, "_font_px", 14) or 14)
            _offs = (1, 2) if _px >= 22 else (1,)
            painter.setPen(QColor(44, 22, 28))
            for _k in _offs:
                _o = max(1, int(round(border_size * (1.0 if _k == 1 else 0.6))))
                for dx, dy in ((-_o, 0), (_o, 0), (0, -_o), (0, _o)):
                    painter.drawText(text_rect.translated(dx, dy), align_flag, _draw_text)
            if _px >= 26:
                for dx, dy in ((-border_size, -border_size), (border_size, -border_size),
                               (-border_size, border_size), (border_size, border_size)):
                    painter.drawText(text_rect.translated(dx, dy), align_flag, _draw_text)

            # 文字正体（白色）
            painter.setPen(Qt.white)
            painter.drawText(text_rect, align_flag, _draw_text)

            painter.end()

        # ── 立绘右上角的快捷按钮（对话 / 菜单）──
        try:
            _ui_p = QPainter(self)
            self._draw_ui_buttons(_ui_p)
            _ui_p.end()
        except Exception as _e:
            print(f"[桌宠] ⚠ 快捷按钮绘制失败: {_e}")

    # 更新立绘
    def update_portrait(self, target, layers):
        # 纯 Live2D 角色（无 fgimages 立绘图层面板）：不生成 2D 立绘，避免空画布
        if not self._has_fgimages:
            self.setPixmap(QPixmap())
            return

        # 先过「服装粘性」：AI 每句可能挑不同的衣服，无理由时沿用当前这件
        try:
            layers = self._sticky_outfit(target, layers)
        except Exception as _e:
            print(f"[桌宠] ⚠ 服装粘性处理失败: {_e}")
        # ⚠ 这里必须记【实际显示】的图层（不是 AI 请求的）：粘性判断、右键换装重画、
        #   以及给模型的"我现在穿什么"都以它为准。
        try:
            self._last_portrait_layers = list(layers or [])
        except Exception:
            pass
        try:
            from tool.portrait_outfit import (describe_layers, set_current_look,
                                              set_current_body, load_outfit)
            # 记录"身上这件"给提示词用（AI 没给身体层时按保存的兜底，与实际显示一致）
            try:
                _b = self._current_body_layer(target)
                if not _b:
                    _of2 = load_outfit(str(target or "")[-1:] or None)
                    _b = int(_of2.get("action_id") or 0) or int(_of2.get("cloth_id") or 0)
                set_current_body(_b)
            except Exception:
                pass
            _st = str(target or "")[-1:]
            _desc = describe_layers(layers, _st if _st in ("a", "b") else None,
                                    getattr(self, "_pet_id", None))
            set_current_look(_desc)
            # 每次外观变化打一行日志：万一还有"表情消失"，日志里能直接看出那一句的图层
            if _desc and _desc != getattr(self, "_last_look_desc", ""):
                self._last_look_desc = _desc
                print(f"[桌宠] 👀 当前立绘：{_desc}（图层 {list(layers or [])}）")
        except Exception as _e:
            print(f"[桌宠] ⚠ 记录外观失败: {_e}")
        pixmap = self._compose_pixmap(target, layers)
        if pixmap is None or pixmap.isNull():
            return
        # ★ 兜底：素材全缺时合成出来的是一张极小的空画布 → 直接保留上一帧，
        #   绝不把桌宠刷成透明（用户反馈"点了裸体后桌宠变透明"）。
        try:
            if pixmap.width() < 8 or pixmap.height() < 8:
                print(f"[桌宠] ⚠ 立绘素材缺失（合成结果 {pixmap.width()}x{pixmap.height()}）→ 保留当前立绘")
                return
        except Exception:
            pass
        # 渐变过渡进行中：把新立绘接到"渐显"阶段，动画不中断（做完自动定格）
        st = getattr(self, "_fade_state", None)
        if st and st.get("id") == self._fade_id:
            # ⚠ 目标套（a/b）变了 → 不能接着淡入，否则两张立绘短暂同屏（看着像"两个立绘"）
            if str(st.get("target") or "") == str(target or ""):
                st["pm_in"] = pixmap
                return
            print(f"[桌宠] ℹ 立绘目标套变化（{st.get('target')} → {target}）→ 结束旧淡入")
            try:
                self._fade_id += 1
                self._fade_state = None
            except Exception:
                pass
        # ★ 换衣服也要透明渐变（用户要求）：身体层变了就走和 a/b 切换同一套渐隐渐显，
        #   而不是"啪"地硬切。表情/装饰变化仍然即时切换（它们本来就是逐句在变的）。
        try:
            from tool.portrait_outfit import body_layers_of
            _bs = str(target or "")[-1:]
            _bs = _bs if _bs in ("a", "b") else self._current_set()
            _bodies = set(body_layers_of(_bs))
            _new_b = next((int(x) for x in (layers or [])
                           if str(x).strip().isdigit() and int(x) in _bodies), 0)
            _old_b = int(getattr(self, "_shown_body", 0) or 0)
            if _new_b and _old_b and _new_b != _old_b:
                self._shown_body = _new_b
                self._last_portrait_layers = list(layers or [])
                self._start_layer_fade(pixmap, str(target or ""))
                return
            if _new_b:
                self._shown_body = _new_b
        except Exception as _e:
            print(f"[桌宠] ⚠ 换装渐隐判断失败（改为直接切换）: {_e}")

        # 5. Attach to the QLabel and request a repaint
        self.setPixmap(pixmap)
        self._ensure_window_fits_pixmap(pixmap)      # 图比窗口宽就先放大窗口，别裁图
        self.resize(pixmap.size())
        self.update()
        # 立绘就绪（main.py 等这个标记再显示窗口：服装没加载出来之前不露脸）
        self._portrait_ready = True

    def _compose_pixmap(self, target, layers):
        """按目标立绘体系合成 QPixmap：
        - 图层跨套时自动换算（a↔b 的服装/发型/装饰/表情对应）；
        - 自动穿该套保存的服装（portrait_choice.json）。"""
        try:
            from tool.portrait_outfit import normalize_layers, apply_outfit
            s = None
            t = str(target or "")
            if t[-1:] in ("a", "b"):
                s = t[-1]
            layers = normalize_layers(layers, s)
            layers = apply_outfit(layers, s, fallback_body=self._current_body_layer(s),
                                  fallback_expr=self._current_expr_layer(s))
        except Exception:
            pass

        # 1. Generate the RGBA numpy image
        cv_img = generate_fgimage(target, layers)
        if cv_img is None or cv_img.size == 0:
            return None

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
        self._last_portrait_target = str(target or "")      # 供缩放函数认"哪一套"的画布
        return self._scale_portrait_pixmap(pixmap)

    def resizeEvent(self, event):
        """窗口尺寸一变就重算字号：字号是按文字区宽度算的，
        不重算就会出现"改过尺寸后字还是旧的"（含首次显示的那一帧）。"""
        try:
            super().resizeEvent(event)
        except Exception:
            pass
        try:
            self._update_text_scaling()
        except Exception:
            pass
        self._sync_quick_buttons()

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

        # ── 显示尺寸（2D 立绘自己的设置：pet.json model.display_2d）──
        # 兼容旧键：model.display.portrait_height_ratio / model.portrait_height_ratio
        _d2 = self._display_cfg_2d()
        _ratio = None
        try:
            _r = _d2.get("height_ratio")
            if _r:
                _ratio = max(0.05, min(1.0, float(_r)))
        except Exception:
            _ratio = None
        if _ratio is None:
            try:
                _ratio = float(_pet_cfg.get("model", {}).get("portrait_height_ratio")
                               or DEFAULT_PORTRAIT_SCREEN_RATIO)
            except Exception:
                _ratio = DEFAULT_PORTRAIT_SCREEN_RATIO

        if available_height:
            target_height = int(available_height * _ratio)
        else:
            target_height = pixmap.height()

        # ★ 自动适配：多图层拼合的立绘可能很宽（如 1551x2916 拼出来更宽），
        #   只按高度缩放会超出屏幕 → 这里同时按「可用宽度」限一次，保证完整显示
        try:
            _avail_w = int(screen.availableGeometry().width() * 0.98) if available_height else None
            if _avail_w and target_height > 0 and pixmap.height() > 0:
                _w_at_h = pixmap.width() * (target_height / float(pixmap.height()))
                if _w_at_h > _avail_w:
                    target_height = int(target_height * (_avail_w / _w_at_h))
                    print(f"[桌宠] 立绘较宽 → 自动缩小到屏幕内（高 {target_height}px）")
        except Exception:
            pass
        # 角色自定义缩放（1.0 = 默认）
        try:
            _sc = float(_d2.get("scale") or 1.0)
            if abs(_sc - 1.0) > 0.01:
                target_height = max(60, int(target_height * max(0.2, min(3.0, _sc))))
        except Exception:
            pass

        target_height = max(1, target_height)
        target_height = min(target_height, pixmap.height())

        if pixmap.height() >= 240:
            target_height = max(240, target_height)

        # 计算文本缩放
        scale_factor = target_height / max(1, pixmap.height())
        self._current_scale = max(scale_factor, 0.1)
        self._update_text_scaling()

        out = pixmap.scaledToHeight(target_height, Qt.SmoothTransformation)
        # ★ 稳定画布：同一套立绘 + 同一目标高度下，画布宽度"只增不减"。
        #   合成图宽度 = 当前图层（表情/动作/服装）的包围盒宽度，换一次表情就变一次；
        #   窗口要是跟着缩，对话框（按窗口宽高归一化）就会忽大忽小 ——
        #   用户看到的"说话时对话框变小"就是它。固定画布后窗口尺寸不变，文字框也就稳了。
        try:
            # ★ 画布在 a/b 两套之间共用（只按目标高度记一份）：
            #   两套的立绘宽高比略有差异，各存一份的话切换类型时窗口尺寸会变
            #   → 对话框位置/字号跟着跳，文字还可能被挤出去（用户反馈）。
            #   共用后切换只多出透明边，窗口和对话框完全不动。
            # ★ 用「本进程见过的最大宽度」而不是按高度分键：
            #   target_height 启动时偶尔会差一两像素 → 换个键，"只增不减"的记忆就失效
            #   → 窗口缩回窄图宽度，而图还是宽的 → 右边被裁掉（用户反馈"立绘只显示一半"）。
            key = ("canvas", int(target_height))
            stab = getattr(self, "_stable_canvas", None) or {}
            if not isinstance(stab, dict):
                stab = {}
            cur = stab.get(key) or 0
            if out.width() > cur:
                stab[key] = int(out.width())
            if len(stab) > 6:                      # 换配置/换屏会攒新 key，留最近几份就够
                stab = dict(list(stab.items())[-6:])
            self._stable_canvas = stab
            _w = stab.get(key) or out.width()
            try:
                _mx_ever = int(getattr(self, "_portrait_max_w", 0) or 0)
                if _mx_ever > _w:
                    _w = _mx_ever
            except Exception:
                pass
            # ★ 尺寸锁死：立绘画布一旦定下来，就把窗口固定成"画布尺寸"。
            #   否则 Qt 会按标签（文字+图）的 sizeHint 把窗口撑大（实测启动时 581，
            #   而立绘画布只要 465 → 用户看到"刚出现时大了一圈，对话一次后变小"）。
            #   锁死后：露面那一刻就是最终尺寸，之后一直不变。
            try:
                _lock = self._pad_pixmap(out, QSize(int(_w), out.height()), center_x=True)
                self._portrait_max_w = max(int(getattr(self, "_portrait_max_w", 0) or 0), _lock.width())
                self.setFixedSize(_lock.size())
                self._ensure_window_fits_pixmap(_lock)   # 窗口绝不能比图窄（否则右侧被裁）
                # ⚠ 传目标尺寸进去：setFixedSize 是异步生效的，这里读 self.height() 会是旧值
                #   → 按旧高度算边界会把她放到屏幕下方，下一轮又拉回来（位置乱跳）。
                self._clamp_to_screen(_lock.size())
                # ★ 锁定尺寸后必须按"最终窗口宽度"重算字号：
                #   字号是按文字区宽度算的，而首帧时窗口还是临时尺寸（比最终大一截），
                #   不重算就会出现"刚出现的字比对话一次后大一圈"（用户反馈）。
                self._update_text_scaling()
            except Exception:
                pass
            # ★ 会话内不回缩：同一个目标高度下，窗口宽度只增不减。
            #   原因：a/b 两套的画布宽度不同（实测 484 / 465），换套那一瞬间窗口会
            #   缩一圈 —— 用户看到的就是"刚出现时比对话一次后大一圈"。
            #   宁可多留透明边，也要保证对话框尺寸自始至终一致。
            #   （改显示比例 / 换屏 → 目标高度变了 → 重新量，不影响正常调整。）
            try:
                _floor_h = int(getattr(self, "_canvas_floor_h", 0) or 0)
                _floor = int(getattr(self, "_canvas_floor", 0) or 0)
                if _floor_h != int(target_height):
                    _floor = 0
                # 第一次算画布时不要参考"当前窗口宽度"：那一刻窗口还是 Qt 按标签算的
                # 临时尺寸（实测 581，而立绘只要 465）→ 会把临时尺寸当成标准永久沿用。
                _nw = max(_w, _floor)
                if getattr(self, "_canvas_locked", False):
                    _nw = max(_nw, int(self.width() or 0))
                # 夹一层上限：万一窗口曾被别的东西撑得很大（背景/首帧），
                # 也不能把它当成"标准宽度"永久沿用（最多放宽 25%）
                _cap = int(round(max(_w, _floor or 0) * 1.25))
                if _cap > 0:
                    _nw = min(_nw, _cap)
                if _nw != _w:
                    print("[桌宠] 📐 画布宽度不回缩：%d → %d（避免对话框变小）" % (_w, _nw))
                _w = _nw
                self._canvas_floor = _nw
                self._canvas_floor_h = int(target_height)
                self._canvas_locked = True
            except Exception:
                pass
            # 启动第一次算画布时，顺手把"这套里其它衣服/姿势"的宽度也量一遍，
            # 直接取最宽 —— 否则第一句对话换了姿势画布会"长大一次"，
            # 用户看到的就是"没对话前和对话一次后对话框大小不一样"。
            if not stab.get(key + ("primed",)):
                try:
                    stab[key + ("primed",)] = True
                    _mx = _w
                    from tool.portrait_outfit import clothes_of, actions_of
                    _ids = set()
                    for _n, _c, _h in clothes_of(str(getattr(self, "_last_portrait_target", "") or "")[-1:] or "a"):
                        _ids.add(int(_c))
                    try:
                        for _n, _a, _o in actions_of(str(getattr(self, "_last_portrait_target", "") or "")[-1:] or "a",
                                                     getattr(self, "_pet_id", None)):
                            if _a:
                                _ids.add(int(_a))
                    except Exception:
                        pass
                    _tgt = str(getattr(self, "_last_portrait_target", "") or "")
                    if _tgt and _ids:
                        _extra = [x for x in (list(getattr(self, "_last_portrait_layers", None) or []))
                                  if (not str(x).isdigit()) or int(x) not in _ids]
                        # 用公共几何函数（与"显示与对话框"预览同一套算法）算最宽
                        try:
                            from tool.portrait_geom import canvas_size_for
                            _extra_ids = [int(x) for x in _extra if str(x).strip().isdigit()]
                            # a / b 两套都比一遍，取最宽（共用一个画布）
                            for _sn in ("a", "b"):
                                _cw, _ = canvas_size_for(getattr(self, "_pet_id", None), _sn,
                                                         target_height, _extra_ids)
                                if _cw > _mx:
                                    _mx = int(_cw)
                        except Exception as _ge:
                            print(f"[桌宠] ⚠ 画布宽度计算失败: {_ge}")
                    if _mx > _w:
                        stab[key] = int(_mx)
                        _w = int(_mx)
                        print("[桌宠] 📐 立绘画布预量：最宽 %dpx（避免对话后对话框变大）" % _w)
                except Exception as _e:
                    print(f"[桌宠] ⚠ 画布预量失败（不影响显示）: {_e}")
            if _w > out.width():
                out = self._pad_pixmap(out, QSize(_w, out.height()), center_x=True)
        except Exception as _e:
            print(f"[桌宠] ⚠ 稳定画布计算失败（不影响显示）: {_e}")
        return out

    def _display_cfg_2d(self) -> dict:
        """2D 立绘的显示设置（pet.json model.display_2d；兼容旧的 display.* 键）。

        与 Live2D 的显示设置**完全独立**，互不影响：大小 / 位置各存一份。"""
        out = {}
        try:
            m = (self._pet_cfg.get("model") or {})
            for src in (m.get("display_2d") or {}, m.get("display") or {}):
                for k in ("height_ratio", "scale", "offset_x", "offset_y"):
                    if src.get(k) is not None and k not in out:
                        out[k] = src.get(k)
            if out.get("height_ratio") is None:
                hr = (m.get("display") or {}).get("portrait_height_ratio")
                if hr is not None:
                    out["height_ratio"] = hr
        except Exception:
            pass
        return out

    def _resolve_pet_font(self) -> str:
        """加载项目自带「思源黑体Bold.otf」并返回真实字体族名。

        ⚠ 以前只是把字体文件名当 family 传给 QFont，从没真正加载字体文件 →
        Qt 落到系统兜底字体，小字号下笔画发虚、边缘发糊。"""
        cached = getattr(self, "_font_family_ok", None)
        if cached:
            return cached
        fam = self._font_family
        try:
            from PyQt5.QtGui import QFontDatabase
            here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            for p in (os.path.join(os.getcwd(), "思源黑体Bold.otf"),
                      os.path.join(here, "思源黑体Bold.otf")):
                if os.path.isfile(p):
                    fid = QFontDatabase.addApplicationFont(p)
                    if fid >= 0:
                        fams = QFontDatabase.applicationFontFamilies(fid)
                        if fams:
                            fam = fams[0]
                            print(f"[桌宠] 已加载字体: {os.path.basename(p)} → {fam}")
                            break
        except Exception as e:
            print(f"[桌宠] ⚠ 字体加载失败（用系统字体）: {e}")
        self._font_family_ok = fam
        return fam

    def _update_text_scaling(self):
        """字号 / 左右留白：**按文字区实际宽度**算，任何立绘比例都不会"字太大显示不全"。

        丛雨原值参考：可用宽 430px 左右 → 字号 12px、左右各约 39px。"""
        scale = max(self._current_scale, 0.1)
        # ① 先定左右留白（按窗口宽度比例，且不超过旧算法给的宽度）
        old_margin = max(10, int(round(self._base_text_x_offset * scale)))
        self.text_x_offset = max(8, min(old_margin, max(10, int(round(self.width() * 0.08)))))
        # ② 用新留白算文字区宽度 → 字号（保证任何窗口尺寸都能显示完整）
        try:
            area_w = max(60, int(self._text_rect().width()))
        except Exception:
            area_w = max(60, int(self.width() * 0.7))
        fscale = self._live_font_scale()   # 实时值优先（拖动即时生效、聊天时不回退）
        if getattr(self, "_live2d_mode", False) and not getattr(self, "_text_box", None):
            # Live2D 且没配置对话框区域：沿用原算法（窗口高度 × font_scale），保持老角色现状
            scaled_font_size = max(8, int(round(self._base_font_size * scale * fscale)))
        else:
            # 按文字区宽度定字号：430px → 12px（丛雨原值），窄立绘自动变小 → 显示完整
            scaled_font_size = max(9, int(round(area_w * self._font_ratio * fscale)))
        # 用「像素字号 + 全提示 + 抗锯齿」：小字号下笔画更实，不会有糊边
        _pt = max(6, int(round(scaled_font_size * 1.333)))     # pt → px（保持原有大小观感）
        self.text_font = QFont(self._resolve_pet_font())
        self.text_font.setPixelSize(_pt)
        try:
            self.text_font.setHintingPreference(QFont.PreferFullHinting)
            self.text_font.setStyleStrategy(QFont.PreferAntialias)
        except Exception:
            pass
        self._font_px = _pt

        scaled_y = int(round(self._base_text_y_offset * scale))
        self.text_y_offset = scaled_y if scaled_y < -10 else -10

        # 文字描边（黑边）：小字号时描边要细，否则字周边会糊成一圈
        # （0.08 ≈ 12px 字号 → 1px 描边，与丛雨原观感一致；上限 3px 防大字号糊边）
        self.border_size = max(1, min(3, int(round(scaled_font_size * 0.08))))

    def _live_font_scale(self) -> float:
        """当前生效的字号缩放（实时值优先，其次本模式配置值）"""
        try:
            v = getattr(self, "_font_scale_live", None)
            if v is None:
                v = (self._live2d_font_scale if getattr(self, "_live2d_mode", False)
                     else getattr(self, "_text_font_scale_cfg", 1.0))
            return max(0.4, min(3.0, float(v or 1.0)))
        except Exception:
            return 1.0

    def set_font_scale(self, value, persist=False):
        """实时调整对话框字号缩放（拖动就能看到效果；persist=True 时写入 pet.json）"""
        try:
            v = max(0.4, min(3.0, float(value)))
            self._font_scale_live = v
            if getattr(self, "_live2d_mode", False):
                self._live2d_font_scale = v
            else:
                self._text_font_scale_cfg = v
            self._update_text_scaling()
            self._rewrap_current_text()
            self.update()
            if persist:
                try:
                    from pets.pet_registry import save_live2d_display
                    save_live2d_display(font_scale=v)
                except Exception as _e:
                    print(f"[桌宠] ⚠ 字号写入配置失败: {_e}")
            return v
        except Exception as e:
            print(f"[桌宠] ⚠ 设置字号失败: {e}")
            return None

    def _wrap_for_box(self, text) -> str:
        """按「对话框实际宽度 + 当前字号」逐字换行。

        ⚠ 以前统一用 wrap_text(text)（固定 10 字一行）：对话框宽/字号一变，
        行宽就对不上——行数太多会被裁掉、行太长会超出右边界（用户反馈"文字显示不全"）。
        """
        s = str(text or "")
        if not s:
            return s
        try:
            fm = QFontMetrics(self.text_font)
            max_w = max(40, int(self._text_rect().width()) - 6)
            out = []
            for para in s.split("\n"):
                if not para:
                    out.append("")
                    continue
                line = ""
                for ch in para:
                    if not line:
                        line = ch
                    elif fm.horizontalAdvance(line + ch) <= max_w:
                        line += ch
                    else:
                        out.append(line)
                        line = ch
                out.append(line)
            return "\n".join(out)
        except Exception as e:
            print(f"[桌宠] ⚠ 像素换行失败（回退固定宽度）: {e}")
            return wrap_text(s)

    def _autofit_text(self, text) -> None:
        """文字放不下就自动缩小字号（保证「显示完整、不被裁掉」）"""
        try:
            s = str(text or "")
            if not s:
                return
            avail_h = max(24, int(self._text_rect().height()) - 4)
            for _ in range(8):
                fm = QFontMetrics(self.text_font)
                lines = self._wrap_for_box(s).split("\n")
                need = fm.lineSpacing() * max(1, len(lines))
                if need <= avail_h or int(getattr(self, "_font_px", 12)) <= 9:
                    break
                ratio = max(0.6, float(avail_h) / float(need))
                new_px = max(9, int(int(getattr(self, "_font_px", 12)) * ratio) - 1)
                if new_px >= int(getattr(self, "_font_px", 12)):
                    break
                self.text_font.setPixelSize(new_px)
                self._font_px = new_px
                self.border_size = max(1, min(3, int(round(new_px * 0.06))))
        except Exception as e:
            print(f"[桌宠] ⚠ 文字自适应缩放失败: {e}")

    def _rewrap_current_text(self) -> None:
        """按当前字号重新给现有文字换行（改字号/改窗口大小后调用）"""
        try:
            if not getattr(self, "full_text", ""):
                return
            raw = getattr(self, "_raw_text", "") or self.full_text
            if raw:
                self.full_text = self._wrap_for_box(raw)
        except Exception:
            pass

    # 显示文本及打字机效果
    def show_text(self, text, typing=True):
        # Live2D 模式：确保文字层可见（与 2D 一致——文字持续显示，不被模型遮挡）
        if self._live2d_mode and not self._overlay_visible:
            self._ensure_live2d_overlay()
        # ① 先按当前窗口/缩放刷新字号（实时值优先 → 聊天中不会变回去）
        try:
            self._update_text_scaling()
        except Exception:
            pass
        self._raw_text = str(text or "")
        # ② 像素级换行 + ③ 放不下就自动缩小，保证显示完整
        wrapped_text = self._wrap_for_box(text)
        self._autofit_text(wrapped_text)
        wrapped_text = self._wrap_for_box(text)
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
        # ★ 她正在思考 / 正在说话：键盘输入也不接受（否则"点不了、但打出来的字还显示"）
        try:
            if self.is_busy_reply():
                self.input_buffer = ""
                self.preedit_text = ""
                self.input_mode = False
                self._set_ime(False)
                self._show_busy_hint()
                return
        except Exception:
            pass
        if not self.input_mode:
            # 如果没进入输入模式，交给父类 QLabel 处理
            return super().keyPressEvent(event)

        # ================== 输入模式下 ==================
        if event.key() == Qt.Key_Escape:
            # Esc 取消输入（退出输入模式，恢复 Live2D 点击穿透）
            self.input_mode = False
            self._set_ime(False)      # 退出输入模式 → 关掉输入法
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
            self._set_ime(False)      # 退出输入模式 → 关掉输入法
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
        # ★ 顺手把历史里"装着 JSON 的台词"洗干净（一次性自愈）。
        #   模型偶尔会把整段台词写成 ["[\"…", "\", \"…"] 这种带转义的 JSON 文本，
        #   早先的版本没还原就存进了历史 → 她照着自己的历史学，越说越像 JSON
        #   （用户反馈"对话的文字还是有问题"）。这里在载入时统一还原并写回：
        #   不用主人清记忆，也不会因为桌宠在跑而被内存里的旧数据覆盖回去。
        try:
            self._scrub_history()
        except Exception as _e:
            print(f"[AIpet] ⚠ 历史清洗跳过: {_e}")

    def _scrub_history(self) -> int:
        """把历史里带转义/嵌套 JSON 的台词还原成干净句子（返回修了几条）"""
        try:
            from classes.Worker_class import _unwrap_jsonish
        except Exception:
            return 0
        n = 0
        for msg in list(getattr(self, "history", []) or []):
            if not isinstance(msg, dict):
                continue
            c = str(msg.get("content") or "")
            if not c or ("\\\"" not in c and not c.strip().startswith('["[')):
                continue
            try:
                arr = json.loads(c)
            except Exception:
                arr = [c]
            if not isinstance(arr, list):
                arr = [arr]
            out = []
            try:
                from classes.Worker_class import _clean_json_fragment as _cjf
            except Exception:
                _cjf = None
            for item in arr:
                u = _unwrap_jsonish(str(item))
                if isinstance(u, list):
                    _items = [str(x) for x in u]
                else:
                    _items = [str(u)]
                for _x in _items:
                    if _cjf:
                        _x = _cjf(_x)
                    if str(_x).strip():
                        out.append(str(_x))
            if out:
                msg["content"] = json.dumps(out, ensure_ascii=False)
                n += 1
        if n:
            print(f"[AIpet] 🧹 历史里有 {n} 条台词是带转义的 JSON 文本 → 已还原成干净台词")
            try:
                self._save_history()
            except Exception:
                pass
        return n

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
