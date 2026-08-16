"""PCL 风格主窗口 — Live2D 预览（回退 2D 立绘）+ 所有动画 + 模型管理"""

import os
import sys
import math
import socket
import time
import subprocess
import urllib.request

from PyQt5.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, QAbstractAnimation, QRect, QRectF
)
from PyQt5.QtGui import (
    QPainter, QColor, QPainterPath, QFont, QPixmap, QIcon, QSurfaceFormat, QImage
)
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, QApplication,
    QLabel, QGraphicsOpacityEffect, QPushButton, QOpenGLWidget, QSizePolicy
)

# ===== API 控制 URL =====
_CONTROL_BASE = "http://localhost:28565/control"


def _send_control(feature: str):
    """向桌宠 API 发送控制指令"""
    try:
        req = urllib.request.Request(f"{_CONTROL_BASE}/{feature}", method="POST", data=b"")
        urllib.request.urlopen(req, timeout=5)
        print(f"[PCL] 已发送控制指令: {feature}")
    except Exception as e:
        print(f"[PCL] 控制指令失败 ({feature}): {e}")


def _send_control_raw(url: str):
    """向桌宠 API 发送原始 POST 请求（用于语音开始/结束）"""
    try:
        req = urllib.request.Request(url, method="POST", data=b"")
        resp = urllib.request.urlopen(req, timeout=5)
        resp.read()  # 读取响应体，避免服务器端 ConnectionResetError
        print(f"[PCL] 已发送: {url}")
    except Exception as e:
        print(f"[PCL] 请求失败 ({url}): {e}")

from .colors import *
from .widgets import PCLTitleBar, PCLSidebar, PCLSettingsPanel, PCLLaunchButton, PCLMemoryManager, PCLPetManager, PCLPromptEditor


# ==================== 路径 & Python 探测 ====================

def _app_base_dir() -> str:
    """
    程序根目录（= 绿色版根目录）：
    - frozen(exe) → exe 所在目录（旁有 Live2d/ fgimages/ run.py runtime/venv/ 等，见 build_launcher.py）
    - 源码模式     → 项目根目录
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _find_python(root: str = None) -> str:
    """
    找到可用的 Python 解释器（按优先级）：
    1. <根目录>/runtime/venv/Scripts/python.exe   （绿色版虚拟环境）
    2. <根目录>/python.exe                        （便携版）
    3. 系统 PATH 中的 python
    （frozen 模式下 sys.executable 是 exe 本身，不是 python，排除）

    额外：源码模式下回退 sys.executable（当前解释器）
    返回 None 表示完全找不到。
    """
    base = root or _app_base_dir()
    is_frozen = getattr(sys, 'frozen', False)

    candidates = [
        os.path.join(base, "runtime", "venv", "Scripts", "python.exe"),
        os.path.join(base, "python.exe"),
    ]
    # 源码模式：当前解释器优先（就是 python.exe）
    if not is_frozen:
        candidates.append(sys.executable)

    for cand in candidates:
        if cand and os.path.exists(cand):
            return cand

    # 最后尝试 PATH
    try:
        import shutil
        p = shutil.which("python")
        if p:
            return p
    except Exception:
        pass
    return None


# ==================== Live2D 预览控件 ====================

class Live2DPreviewWidget(QOpenGLWidget):
    """Live2D 预览 — 与 Live2d/live2d_ui.py 保持一致的初始化模式"""

    def __init__(self, model_path: str = None, parent=None,
                 model_scale: float = 1.0, offset_x: float = 0.0, offset_y: float = 0.0):
        super().__init__(parent)
        self._model_path = model_path
        self._model_scale = model_scale
        self._offset_x = offset_x
        self._offset_y = offset_y
        self.model = None
        self._render_ready = False
        self._failed = False
        self._t = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._timer.setInterval(16)
        self.setAutoFillBackground(False)

    def _apply_transform(self):
        """应用按角色的缩放/平移（修复半身模型偏小/头顶鞋子被裁）"""
        if self.model is None:
            return
        try:
            if self._model_scale != 1.0 or self._offset_x != 0.0 or self._offset_y != 0.0:
                self.model.SetScale(self._model_scale)
                self.model.SetOffset(self._offset_x, self._offset_y)
        except Exception:
            pass

    def initializeGL(self):
        try:
            from OpenGL.GL import (
                glEnable, GL_BLEND, GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA,
                glBlendFunc, glClearColor, glClear, GL_COLOR_BUFFER_BIT
            )
            import live2d.v3 as l2d
            try:
                l2d.init()
            except Exception:
                pass
            l2d.glInit()
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            glClearColor(0xea / 255, 0xf2 / 255, 0xfe / 255, 1.0)

            if self._model_path and os.path.exists(self._model_path):
                path = os.path.normpath(os.path.abspath(self._model_path)).replace("\\", "/")
                self.model = l2d.LAppModel()
                self.model.LoadModelJson(path)
                self._apply_transform()
                self._render_ready = True
                print(f"[PCL] Live2D 模型加载成功: {path}")
            else:
                self._failed = True

            self._timer.start()
        except Exception as e:
            self._failed = True
            import traceback
            print(f"[PCL] Live2D init 失败: {e}")
            traceback.print_exc()

    def load_model(self, path: str):
        self._model_path = path
        if not self._render_ready:
            return
        if self.model:
            self.model = None
        self._render_ready = False
        try:
            p = os.path.normpath(os.path.abspath(path)).replace("\\", "/")
            import live2d.v3 as l2d
            self.model = l2d.LAppModel()
            self.model.LoadModelJson(p)
            self._apply_transform()
            self._render_ready = True
        except Exception as e:
            self._failed = True
            print(f"[PCL] Live2D 模型切换失败: {e}")

    def paintGL(self):
        try:
            from OpenGL.GL import glClearColor, glClear, GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT
            glClearColor(0xea / 255, 0xf2 / 255, 0xfe / 255, 1.0)
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        except Exception:
            pass
        if not self._render_ready or self._failed:
            return
        if self.model and self._render_ready:
            try:
                self.model.Update()
                self.model.Draw()
            except Exception:
                pass

    def resizeGL(self, width, height):
        if self.model and self._render_ready:
            self.model.Resize(width, height)

    def _on_tick(self):
        if not self._render_ready:
            self.update()
            return
        self._t += 0.016
        try:
            angle_x = 6 * math.sin(self._t * 0.8)
            body_x = 4 * math.sin(self._t * 0.5 + 1.0)
            angle_y = 3 * math.sin(self._t * 0.6 + 2.0)
            breath = 0.5 + 0.5 * math.sin(self._t * 1.2)
            self.model.SetParameterValue("ParamAngleX", angle_x, 0.5)
            self.model.SetParameterValue("ParamBodyAngleX", body_x, 0.3)
            self.model.SetParameterValue("ParamAngleY", angle_y, 0.4)
            self.model.SetParameterValue("ParamBreath", breath, 0.6)
        except Exception:
            pass
        self.update()


# ==================== 2D 立绘回退预览 ====================

class PortraitPreviewWidget(QLabel):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(200)
        self.setStyleSheet(f"background-color: {Color8.name()}; border-radius: 8px;")
        self._has_model = False
        self._portrait_type = config.get("portrait", "b")
        self._t = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._timer.setInterval(33)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._timer.isActive():
            self._timer.start()
        QTimer.singleShot(100, self._generate_portrait)

    def _generate_portrait(self):
        try:
            from tool.generate import generate_fgimage
            from pets.pet_registry import get_pet_config
            import cv2
            pet_cfg = get_pet_config()
            prefix = pet_cfg.get("model", {}).get("fgimages_prefix", "")
            target = f"{prefix}{self._portrait_type}" if prefix else f"ムラサメ{self._portrait_type}"
            # 默认图层也从角色包读取
            from pets.pet_registry import get_portrait_prompts
            pp = get_portrait_prompts()
            first = pp.get("sets", {}).get(self._portrait_type, {}).get("first_portrait", [1715, 1306, 1719])
            cv_img = generate_fgimage(target, first)
            if cv_img.shape[2] == 4:
                cv_img = cv2.cvtColor(cv_img, cv2.COLOR_RGBA2BGRA)
            h, w, ch = cv_img.shape
            qimg = QImage(cv_img.data, w, h, ch * w, QImage.Format_RGBA8888)
            pixmap = QPixmap.fromImage(qimg)
            scaled = pixmap.scaled(self.width() - 32, self.height() - 16,
                                    Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.setPixmap(scaled)
            self._has_model = True
        except Exception as e:
            self.setText(f"立绘加载失败\n{str(e)[:80]}")
            self.setStyleSheet(f"color: {Gray3.name()}; font-size: 13px; background-color: {Color8.name()};")

    def _on_tick(self):
        self._t += 0.033
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._has_model:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(Gray2)
            painter.setFont(QFont("Microsoft YaHei", 12))
            painter.drawText(self.rect(), Qt.AlignHCenter | Qt.AlignVCenter, "加载中...")
            painter.end()


# ==================== 主窗口 ====================

class PCLMainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self._pet_process = None
        self._running_pet_id = None  # 当前运行的 AI 桌宠角色（互斥/切换用）
        self._config = self._load_config()
        self._selected_model_path = None
        self._model_queue = []
        self._preview_widget = None
        self._pets_by_id = {}      # pet_id -> {"summary", "model_json", "avatar"}
        self._selected_pet_id = None
        self._qq_pet_id = None     # QQ 进程启动时服务的角色

        self._setup_window()
        self.pan_back = QWidget(self)
        self.pan_back.setGeometry(int(8 * S), int(8 * S), int(self.width() - 16 * S), int(self.height() - 16 * S))
        self._build_ui()

        self._fade_timer = QTimer(self); self._fade_step = 0; self._fade_max = 0; self._fade_cb = None; self._fade_effect = None
        self._color_old = ("blue", {}); self._color_new = ("blue", {}); self._color_step = 0; self._color_max = 30
        self._color_timer = QTimer(self); self._color_timer.timeout.connect(self._color_tick)
        self._drag_pos = None
        self._animating = False

        self._discover_models()

    def _load_config(self):
        import json
        base = _app_base_dir()
        path = os.path.join(base, "config.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        # 没有 config.json → 尝试从 example 自动复制
        self._auto_create_config(base)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"portrait": "b"}

    @staticmethod
    def _auto_create_config(base: str):
        """无 config.json 时，从 config.example.json 复制一份"""
        src = os.path.join(base, "config.example.json")
        dst = os.path.join(base, "config.json")
        if os.path.exists(src) and not os.path.exists(dst):
            try:
                import shutil
                shutil.copyfile(src, dst)
                print(f"[PCL] 已从 config.example.json 生成 config.json，请填写 API Key")
            except Exception:
                pass

    def showEvent(self, event):
        super().showEvent(event)
        if self._model_queue and self._preview_widget is None:
            pet_id, path = self._model_queue.pop(0)
            self._preview_pet(pet_id, path)

    def _setup_window(self):
        # 不再置顶：PCL 是普通窗口，可通过任务栏正常最小化（用户反馈）
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        w, h = int(1200 * S), int(900 * S)
        self.setMinimumSize(int(950 * S), int(700 * S))
        self.resize(w, h)

    def _build_ui(self):
        self.titlebar = PCLTitleBar(self)
        self.titlebar.setParent(self.pan_back)
        self.titlebar.setGeometry(0, 0, self.pan_back.width(), int(48 * S))
        self.titlebar.nav_changed.connect(self._switch_page)

        content = QWidget(self.pan_back)
        content.setGeometry(0, int(48 * S), self.pan_back.width(), self.pan_back.height() - int(48 * S))
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0); content_layout.setSpacing(0)

        self.sidebar = PCLSidebar()
        # 阶段 B：点卡片 → 设为活动角色 + 预览对应模型
        self.sidebar.model_selected.connect(self._on_model_selected)
        content_layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack, 1)

        # ===== 预览页 =====
        self.preview_page = QWidget()
        self.preview_layout = QVBoxLayout(self.preview_page)
        self.preview_layout.setContentsMargins(int(16 * S), int(16 * S), int(16 * S), int(16 * S))
        self.preview_layout.setSpacing(int(12 * S))

        # ===== 双启动按钮（桌宠 + QQ）=====
        self._qq_process = None
        btn_row = QHBoxLayout()
        btn_row.setSpacing(int(12 * S))

        self.launch_btn = PCLLaunchButton()
        self.launch_btn.setObjectName("launchPet")
        self.launch_btn.setText("  启动 AIpet 桌宠")
        self.launch_btn.clicked.connect(self._on_launch_clicked)
        btn_row.addWidget(self.launch_btn, 1)

        # QQ 按钮（config qq_enabled="true" 才显示）
        qq_enabled = str(self._config.get("qq_enabled", "false")).lower() == "true"
        self.qq_btn = QPushButton("  💬 启动 QQ AIpet")
        self.qq_btn.setToolTip("启动 QQ 聊天模块（自动启动 NapCat，首次需扫码登录）")
        self.qq_btn.setStyleSheet(f"""
            QPushButton {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 {THEME_COLORS['blue']['btn_start']},stop:1 {THEME_COLORS['blue']['btn_end']});
                color: white; border: none; font-size: {int(14*S)}px; font-weight: bold;
                font-family: 'Microsoft YaHei'; border-radius: {int(8*S)}px; }}
            QPushButton:hover {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 {THEME_COLORS['blue']['btn_end']},stop:1 {THEME_COLORS['blue']['btn_start']}); }}
        """)
        self.qq_btn.setFixedHeight(int(48 * S))
        self.qq_btn.clicked.connect(self._on_qq_clicked)
        if qq_enabled:
            btn_row.addWidget(self.qq_btn, 1)
        btn_row.addStretch(0)
        self.preview_layout.addLayout(btn_row)
        self._qq_btn_visible = qq_enabled

        # ===== 底部功能按钮面板（桌宠启动后才显示）=====
        self.control_panel = QWidget()
        self.control_panel.setFixedHeight(int(56 * S))
        self.control_panel.hide()
        ctrl_layout = QHBoxLayout(self.control_panel)
        ctrl_layout.setContentsMargins(0, int(4 * S), 0, 0)
        ctrl_layout.setSpacing(int(8 * S))

        ctrl_btn = f"""
            QPushButton {{
                background: {Color6.name()};
                color: {Color1.name()};
                border: 1px solid {Color5.name()};
                padding: {int(10*S)}px {int(18*S)}px;
                font-size: {int(12*S)}px;
                font-family: 'Microsoft YaHei';
                border-radius: {int(6*S)}px;
            }}
            QPushButton:hover {{
                background: {Color4.name()};
                color: white;
                border: 1px solid {Color3.name()};
            }}
        """
        self.btn_voice = QPushButton("🎤 按住说话")
        self.btn_voice.setToolTip("长按按钮录音，松开发送语音对话")
        self.btn_voice.setStyleSheet(ctrl_btn)
        # 长按录音交互：按下 → 开始录音 / 松开 → 停止并识别
        self.btn_voice.pressed.connect(lambda: (
            print("[PCL] 语音按钮按下，开始录音"),
            _send_control_raw("http://localhost:28565/voice/start")
        ))
        self.btn_voice.released.connect(lambda: (
            print("[PCL] 语音按钮松开，停止录音并识别"),
            _send_control_raw("http://localhost:28565/voice/end")
        ))

        self.btn_screenshot = QPushButton("🖥️ 屏幕识别")
        self.btn_screenshot.setToolTip("立即进行屏幕截图识别")
        self.btn_screenshot.setStyleSheet(ctrl_btn)
        self.btn_screenshot.clicked.connect(lambda: _send_control("screenshot"))

        self.btn_camera = QPushButton("📷 摄像头识别")
        self.btn_camera.setToolTip("触发摄像头拍照")
        self.btn_camera.setStyleSheet(ctrl_btn)
        self.btn_camera.clicked.connect(lambda: _send_control("camera"))

        self.btn_live2d = QPushButton("🎭 Live2D")
        self.btn_live2d.setToolTip("切换 Live2D 模式")
        self.btn_live2d.setStyleSheet(ctrl_btn)
        self.btn_live2d.clicked.connect(lambda: _send_control("live2d"))

        self.btn_longtext = QPushButton("📝 长文本模式")
        self.btn_longtext.setToolTip("切换长/短文本输出模式")
        self.btn_longtext.setStyleSheet(ctrl_btn)
        self.btn_longtext.clicked.connect(lambda: _send_control("longtext"))

        ctrl_layout.addWidget(self.btn_voice)
        ctrl_layout.addWidget(self.btn_screenshot)
        ctrl_layout.addWidget(self.btn_camera)
        ctrl_layout.addWidget(self.btn_live2d)
        ctrl_layout.addWidget(self.btn_longtext)
        ctrl_layout.addStretch()
        self.preview_layout.addWidget(self.control_panel)

        self.stack.addWidget(self.preview_page)

        self.settings_page = PCLSettingsPanel()
        self.settings_page.size_changed.connect(self._on_size_changed)
        self.settings_page.color_changed.connect(self._start_color_anim)
        self.stack.addWidget(self.settings_page)

        # 人脸管理页
        from .widgets import PCLFaceManager
        self.face_page = PCLFaceManager()
        self.stack.addWidget(self.face_page)

        # 记忆管理页（分仓记忆 + 共享记忆清理）
        self.memory_page = PCLMemoryManager()
        self.stack.addWidget(self.memory_page)

        # 桌宠管理页（多桌宠：设为活动/添加/删除/打开文件夹）
        self.pet_page = PCLPetManager()
        self.stack.addWidget(self.pet_page)

        # 提示词编辑器页
        self.prompt_page = PCLPromptEditor()
        self.stack.addWidget(self.prompt_page)

    def _try_load_live2d(self, path, pet_id=None):
        try:
            # 按角色应用显示调整（缩放/平移，与引擎一致）
            scale, ox, oy = 1.0, 0.0, 0.0
            if pet_id:
                try:
                    from pets.pet_registry import get_live2d_display
                    d = get_live2d_display(pet_id)
                    scale, ox, oy = d["scale"], d["offset_x"], d["offset_y"]
                except Exception:
                    pass
            widget = Live2DPreviewWidget(model_path=path, model_scale=scale, offset_x=ox, offset_y=oy)
            widget.setMinimumHeight(int(350 * S))
            widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self._install_preview(widget)

            def _check():
                if widget._failed:
                    widget.hide(); widget.deleteLater()
                    self._fallback_to_2d()
                    return
                if widget._render_ready:
                    return
                _check._count = getattr(_check, '_count', 0) + 1
                if _check._count < 50:
                    QTimer.singleShot(100, _check)
                else:
                    widget.hide(); widget.deleteLater()
                    self._fallback_to_2d()
            QTimer.singleShot(200, _check)
        except Exception:
            import traceback
            traceback.print_exc()
            self._fallback_to_2d()

    def _fallback_to_2d(self):
        print("[PCL] 回退到 2D 立绘")
        widget = PortraitPreviewWidget(self._config)
        widget.setMinimumHeight(int(250 * S))
        self._install_preview(widget)

    def _install_preview(self, widget):
        if self._preview_widget:
            self.preview_layout.removeWidget(self._preview_widget)
            self._preview_widget.hide(); self._preview_widget.deleteLater()
        self._preview_widget = widget
        self.preview_layout.insertWidget(0, widget, 1)

    def _on_model_selected(self, pet_id, name, model_path):
        """点角色卡片 → 设为活动角色 + 预览对应模型（阶段 B）"""
        from pets.pet_registry import set_active_pet_id
        if set_active_pet_id(pet_id):
            print(f"[PCL] 已设为活动桌宠: {name} ({pet_id})，启动 AIpet / QQ 将使用该角色")
        else:
            print(f"[PCL] ⚠ 设为活动失败: {pet_id}")
        self._selected_pet_id = pet_id
        self._preview_pet(pet_id, model_path)
        self._sync_qq_button_hint()

    def _preview_pet(self, pet_id, model_path):
        """PCL 预览统一显示 Live2D（含丛雨）；无模型/加载失败才回退 2D 立绘"""
        if model_path and os.path.exists(model_path):
            self._try_load_live2d(model_path, pet_id)
        else:
            self._fallback_to_2d()

    def _sync_qq_button_hint(self):
        """QQ 运行中切换了活动角色 → 提示需重启 QQ 才生效"""
        if self._qq_process is None:
            return
        from pets.pet_registry import get_active_pet_id
        if get_active_pet_id() != self._qq_pet_id:
            self.qq_btn.setToolTip("QQ 正在服务旧角色，点击关闭后重新启动即可切换")
            print("[PCL] QQ 运行中，活动角色已切换；重启 QQ 后生效")
        else:
            self.qq_btn.setToolTip("启动 QQ 聊天模块（自动启动 NapCat，首次需扫码登录）")

    def _on_launch_clicked(self):
        """启动/关闭 AI 桌宠（阶段 C 互斥：不允许同时跑 2 个 AI 桌宠）"""
        from pets.pet_registry import get_active_pet_id
        current_pet = get_active_pet_id()
        if self._pet_process is not None:
            if self._running_pet_id == current_pet:
                # 同一个角色 → 视为关闭
                self._kill_pet_process()
                self.control_panel.hide()
                self.launch_btn.setText("  启动 AIpet 桌宠")
                self.launch_btn.setStyleSheet(f"""
                    QPushButton {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                        stop:0 {THEME_COLORS['blue']['btn_start']},stop:1 {THEME_COLORS['blue']['btn_end']});
                        color: white; border: none; font-size: {int(14*S)}px; font-weight: bold;
                        font-family: 'Microsoft YaHei'; border-radius: {int(8*S)}px; }}
                """)
                print(f"[PCL] 已关闭桌宠: {current_pet}")
            else:
                # 切换角色 → 先关旧的再启动新的（互斥）
                print(f"[PCL] 关闭旧桌宠({self._running_pet_id})，启动新桌宠({current_pet})")
                self._kill_pet_process()
                self._launch_pet_process()
        else:
            self._launch_pet_process()

    def _launch_pet_process(self):
        """启动 run.py 子进程（按当前活动角色）"""
        base = _app_base_dir()
        py = _find_python(base)
        if not py:
            self._show_config_dialog("未找到 Python 解释器")
            return
        # 互斥保护：API 存活说明已有桌宠在运行（可能是手动启动的）→ 拒绝再启动
        if self._pet_api_alive():
            self._show_config_dialog("桌宠已在运行（可能是手动启动的），请先关闭再启动新的")
            return
        from pets.pet_registry import get_active_pet_id
        self._running_pet_id = get_active_pet_id()
        self._pet_process = subprocess.Popen(
            [py, os.path.join(base, "run.py")],
            cwd=base,
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        self.control_panel.show()
        self.launch_btn.setText("  ⏹ 关闭桌宠")
        self.launch_btn.setStyleSheet(f"""
            QPushButton {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 #e03030,stop:1 #f06060);
                color: white; border: none; font-size: {int(14*S)}px; font-weight: bold;
                border-radius: {int(8*S)}px; }}
        """)
        print(f"[PCL] 已启动桌宠: {self._running_pet_id}")

    def _kill_process(self, proc_ref):
        """强制终止一个子进程（含子进程树）"""
        if proc_ref is None:
            return
        try:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc_ref.pid)],
                           capture_output=True, timeout=10)
        except Exception:
            pass
        try:
            proc_ref.terminate()
            proc_ref.wait(timeout=3)
        except subprocess.TimeoutExpired:
            try:
                proc_ref.kill()
            except Exception:
                pass
        except Exception:
            try:
                proc_ref.kill()
            except Exception:
                pass

    def _kill_pet_process(self):
        """关闭桌宠进程"""
        if self._pet_process is None:
            return
        self._kill_process(self._pet_process)
        self._pet_process = None
        self._running_pet_id = None

    def _kill_qq_process(self):
        """关闭 QQ AIpet 进程"""
        if self._qq_process is None:
            return
        self._kill_process(self._qq_process)
        self._qq_process = None

    @staticmethod
    def _napcat_port_open(port=3001, host="127.0.0.1", timeout=1):
        """检查 NapCat WebSocket 端口是否可连接"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                return s.connect_ex((host, port)) == 0
        except Exception:
            return False

    @staticmethod
    def _pet_api_alive():
        """桌宠 API 是否可访问（仅在点击启动时检查一次，防止同时跑两个桌宠）"""
        try:
            req = urllib.request.Request("http://localhost:28565/control", method="GET")
            urllib.request.urlopen(req, timeout=2).read()
            return True
        except Exception:
            return False

    def _start_run_qq(self):
        """启动 run_qq.py 子进程并更新按钮状态"""
        base = _app_base_dir()
        py = _find_python(base)
        if not py:
            self._show_config_dialog("未找到 Python 解释器")
            return
        # 记录 QQ 服务的角色（切角色时用于提示）
        try:
            from pets.pet_registry import get_active_pet_id
            self._qq_pet_id = get_active_pet_id()
        except Exception:
            self._qq_pet_id = None
        self._qq_process = subprocess.Popen(
            [py, os.path.join(base, "run_qq.py")],
            cwd=base,
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        self.qq_btn.setText("  ⏹ 关闭 QQ AIpet")
        self.qq_btn.setStyleSheet(f"""
            QPushButton {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 #e03030,stop:1 #f06060);
                color: white; border: none; font-size: {int(14*S)}px; font-weight: bold;
                border-radius: {int(8*S)}px; }}
        """)

    def _ensure_napcat_async(self, timeout_sec=45):
        """
        异步确保 NapCat 已运行（不阻塞 UI）：
        - 若 3001 端口已可连接 → 直接启动 run_qq.py
        - 否则启动 start_napcat.bat（新控制台）
          → 用 QTimer 每秒探测端口，就绪后自动启动 run_qq.py
          → 超过 timeout_sec 秒 → 恢复按钮并弹窗提示
        """
        # 若等待计时器已在运行，忽略重复点击
        if getattr(self, "_napcat_wait_running", False):
            print("[PCL] 已在等待 NapCat 启动，请勿重复点击")
            return

        # 情况 1：NapCat 已在运行 → 直接启动
        if self._napcat_port_open():
            print("[PCL] NapCat 已在运行（端口 3001）")
            self._start_run_qq()
            return

        # 情况 2：启动 NapCat
        base = _app_base_dir()

        napcat_bat = os.path.join(base, "NapCat.Shell.Windows.OneKey", "start_napcat.bat")
        if not os.path.exists(napcat_bat):
            print(f"[PCL] ⚠ 未找到 NapCat 启动脚本: {napcat_bat}")
            self._show_config_dialog("NapCat 未安装")
            return

        print(f"[PCL] NapCat 未运行，正在自动启动: {napcat_bat}")
        try:
            subprocess.Popen(
                [napcat_bat],
                cwd=os.path.dirname(napcat_bat),
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        except Exception as e:
            print(f"[PCL] ⚠ 启动 NapCat 失败: {e}")
            self._show_config_dialog("NapCat 启动失败")
            return

        # 等待期间：禁用按钮 + 更新文字，防止重复点击
        self.qq_btn.setEnabled(False)
        self.qq_btn.setText("  ⏳ 等待 NapCat...（登录后自动继续）")

        # 异步轮询：QTimer 每秒检查一次端口（不阻塞 UI）
        self._napcat_wait_elapsed = 0
        self._napcat_wait_running = True
        self._napcat_wait_timeout = timeout_sec

        if not hasattr(self, "_napcat_wait_timer"):
            self._napcat_wait_timer = QTimer(self)
            self._napcat_wait_timer.timeout.connect(self._napcat_wait_tick)
        if not self._napcat_wait_timer.isActive():
            self._napcat_wait_timer.start(1000)  # 每 1 秒触发

    def _napcat_wait_tick(self):
        """QTimer 每秒触发：检查 NapCat 端口是否就绪"""
        self._napcat_wait_elapsed += 1

        # 已就绪 → 停止轮询，启动 run_qq.py
        if self._napcat_port_open():
            elapsed = self._napcat_wait_elapsed
            self._napcat_wait_running = False
            self._napcat_wait_timer.stop()
            self._napcat_wait_elapsed = 0
            print(f"[PCL] ✅ NapCat WebSocket 就绪（{elapsed} 秒）")
            self._start_run_qq()
            return

        # 超时 → 停止轮询，恢复按钮
        if self._napcat_wait_elapsed >= self._napcat_wait_timeout:
            self._napcat_wait_running = False
            self._napcat_wait_timer.stop()
            self._napcat_wait_elapsed = 0
            self.qq_btn.setEnabled(True)
            self.qq_btn.setText("  💬 启动 QQ AIpet")
            print(f"[PCL] ⚠ 等待 NapCat 超时（{self._napcat_wait_timeout} 秒），请检查 NapCat 控制台")
            self._show_config_dialog("NapCat 启动超时")
            return

        # 仍在等待：每 5 秒打印一次状态
        if self._napcat_wait_elapsed % 5 == 0:
            print(f"[PCL] 等待 NapCat 启动...（已等待 {self._napcat_wait_elapsed} 秒，请扫码登录 QQ）")

    def _on_qq_clicked(self):
        """启动/关闭 QQ AIpet（启动前自动确保 NapCat 运行，异步不阻塞 UI）"""
        # 若正在等待 NapCat 就绪，禁止再次点击
        if getattr(self, "_napcat_wait_running", False):
            print("[PCL] 正在等待 NapCat 启动，请稍候...")
            return

        # 关闭 QQ AIpet
        if self._qq_process is not None:
            self._kill_qq_process()
            self._qq_pet_id = None
            self.qq_btn.setText("  💬 启动 QQ AIpet")
            self.qq_btn.setEnabled(True)
            self.qq_btn.setToolTip("启动 QQ 聊天模块（自动启动 NapCat，首次需扫码登录）")
            self.qq_btn.setStyleSheet(f"""
                QPushButton {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {THEME_COLORS['blue']['btn_start']},stop:1 {THEME_COLORS['blue']['btn_end']});
                    color: white; border: none; font-size: {int(14*S)}px; font-weight: bold;
                    font-family: 'Microsoft YaHei'; border-radius: {int(8*S)}px; }}
            """)
            return

        # 检查子进程解释器可用（QQ 本体由 run_qq.py 子进程运行，
        # websocket-client 由该进程的 Python 环境提供；壳自身无需打包）
        if not _find_python(_app_base_dir()):
            self._show_config_dialog("未找到 Python 解释器")
            return

        # 异步确保 NapCat 运行（不阻塞 UI）
        self._ensure_napcat_async()

    def closeEvent(self, event):
        """关闭窗口时一并终止桌宠与 QQ 进程"""
        self._kill_pet_process()
        self._kill_qq_process()
        super().closeEvent(event)

    def nativeEvent(self, event_type, message):
        """修复无边框窗口点击任务栏图标不最小化（WM_SYSCOMMAND/SC_MINIMIZE）"""
        if sys.platform == "win32" and event_type == "windows_generic_MSG":
            try:
                import ctypes
                from ctypes import wintypes
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == 0x0112 and (msg.wParam & 0xFFF0) == 0xF020:  # SC_MINIMIZE
                    self.showMinimized()
                    return True, 0
            except Exception:
                pass
        return super().nativeEvent(event_type, message)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.y() < int(48 * S):
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
        else:
            self._drag_pos = None  # 点击非标题栏区域，禁止拖动

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            self.move(event.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))
        r = QRect(int(8 * S), int(8 * S), self.width() - int(16 * S), self.height() - int(16 * S))
        path = QPainterPath()
        path.addRoundedRect(QRectF(r), 12.0, 12.0)
        painter.setClipPath(path)
        painter.fillRect(r, Qt.white)

    def _switch_page(self, index):
        # 如果正在动画中，直接切页面，跳过动画
        if self._animating:
            self.stack.setCurrentIndex(index)
            return
        self._fade_page_out(lambda: self._do_switch(index))

    def _do_switch(self, index):
        self.stack.setCurrentIndex(index); self._fade_page_in()

    def _fade_page_out(self, callback):
        self._animating = True
        self._fade_out_effect = QGraphicsOpacityEffect(self.stack)
        self._fade_out_effect.setOpacity(1.0)
        self.stack.setGraphicsEffect(self._fade_out_effect)
        self._fade_out_anim = QPropertyAnimation(self._fade_out_effect, b"opacity")
        self._fade_out_anim.setDuration(150)
        self._fade_out_anim.setStartValue(1.0)
        self._fade_out_anim.setEndValue(0.0)
        self._fade_out_anim.finished.connect(lambda: (
            self.stack.setGraphicsEffect(None),
            callback(),
            setattr(self, '_animating', False)
        ))
        self._fade_out_anim.start(QAbstractAnimation.DeleteWhenStopped)

    def _fade_page_in(self):
        self._animating = True
        self._fade_in_effect = QGraphicsOpacityEffect(self.stack)
        self._fade_in_effect.setOpacity(0.0)
        self.stack.setGraphicsEffect(self._fade_in_effect)
        self._fade_in_anim = QPropertyAnimation(self._fade_in_effect, b"opacity")
        self._fade_in_anim.setDuration(150)
        self._fade_in_anim.setStartValue(0.0)
        self._fade_in_anim.setEndValue(1.0)
        self._fade_in_anim.finished.connect(lambda: (
            self.stack.setGraphicsEffect(None),
            setattr(self, '_animating', False)
        ))
        self._fade_in_anim.start(QAbstractAnimation.DeleteWhenStopped)

    def _start_fade_close(self):
        self._start_fade(25, self.close)

    def _start_fade(self, steps, callback):
        self._fade_effect = QGraphicsOpacityEffect(self.pan_back)
        self._fade_effect.setOpacity(1.0)
        self.pan_back.setGraphicsEffect(self._fade_effect)
        self._fade_step = 0; self._fade_max = steps; self._fade_cb = callback
        self._fade_timer.timeout.connect(self._fade_tick)
        self._fade_timer.start(16)

    def _fade_tick(self):
        self._fade_step += 1
        self._fade_effect.setOpacity(max(0.0, 1.0 - self._fade_step / self._fade_max))
        if self._fade_step >= self._fade_max:
            self._fade_timer.stop(); self.pan_back.setGraphicsEffect(None); self._fade_cb()

    def _start_color_anim(self, key):
        self._color_old = (self._color_new[0], THEME_COLORS[self._color_new[0]])
        self._color_new = (key, THEME_COLORS[key])
        self._color_step = 0
        if not self._color_timer.isActive(): self._color_timer.start(16)
        self.sidebar.set_theme(key)

    def _color_tick(self):
        self._color_step += 1
        p = min(1.0, self._color_step / self._color_max)
        old, new = self._color_old[1], self._color_new[1]
        self.titlebar.set_interpolated_accent(
            QColor(old["title_start"]), QColor(old["title_end"]),
            QColor(new["title_start"]), QColor(new["title_end"]), p)
        if self._color_step >= self._color_max: self._color_timer.stop()

    def _show_config_dialog(self, feature_name: str):
        """PCL 风格弹窗 — 功能未启用提示"""
        dlg = QWidget(self, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        dlg.setFixedSize(int(400 * S), int(180 * S))
        dlg.setStyleSheet(f"background: white; border: 1px solid {Color5.name()}; border-radius: 12px;")
        layout = QVBoxLayout(dlg); layout.setContentsMargins(int(24*S), int(20*S), int(24*S), int(16*S)); layout.setSpacing(int(10*S))
        title = QLabel(f"  {feature_name} 未启用")
        title.setStyleSheet(f"color: {Color1.name()}; font-size: {int(15*S)}px; font-weight: bold; font-family: 'Microsoft YaHei'; border: none;")
        body = QLabel("该功能在 config.json 中被设为 false，\n请修改配置后重启桌宠。")
        body.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(12*S)}px; font-family: 'Microsoft YaHei'; border: none;")
        btn = QPushButton("  确定  ")
        btn.setStyleSheet(f"QPushButton {{ background: {Color3.name()}; color: white; border: none; padding: {int(8*S)}px {int(32*S)}px; font-size: {int(13*S)}px; border-radius: {int(6*S)}px; font-family: 'Microsoft YaHei'; }} QPushButton:hover {{ background: {Color4.name()}; }}")
        btn.clicked.connect(dlg.close)
        layout.addWidget(title); layout.addWidget(body); layout.addStretch()
        hh = QHBoxLayout(); hh.addStretch(); hh.addWidget(btn); hh.addStretch(); layout.addLayout(hh)
        center = self.mapToGlobal(self.rect().center())
        dlg.move(center.x() - dlg.width()//2, center.y() - dlg.height()//2)
        dlg.show()

    def _on_size_changed(self, w, h):
        self._resize_to(w, h)

    def _resize_to(self, w, h):
        anim = QPropertyAnimation(self, b"geometry")
        anim.setDuration(200); anim.setStartValue(self.geometry())
        cx = self.x() + (self.width() - w) // 2
        cy = self.y() + (self.height() - h) // 2
        anim.setEndValue(QRect(cx, cy, w, h))
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start(QAbstractAnimation.DeleteWhenStopped)

    def _discover_models(self):
        """遍历注册中心所有桌宠，为每个角色生成一张卡片（阶段 B）。
        启动时高亮当前活动角色并排队预览，点卡片由 _on_model_selected 处理。"""
        from pets.pet_registry import (
            get_all_pets_summary, get_live2d_model_json, get_pet_dir, get_active_pet_id,
        )
        try:
            pets = get_all_pets_summary()
        except Exception as e:
            print(f"[PCL] 加载桌宠列表失败: {e}")
            pets = []

        active_id = get_active_pet_id()
        self._selected_pet_id = active_id
        active_model_path = ""

        for p in pets:
            pet_id = p["id"]
            caps = p.get("capabilities", {})
            model_json = get_live2d_model_json(pet_id) if caps.get("has_live2d") else ""
            avatar = ""
            if p.get("avatar"):
                candidate = os.path.join(get_pet_dir(pet_id), p["avatar"])
                if os.path.exists(candidate):
                    avatar = candidate
            self._pets_by_id[pet_id] = {
                "summary": p,
                "model_json": model_json,
                "avatar": avatar,
            }
            self.sidebar.add_model(
                pet_id,
                p.get("display_name") or p.get("name", pet_id),
                model_json,
                avatar,
            )
            if pet_id == active_id:
                active_model_path = model_json

        # 高亮活动角色卡片（不触发切换信号）
        self.sidebar.select_pet(active_id)
        # 排队等待 showEvent 后加载预览（OpenGL 需窗口显示后初始化）
        self._model_queue.append((active_id, active_model_path))
        print(f"[PCL] 发现 {len(pets)} 个桌宠，当前活动: {active_id}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.pan_back.setGeometry(int(8 * S), int(8 * S), self.width() - int(16 * S), self.height() - int(16 * S))