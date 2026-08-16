"""PCL 风格 UI 控件"""

import os
import json
import subprocess
import sys
import urllib.request

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QLinearGradient, QPainterPath, QFont, QIcon, QPixmap
from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QSpinBox, QScrollArea,
    QLineEdit, QSlider, QDoubleSpinBox, QComboBox, QTextEdit
)

from .colors import *

S = 1.0

# ==================== 标题栏 ====================

class PCLTitleBar(QWidget):
    nav_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(int(48 * S))
        self._nav_index = 0
        self._accent_start = QColor("#1370f3")
        self._accent_end = QColor("#4890f5")
        self._interp_start = None
        self._interp_end = None
        self._interp_progress = 1.0

        layout = QHBoxLayout(self)
        layout.setContentsMargins(int(12 * S), 0, int(8 * S), 0)
        layout.setSpacing(0)

        self.logo = QLabel()
        self.logo.setPixmap(QPixmap(block_icon("Grass")).scaled(int(24 * S), int(24 * S), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout.addWidget(self.logo)
        layout.addSpacing(int(12 * S))

        nav_widget = QWidget()
        nav_layout = QHBoxLayout(nav_widget)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(int(4 * S))

        self.btn_model = self._make_nav_btn("模型", block_icon("GoldBlock"), 0)
        self.btn_settings = self._make_nav_btn("设置", block_icon("RedstoneBlock"), 1)
        self.btn_faces = self._make_nav_btn("人脸", block_icon("RedstoneLampOn"), 2)
        self.btn_memory = self._make_nav_btn("记忆", block_icon("DiamondBlock"), 3)
        self.btn_pets = self._make_nav_btn("桌宠", block_icon("Grass"), 4)
        self.btn_prompt = self._make_nav_btn("提示词", block_icon("CommandBlock"), 5)
        nav_layout.addWidget(self.btn_model)
        nav_layout.addWidget(self.btn_settings)
        nav_layout.addWidget(self.btn_faces)
        nav_layout.addWidget(self.btn_memory)
        nav_layout.addWidget(self.btn_pets)
        nav_layout.addWidget(self.btn_prompt)
        nav_layout.addStretch()
        layout.addWidget(nav_widget, 1)

        self.btn_min = self._make_icon_btn("−", self._on_min)
        self.btn_close = self._make_icon_btn("✕", self._on_close)
        layout.addWidget(self.btn_min)
        layout.addSpacing(int(8 * S))
        layout.addWidget(self.btn_close)

        self._update_nav_style()

    def _make_nav_btn(self, text, icon_path, index):
        btn = QPushButton(f"  {text}")
        btn.setCheckable(True)
        btn.setIcon(QIcon(icon_path))
        btn.setIconSize(QPixmap(icon_path).scaled(int(18 * S), int(18 * S)).size())
        btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: white; border: none;
                padding: {int(6*S)}px {int(14*S)}px; font-size: {int(13*S)}px;
                font-family: 'Microsoft YaHei'; border-radius: {int(4*S)}px; }}
            QPushButton:hover {{ background: rgba(255,255,255,0.15); }}
            QPushButton:checked {{ background: rgba(255,255,255,0.25); }}
        """)
        btn.clicked.connect(lambda: self._on_nav(index))
        return btn

    def _make_icon_btn(self, text, callback):
        btn = QPushButton(text)
        btn.setFixedSize(int(32 * S), int(32 * S))
        btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: white; border: none;
                font-size: {int(14*S)}px; font-family: 'Microsoft YaHei'; font-weight: bold; }}
            QPushButton:hover {{ background: rgba(255,255,255,0.2); border-radius: 4px; }}
        """)
        btn.clicked.connect(callback)
        return btn

    def _on_nav(self, index):
        self._nav_index = index
        self._update_nav_style()
        self.nav_changed.emit(index)

    def _update_nav_style(self):
        self.btn_model.setChecked(self._nav_index == 0)
        self.btn_settings.setChecked(self._nav_index == 1)
        self.btn_faces.setChecked(self._nav_index == 2)
        self.btn_memory.setChecked(self._nav_index == 3)
        self.btn_pets.setChecked(self._nav_index == 4)
        self.btn_prompt.setChecked(self._nav_index == 5)

    def _on_min(self): self.window().showMinimized()
    def _on_close(self): self.window()._start_fade_close()

    def set_interpolated_accent(self, old_start, old_end, new_start, new_end, progress):
        self._interp_start = old_start
        self._interp_end = old_end
        self._accent_start = new_start
        self._accent_end = new_end
        self._interp_progress = progress
        self.update()

    def _lerp_color(self, c1, c2, t):
        return QColor(
            int(c1.red() + (c2.red() - c1.red()) * t),
            int(c1.green() + (c2.green() - c1.green()) * t),
            int(c1.blue() + (c2.blue() - c1.blue()) * t),
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        if self._interp_start and self._interp_progress < 1.0:
            c1 = self._lerp_color(self._interp_start, self._accent_start, self._interp_progress)
            c2 = self._lerp_color(self._interp_end, self._accent_end, self._interp_progress)
        else:
            c1, c2 = self._accent_start, self._accent_end
        gradient = QLinearGradient(0, 0, rect.width(), 0)
        gradient.setColorAt(0.0, c1); gradient.setColorAt(0.5, c2); gradient.setColorAt(1.0, c1)
        painter.fillRect(rect, gradient)


# ==================== 侧栏 ====================

class PCLSidebar(QWidget):
    model_selected = pyqtSignal(str, str, str)  # (pet_id, name, model_path)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(int(210 * S))
        self._models = []
        self._current = -1
        layout = QVBoxLayout(self)
        layout.setContentsMargins(int(12 * S), int(12 * S), int(12 * S), int(12 * S))
        layout.setSpacing(int(4 * S))

        header = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(QPixmap(block_icon("Grass")).scaled(int(20 * S), int(20 * S)))
        header.addWidget(icon)
        title = QLabel(" 模型列表")
        title.setFont(QFont("Microsoft YaHei", int(12 * S), QFont.Bold))
        title.setStyleSheet(f"color: {Color1.name()};")
        header.addWidget(title); header.addStretch()
        layout.addLayout(header); layout.addSpacing(int(8 * S))

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.btn_container = QWidget()
        self.btn_layout = QVBoxLayout(self.btn_container)
        self.btn_layout.setContentsMargins(0, 0, 0, 0)
        self.btn_layout.setSpacing(int(2 * S))
        self.btn_layout.addStretch()
        self.scroll.setWidget(self.btn_container)
        layout.addWidget(self.scroll, 1)

        line = QWidget(); line.setFixedHeight(1)
        line.setStyleSheet(f"background: {Gray5.name()};")
        layout.addWidget(line); layout.addSpacing(int(8 * S))

    def set_theme(self, theme: str): pass

    def add_model(self, pet_id: str, name: str, model_path: str = "", avatar_path: str = ""):
        """添加一张角色卡片：pet_id 用于切换活动角色，avatar_path 为角色包内头像绝对路径。"""
        self._models.append((pet_id, name, model_path))
        idx = len(self._models) - 1
        container = QWidget()
        container.setCursor(Qt.PointingHandCursor)
        container.setStyleSheet(f"""
            QWidget {{ background: transparent; border-left: 3px solid transparent;
                border-radius: 0 {int(6*S)}px {int(6*S)}px 0; }}
            QWidget:hover {{ background: {Color5.name()}; }}
            QWidget[selected="true"] {{ background: {Color6.name()}; border-left: 3px solid {Color3.name()}; }}
        """)
        setattr(container, 'model_idx', idx)
        row = QHBoxLayout(container)
        row.setContentsMargins(int(8*S), int(6*S), int(10*S), int(6*S))
        row.setSpacing(int(8*S))
        avatar = QLabel()
        avatar.setFixedSize(int(32*S), int(32*S))
        avatar.setScaledContents(True)
        avatar.setStyleSheet("border: none; background: transparent;")
        # 优先角色包头像，缺失回退默认图标（旧路径兼容）
        if avatar_path and os.path.exists(avatar_path):
            avatar.setPixmap(QPixmap(avatar_path).scaled(int(32*S), int(32*S), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "icons", "avatar.png")
            if os.path.exists(icon_path):
                avatar.setPixmap(QPixmap(icon_path).scaled(int(32*S), int(32*S), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        row.addWidget(avatar)
        label = QLabel(name)
        label.setFont(QFont("Microsoft YaHei", int(14*S), QFont.Bold))
        label.setStyleSheet(f"color: {Color1.name()}; background: transparent; border: none;")
        row.addWidget(label, 1)
        container.mousePressEvent = lambda ev, i=idx: self._select(i)
        avatar.mousePressEvent = lambda ev, i=idx: self._select(i)
        label.mousePressEvent = lambda ev, i=idx: self._select(i)
        self.btn_layout.insertWidget(self.btn_layout.count() - 1, container)

    def _select(self, index):
        self.set_selected(index)
        pet_id, name, path = self._models[index]
        self.model_selected.emit(pet_id, name, path)

    def set_selected(self, index):
        """高亮指定卡片（不触发信号）"""
        self._current = index
        for i in range(self.btn_layout.count()):
            w = self.btn_layout.itemAt(i).widget()
            if w and hasattr(w, 'model_idx'):
                w.setProperty("selected", "true" if w.model_idx == index else "false")
                w.style().unpolish(w); w.style().polish(w)

    def select_pet(self, pet_id: str) -> bool:
        """按 pet_id 高亮卡片（启动时用，不触发切换信号），返回是否找到。"""
        for i, m in enumerate(self._models):
            if m[0] == pet_id:
                self.set_selected(i)
                return True
        return False


# ==================== 设置面板 (完整 Config 表单) ====================

class PCLSettingsPanel(QScrollArea):
    size_changed = pyqtSignal(int, int)
    color_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.NoFrame)
        self.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self._widgets = {}
        self._config_path = None

        container = QWidget()
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(int(30 * S), int(30 * S), int(30 * S), int(30 * S))
        self._layout.setSpacing(int(14 * S))
        self.setWidget(container)

        title = QLabel("  ⚙ 桌宠配置")
        title.setFont(QFont("Microsoft YaHei", int(16 * S), QFont.Bold))
        title.setStyleSheet(f"color: {Color1.name()};")
        self._layout.addWidget(title)

        self._add_text_input("user_name", "使用者名称", "")
        self._add_text_input("deepseek_api_key", "DeepSeek API Key", "", placeholder="sk-...")
        self._add_text_input("qwen_api_key", "Qwen API Key", "", placeholder="sk-...")

        self._add_slider("model_type", "对话模型", ["local", "deepseek", "qwen"], "qwen")
        self._add_slider("tts_type", "TTS 语音合成", ["local", "cloud"], "local")
        self._add_slider("portrait", "立绘类型", ["a", "b"], "b")
        self._add_slider("screen_type", "屏幕识别", ["false", "true"], "false")
        self._add_slider("voice_trigger", "语音识别", ["false", "true"], "false")
        self._add_slider("live2d_enabled", "Live2D 模式", ["false", "true"], "true")
        self._add_slider("camera_enabled", "常开摄像头识别", ["false", "true"], "true")
        self._add_slider("face_recognition_enabled", "人脸识别", ["false", "true"], "true")
        self._add_slider("force_gpu_check", "强制 GPU 检查", ["false", "true"], "false")
        self._add_slider("longtext_enabled", "长文本输出模式", ["false", "true"], "true")
        self._add_slider("longtext_model", "长文本对话模型", ["qwen", "deepseek"], "qwen")

        # ===== QQ 配置分组 =====
        qq_title = QLabel("  💬 QQ 聊天配置")
        qq_title.setFont(QFont("Microsoft YaHei", int(14 * S), QFont.Bold))
        qq_title.setStyleSheet(f"color: {Color1.name()}; margin-top: {int(16*S)}px;")
        self._layout.addWidget(qq_title)

        self._add_text_input("qq_owner_id", "主人 QQ 号（共享记忆）", "", placeholder="如：123456789")
        self._add_slider("qq_enabled", "QQ 功能总开关", ["false", "true"], "false")
        self._add_slider("qq_send_sticker", "QQ 表情包", ["false", "true"], "true")
        self._add_slider("qq_send_voice", "QQ 语音消息 (F5-TTS)", ["false", "true"], "false")
        self._add_slider("qq_vision_enabled", "QQ 图片识别", ["false", "true"], "true")
        self._add_slider("qq_allow_groups", "QQ 群聊 (需@)", ["false", "true"], "true")

        # ===== 微信 ClawBot 配置分组 =====
        wx_title = QLabel("  💬 微信 ClawBot 配置")
        wx_title.setFont(QFont("Microsoft YaHei", int(14 * S), QFont.Bold))
        wx_title.setStyleSheet(f"color: {Color1.name()}; margin-top: {int(16*S)}px;")
        self._layout.addWidget(wx_title)

        self._add_slider("wechat_enabled", "微信 ClawBot 总开关", ["false", "true"], "false")
        self._add_slider("wechat_send_voice", "微信语音回复（尚不支持此功能）", ["false", "true"], "false")
        self._add_text_input("wechat_owner_id", "微信白名单（xxx@im.wechat，空=回复所有人）", "",
                             placeholder="如：wxid_xxx@im.wechat")

        self._add_spin("screen_interval", "屏幕截图间隔 (秒)", 60, 3600, 300)
        self._add_spin("camera_interval", "摄像头常开间隔 (秒)", 60, 3600, 300)
        self._add_spin("screen_index", "桌宠显示屏幕编号", 0, 3, 0)
        self._add_spin("camera_id", "摄像头设备编号", 0, 5, 0)
        self._add_spin("idle_thinking_minutes", "空闲发呆阈值 (分钟)", 1, 60, 3)
        self._add_spin("idle_away_minutes", "空闲离屏阈值 (分钟)", 2, 120, 10)
        self._add_double_spin("DEFAULT_PORTRAIT_SCREEN_RATIO", "立绘高度比例", 0.1, 1.0, 0.8, 0.05)

        # 主题色
        color_label = QLabel("🎨 主题色")
        color_label.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(12*S)}px;")
        self._layout.addWidget(color_label)
        color_row = QHBoxLayout(); color_row.setSpacing(int(10 * S))
        for key in ["blue", "red", "green", "gold", "dark"]:
            btn = QPushButton()
            btn.setFixedSize(int(32 * S), int(32 * S))
            btn.setStyleSheet(f"""
                QPushButton {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 {THEME_COLORS[key]['title_start']},stop:1 {THEME_COLORS[key]['title_end']});
                    border: 2px solid {Gray5.name()}; border-radius: {int(16*S)}px; }}
                QPushButton:hover {{ border: 3px solid {Color3.name()}; }}
            """)
            btn.clicked.connect(lambda checked, k=key: self.color_changed.emit(k))
            color_row.addWidget(btn)
        color_row.addStretch()
        self._layout.addLayout(color_row)

        self._layout.addSpacing(int(10 * S))

        # 保存按钮
        btn_save = QPushButton("  💾 保存  ")
        btn_save.setStyleSheet(f"""
            QPushButton {{ background: {Color3.name()}; color: white; border: none;
                padding: {int(10*S)}px {int(24*S)}px; font-size: {int(13*S)}px;
                border-radius: {int(6*S)}px; font-family: 'Microsoft YaHei'; }}
            QPushButton:hover {{ background: {Color4.name()}; }}
        """)
        btn_save.clicked.connect(self._save_config)
        self._layout.addWidget(btn_save, 0, Qt.AlignLeft)

        # Live2D 显示调参面板（PCL → 桌宠 API 实时应用/保存）
        self._layout.addWidget(PCLLive2DTunePanel())

        self._layout.addStretch()

        # 加载当前配置
        self._load_current_config()

    # ---- helpers ----
    def _config_path_resolve(self):
        if self._config_path:
            return self._config_path
        # 统一用程序根目录解析（exe 模式 → exe 旁；源码 → 项目根），
        # 避免 PCL 壳用 __file__ 推导落到 _internal/ 导致读写错位
        from tool.paths import data_path
        p = data_path("config.json")
        if os.path.exists(p):
            self._config_path = p
            return p
        return p

    def _add_text_input(self, key, label, default="", placeholder=""):
        lbl = QLabel(f"  {label}")
        lbl.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(12*S)}px;")
        self._layout.addWidget(lbl)
        inp = QLineEdit()
        inp.setText(str(default))
        inp.setPlaceholderText(placeholder)
        inp.setStyleSheet(f"""
            QLineEdit {{ border: 1px solid {Gray5.name()}; padding: {int(6*S)}px;
                font-size: {int(12*S)}px; border-radius: {int(4*S)}px;
                background: white; font-family: 'Microsoft YaHei'; }}
            QLineEdit:focus {{ border: 1px solid {Color3.name()}; }}
        """)
        self._layout.addWidget(inp)
        self._widgets[key] = inp

    def _block_wheel(self, obj):
        obj.setFocusPolicy(Qt.StrongFocus)
        obj.wheelEvent = lambda e: e.ignore()

    def _add_slider(self, key, label, options, default):
        row = QHBoxLayout()
        lbl = QLabel(f"{label}：{default}")
        lbl.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(14*S)}px; min-width: 120px;")
        row.addWidget(lbl)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, len(options) - 1)
        slider.setValue(options.index(default) if default in options else 0)
        slider.setFixedWidth(int(140 * S))
        slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{ height: 4px; background: {Gray5.name()}; border-radius: 2px; }}
            QSlider::handle:horizontal {{ width: 12px; height: 12px; margin: -4px 0;
                background: {Color3.name()}; border-radius: 6px; }}
        """)
        self._block_wheel(slider)
        slider.valueChanged.connect(lambda v: lbl.setText(f"{label}：{options[v]}"))
        row.addWidget(slider)
        row.addStretch()
        self._layout.addLayout(row)
        self._widgets[key] = (slider, options, lbl)

    def _add_spin(self, key, label, min_val, max_val, default):
        row = QHBoxLayout()
        lbl = QLabel(f"{label}")
        lbl.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(14*S)}px; min-width: 160px;")
        row.addWidget(lbl)
        spin = QSpinBox()
        spin.setRange(min_val, max_val); spin.setValue(default)
        spin.setFixedWidth(int(90 * S))
        spin.setStyleSheet(f"QSpinBox {{ border:1px solid {Gray5.name()}; padding:{int(4*S)}px; font-size:{int(13*S)}px; border-radius:{int(3*S)}px; }}")
        self._block_wheel(spin)
        row.addWidget(spin); row.addStretch()
        self._layout.addLayout(row)
        self._widgets[key] = spin

    def _add_double_spin(self, key, label, min_val, max_val, default, step):
        row = QHBoxLayout()
        lbl = QLabel(f"{label}")
        lbl.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(14*S)}px; min-width: 160px;")
        row.addWidget(lbl)
        spin = QDoubleSpinBox()
        spin.setRange(min_val, max_val); spin.setValue(default); spin.setSingleStep(step)
        spin.setFixedWidth(int(90 * S))
        spin.setStyleSheet(f"QDoubleSpinBox {{ border:1px solid {Gray5.name()}; padding:{int(4*S)}px; font-size:{int(13*S)}px; border-radius:{int(3*S)}px; }}")
        self._block_wheel(spin)
        row.addWidget(spin); row.addStretch()
        self._layout.addLayout(row)
        self._widgets[key] = spin

    def _load_current_config(self):
        try:
            path = self._config_path_resolve()
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            self._set_if("user_name", cfg.get("user_name", ""))
            self._set_if("deepseek_api_key", cfg.get("APIKEY", {}).get("deepseek", ""))
            self._set_if("qwen_api_key", cfg.get("APIKEY", {}).get("qwen", ""))
            self._set_slider("model_type", cfg.get("model_type", "qwen"))
            self._set_slider("tts_type", cfg.get("tts_type", "local"))
            self._set_slider("portrait", cfg.get("portrait", "b"))
            self._set_slider("screen_type", cfg.get("screen_type", "false"))
            self._set_slider("voice_trigger", cfg.get("voice_trigger", "false"))
            self._set_slider("live2d_enabled", cfg.get("live2d_enabled", "true"))
            self._set_slider("camera_enabled", cfg.get("camera_enabled", "true"))
            self._set_slider("face_recognition_enabled", cfg.get("face_recognition_enabled", "true"))
            self._set_slider("force_gpu_check", cfg.get("force_gpu_check", "false"))
            self._set_slider("longtext_enabled", cfg.get("longtext_enabled", "true"))
            self._set_slider("longtext_model", cfg.get("longtext_model", "qwen"))
            self._set_if("qq_owner_id", cfg.get("qq_owner_id", ""))
            self._set_slider("qq_enabled", cfg.get("qq_enabled", "false"))
            self._set_slider("qq_send_sticker", cfg.get("qq_send_sticker", "true"))
            self._set_slider("qq_send_voice", cfg.get("qq_send_voice", "false"))
            self._set_slider("qq_vision_enabled", cfg.get("qq_vision_enabled", "true"))
            self._set_slider("qq_allow_groups", cfg.get("qq_allow_groups", "true"))
            self._set_slider("wechat_enabled", cfg.get("wechat_enabled", "false"))
            self._set_slider("wechat_send_voice", cfg.get("wechat_send_voice", "false"))
            self._set_if("wechat_owner_id", cfg.get("wechat_owner_id", ""))
            for k in ["screen_interval", "camera_interval", "screen_index", "camera_id", "idle_thinking_minutes", "idle_away_minutes"]:
                self._set_if(k, cfg.get(k, 0))
            self._set_if("DEFAULT_PORTRAIT_SCREEN_RATIO", cfg.get("DEFAULT_PORTRAIT_SCREEN_RATIO", 0.8))
        except Exception:
            pass

    def _set_if(self, key, val):
        w = self._widgets.get(key)
        if isinstance(w, QLineEdit): w.setText(str(val))
        elif isinstance(w, (QSpinBox, QDoubleSpinBox)): w.setValue(val)

    def _set_slider(self, key, val):
        entry = self._widgets.get(key)
        if entry:
            slider, options, lbl = entry
            idx = options.index(val) if val in options else 0
            slider.setValue(idx)
            lbl.setText(lbl.text().split("：")[0] + f"：{options[idx]}")

    def _save_config(self):
        try:
            path = self._config_path_resolve()
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)

            cfg["user_name"] = self._get_text("user_name")
            cfg.setdefault("APIKEY", {})
            cfg["APIKEY"]["deepseek"] = self._get_text("deepseek_api_key")
            cfg["APIKEY"]["qwen"] = self._get_text("qwen_api_key")

            cfg["model_type"] = self._get_slider("model_type")
            cfg["tts_type"] = self._get_slider("tts_type")
            cfg["portrait"] = self._get_slider("portrait")
            cfg["screen_type"] = self._get_slider("screen_type")
            cfg["voice_trigger"] = self._get_slider("voice_trigger")
            cfg["live2d_enabled"] = self._get_slider("live2d_enabled")
            cfg["camera_enabled"] = self._get_slider("camera_enabled")
            cfg["face_recognition_enabled"] = self._get_slider("face_recognition_enabled")
            cfg["force_gpu_check"] = self._get_slider("force_gpu_check")
            cfg["longtext_enabled"] = self._get_slider("longtext_enabled")
            cfg["longtext_model"] = self._get_slider("longtext_model")
            cfg["qq_owner_id"] = self._get_text("qq_owner_id")
            cfg["qq_enabled"] = self._get_slider("qq_enabled")
            cfg["qq_send_sticker"] = self._get_slider("qq_send_sticker")
            cfg["qq_send_voice"] = self._get_slider("qq_send_voice")
            cfg["qq_vision_enabled"] = self._get_slider("qq_vision_enabled")
            cfg["qq_allow_groups"] = self._get_slider("qq_allow_groups")
            cfg["wechat_enabled"] = self._get_slider("wechat_enabled")
            cfg["wechat_send_voice"] = self._get_slider("wechat_send_voice")
            cfg["wechat_owner_id"] = self._get_text("wechat_owner_id")

            for k in ["screen_interval", "camera_interval", "screen_index", "camera_id", "idle_thinking_minutes", "idle_away_minutes"]:
                w = self._widgets.get(k)
                if isinstance(w, QSpinBox): cfg[k] = w.value()
            w = self._widgets.get("DEFAULT_PORTRAIT_SCREEN_RATIO")
            if isinstance(w, QDoubleSpinBox): cfg["DEFAULT_PORTRAIT_SCREEN_RATIO"] = w.value()

            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)

            # 重启桌宠
            self._restart_pet()
        except Exception as e:
            print(f"[PCL] 保存配置失败: {e}")

    def _get_text(self, key):
        w = self._widgets.get(key)
        return w.text().strip() if isinstance(w, QLineEdit) else ""

    def _get_slider(self, key):
        entry = self._widgets.get(key)
        if entry:
            slider, options, _ = entry
            return options[slider.value()]
        return "false"

    def _restart_pet(self):
        """保存配置后，关闭当前运行中的桌宠进程（不重启）"""
        try:
            # 通过 API 通知桌宠退出
            import urllib.request
            req = urllib.request.Request("http://localhost:28565/control/shutdown", method="POST", data=b"")
            urllib.request.urlopen(req, timeout=3)
            print("[PCL] 已通知桌宠关闭")
        except Exception:
            pass
        # 同时通过 PCLMainWindow 的进程引用直接终止
        try:
            main_win = self.window()
            # 清理桌宠进程
            if hasattr(main_win, '_pet_process') and main_win._pet_process is not None:
                pid = main_win._pet_process.pid
                try:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                                   capture_output=True, timeout=10)
                    print(f"[PCL] 已终止桌宠进程 PID={pid}")
                except Exception:
                    try:
                        main_win._pet_process.terminate()
                        main_win._pet_process.wait(timeout=5)
                    except Exception:
                        try:
                            main_win._pet_process.kill()
                        except Exception:
                            pass
                main_win._pet_process = None
                # 更新按钮状态
                if hasattr(main_win, 'control_panel'):
                    main_win.control_panel.hide()
                if hasattr(main_win, 'launch_btn'):
                    main_win.launch_btn.setText("  启动 AIpet 桌宠")
            # 清理 QQ 进程（若在运行）
            if hasattr(main_win, '_qq_process') and main_win._qq_process is not None:
                pid2 = main_win._qq_process.pid
                try:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid2)],
                                   capture_output=True, timeout=10)
                    print(f"[PCL] 已终止 QQ AIpet 进程 PID={pid2}")
                except Exception:
                    try:
                        main_win._qq_process.terminate()
                        main_win._qq_process.wait(timeout=5)
                    except Exception:
                        try:
                            main_win._qq_process.kill()
                        except Exception:
                            pass
                main_win._qq_process = None
                if hasattr(main_win, 'qq_btn'):
                    main_win.qq_btn.setText("  💬 启动 QQ AIpet")
        except Exception as e:
            print(f"[PCL] 关闭进程异常: {e}")


# ==================== 人脸管理面板 ====================

class PCLFaceManager(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.NoFrame)
        self.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        container = QWidget()
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(int(30 * S), int(30 * S), int(30 * S), int(30 * S))
        self._layout.setSpacing(int(14 * S))
        self.setWidget(container)

        title = QLabel("  👤 人脸管理")
        title.setFont(QFont("Microsoft YaHei", int(16 * S), QFont.Bold))
        title.setStyleSheet(f"color: {Color1.name()};")
        self._layout.addWidget(title)

        desc = QLabel("主人照片（不限张数，支持多角度多光照）：")
        desc.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(12*S)}px;")
        self._layout.addWidget(desc)

        # 主人照片列表
        self._master_list = QWidget()
        self._master_layout = QVBoxLayout(self._master_list)
        self._master_layout.setContentsMargins(0, int(4*S), 0, 0)
        self._master_layout.setSpacing(int(4*S))
        self._layout.addWidget(self._master_list)

        # 添加主人照片按钮
        btn_add_master = QPushButton("  + 添加主人照片")
        btn_add_master.setStyleSheet(f"""
            QPushButton {{ background: {Color3.name()}; color: white; border: none;
                padding: {int(8*S)}px {int(16*S)}px; font-size: {int(13*S)}px;
                border-radius: {int(6*S)}px; font-family: 'Microsoft YaHei'; }}
            QPushButton:hover {{ background: {Color4.name()}; }}
        """)
        btn_add_master.clicked.connect(self._add_master_face)
        self._layout.addWidget(btn_add_master)

        self._layout.addSpacing(int(16 * S))

        # 其他人照片
        desc2 = QLabel("其他人照片（每人限 1 张）：")
        desc2.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(12*S)}px;")
        self._layout.addWidget(desc2)

        self._others_list = QWidget()
        self._others_layout = QVBoxLayout(self._others_list)
        self._others_layout.setContentsMargins(0, int(4*S), 0, 0)
        self._others_layout.setSpacing(int(4*S))
        self._layout.addWidget(self._others_list)

        btn_add_other = QPushButton("  + 添加其他人")
        btn_add_other.setStyleSheet(f"""
            QPushButton {{ background: {Color3.name()}; color: white; border: none;
                padding: {int(8*S)}px {int(16*S)}px; font-size: {int(13*S)}px;
                border-radius: {int(6*S)}px; font-family: 'Microsoft YaHei'; }}
            QPushButton:hover {{ background: {Color4.name()}; }}
        """)
        btn_add_other.clicked.connect(self._add_other_face)
        self._layout.addWidget(btn_add_other)

        self._layout.addStretch()
        self._refresh()

    def _refresh(self):
        """刷新人脸列表"""
        import json, os
        from tool.face_recognition import FACE_DIR

        # 清空现有列表
        while self._master_layout.count():
            w = self._master_layout.takeAt(0).widget()
            if w:
                w.deleteLater()
        while self._others_layout.count():
            w = self._others_layout.takeAt(0).widget()
            if w:
                w.deleteLater()

        faces_path = os.path.join(FACE_DIR, "faces.json")
        cfg = {"master": [], "others": {}}
        if os.path.exists(faces_path):
            with open(faces_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)

        # 主人照片
        for item in cfg.get("master", []):
            row = QHBoxLayout()
            lbl = QLabel(f"📷 {item.get('desc', '主人的照片')}")
            lbl.setStyleSheet(f"color: {Color1.name()}; font-size: {int(12*S)}px;")
            row.addWidget(lbl, 1)
            btn_del = QPushButton("删除")
            btn_del.setFixedWidth(int(60 * S))
            btn_del.setStyleSheet(f"""
                QPushButton {{ background: #e03030; color: white; border: none;
                    padding: {int(4*S)}px {int(8*S)}px; font-size: {int(11*S)}px;
                    border-radius: {int(4*S)}px; }}
                QPushButton:hover {{ background: #f06060; }}
            """)
            file_path = item.get("file", "")
            btn_del.clicked.connect(lambda checked, fp=file_path: self._delete_master(fp))
            row.addWidget(btn_del)
            self._master_layout.addLayout(row)

        # 其他人
        for name, val in cfg.get("others", {}).items():
            if isinstance(val, dict):
                relation = val.get("relation", "")
                file_path = val.get("file", "")
            else:
                relation = ""
                file_path = val
            row = QHBoxLayout()
            label_text = f"👤 {name}"
            if relation:
                label_text += f" ({relation})"
            lbl = QLabel(label_text)
            lbl.setStyleSheet(f"color: {Color1.name()}; font-size: {int(12*S)}px;")
            row.addWidget(lbl, 1)
            btn_del = QPushButton("删除")
            btn_del.setFixedWidth(int(60 * S))
            btn_del.setStyleSheet(f"""
                QPushButton {{ background: #e03030; color: white; border: none;
                    padding: {int(4*S)}px {int(8*S)}px; font-size: {int(11*S)}px;
                    border-radius: {int(4*S)}px; }}
                QPushButton:hover {{ background: #f06060; }}
            """)
            btn_del.clicked.connect(lambda checked, n=name: self._delete_other(n))
            row.addWidget(btn_del)
            self._others_layout.addLayout(row)

    def _add_master_face(self):
        from PyQt5.QtWidgets import QFileDialog, QInputDialog
        path, _ = QFileDialog.getOpenFileName(self, "选择主人照片", "", "图片 (*.jpg *.jpeg *.png)")
        if not path:
            return
        desc, ok = QInputDialog.getText(self, "照片描述", "请输入这张照片的描述（可不填）：")
        if not ok:
            desc = ""
        from tool.face_recognition import add_master_face
        if add_master_face(path, desc):
            print(f"[PCL] 已添加主人照片: {path}")
        self._refresh()

    def _add_other_face(self):
        from PyQt5.QtWidgets import QFileDialog, QInputDialog
        name, ok = QInputDialog.getText(self, "输入姓名", "请输入这个人的姓名：")
        if not ok or not name.strip():
            return
        relation, ok2 = QInputDialog.getText(self, "与主人的关系", "请输入这个人和主人的关系（如：朋友、同事、家人）：")
        if not ok2:
            relation = ""
        path, _ = QFileDialog.getOpenFileName(self, f"选择 {name} 的照片", "", "图片 (*.jpg *.jpeg *.png)")
        if not path:
            return
        from tool.face_recognition import add_other_face
        if add_other_face(path, name.strip(), relation.strip()):
            print(f"[PCL] 已添加 {name}({relation}) 的照片")
        self._refresh()

    def _delete_master(self, file_path):
        from tool.face_recognition import _load_faces_config, _save_faces_config, clear_cache, FACE_DIR
        cfg = _load_faces_config()
        cfg["master"] = [m for m in cfg.get("master", []) if m.get("file") != file_path]
        _save_faces_config(cfg)
        clear_cache()
        self._refresh()

    def _delete_other(self, name):
        from tool.face_recognition import delete_face
        delete_face(name)
        self._refresh()


# ==================== 记忆管理面板 ====================

class PCLMemoryManager(QScrollArea):
    """多角色记忆管理：查看/预览/清除/备份各角色记忆 + QQ 离线补拉状态"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.NoFrame)
        self.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        container = QWidget()
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(int(30 * S), int(30 * S), int(30 * S), int(30 * S))
        self._layout.setSpacing(int(14 * S))
        self.setWidget(container)

        title = QLabel("  💾 记忆管理")
        title.setFont(QFont("Microsoft YaHei", int(16 * S), QFont.Bold))
        title.setStyleSheet(f"color: {Color1.name()};")
        self._layout.addWidget(title)

        desc = QLabel("查看、预览、清除和备份各角色的记忆。\n清除后聊天记录将从对应记忆文件移除（不可恢复）。")
        desc.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(12*S)}px;")
        self._layout.addWidget(desc)

        # ===== 角色选择 =====
        row_pet = QHBoxLayout()
        lbl_pet = QLabel("角色：")
        lbl_pet.setStyleSheet(f"color: {Color1.name()}; font-size: {int(13*S)}px;")
        row_pet.addWidget(lbl_pet)
        self._pet_combo = QComboBox()
        try:
            from pets.pet_registry import get_pet_ids
            for pid in get_pet_ids():
                self._pet_combo.addItem(pid, pid)
        except Exception:
            pass
        self._pet_combo.currentIndexChanged.connect(lambda _: self._refresh())
        row_pet.addWidget(self._pet_combo)
        row_pet.addStretch()
        self._layout.addLayout(row_pet)

        # ===== 记忆文件列表 =====
        list_title = QLabel("📁 该角色记忆文件")
        list_title.setFont(QFont("Microsoft YaHei", int(14 * S), QFont.Bold))
        list_title.setStyleSheet(f"color: {Color1.name()}; margin-top: {int(8*S)}px;")
        self._layout.addWidget(list_title)

        self._mem_list = QWidget()
        self._mem_layout = QVBoxLayout(self._mem_list)
        self._mem_layout.setContentsMargins(0, int(4*S), 0, 0)
        self._mem_layout.setSpacing(int(4*S))
        self._layout.addWidget(self._mem_list)

        # ===== 预览区 =====
        prev_title = QLabel("👁 预览（最近 20 条）")
        prev_title.setFont(QFont("Microsoft YaHei", int(14 * S), QFont.Bold))
        prev_title.setStyleSheet(f"color: {Color1.name()}; margin-top: {int(8*S)}px;")
        self._layout.addWidget(prev_title)

        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setFixedHeight(int(160 * S))
        self._preview.setStyleSheet(
            f"QTextEdit {{ background: {Color8.name()}; color: {Color1.name()}; "
            f"border: 1px solid {Color5.name()}; border-radius: {int(6*S)}px; "
            f"font-size: {int(12*S)}px; }}")
        self._layout.addWidget(self._preview)

        # ===== 操作按钮 =====
        btn_row = QHBoxLayout()
        btn_backup = QPushButton("  📦 备份该角色记忆 ")
        btn_backup.setStyleSheet(self._btn_style("#2f8f4e"))
        btn_backup.clicked.connect(self._backup_pet)
        btn_row.addWidget(btn_backup)
        btn_clear_all = QPushButton("  🗑 清空该角色全部记忆 ")
        btn_clear_all.setStyleSheet(self._btn_style("#e03030"))
        btn_clear_all.clicked.connect(self._clear_pet_all)
        btn_row.addWidget(btn_clear_all)
        btn_row.addStretch()
        self._layout.addLayout(btn_row)

        # ===== QQ 离线补拉状态 =====
        off_title = QLabel("🕐 QQ 离线补拉状态")
        off_title.setFont(QFont("Microsoft YaHei", int(14 * S), QFont.Bold))
        off_title.setStyleSheet(f"color: {Color1.name()}; margin-top: {int(12*S)}px;")
        self._layout.addWidget(off_title)

        self._off_label = QLabel("")
        self._off_label.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(12*S)}px;")
        self._layout.addWidget(self._off_label)

        btn_off = QPushButton("  清空已处理消息 ID  ")
        btn_off.setStyleSheet(self._btn_style("#8a6d1a"))
        btn_off.clicked.connect(self._clear_processed_ids)
        self._layout.addWidget(btn_off)

        self._layout.addStretch()
        self._refresh()

    @staticmethod
    def _btn_style(bg):
        return f"""
            QPushButton {{ background: {bg}; color: white; border: none;
                padding: {int(8*S)}px {int(16*S)}px; font-size: {int(13*S)}px;
                border-radius: {int(6*S)}px; font-family: 'Microsoft YaHei'; }}
            QPushButton:hover {{ background: {bg}; opacity: 0.8; }}
        """

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                PCLMemoryManager._clear_layout(item.layout())

    # ===== 数据访问 =====
    def _current_pet(self):
        idx = self._pet_combo.currentIndex()
        return self._pet_combo.itemData(idx) if idx >= 0 else None

    def _pet_memory_dir(self, pet_id):
        try:
            from pets.pet_registry import get_memory_dir
            d = get_memory_dir(pet_id)
            if d:
                return d
        except Exception:
            pass
        return ""

    def _list_memory_files(self):
        """返回 [(相对名, 绝对路径)]：history/long_history + qq 分仓"""
        pet = self._current_pet()
        mdir = self._pet_memory_dir(pet) if pet else ""
        files = []
        if not mdir or not os.path.isdir(mdir):
            return files
        for f in ("history.json", "long_history.json"):
            p = os.path.join(mdir, f)
            if os.path.exists(p):
                files.append((f, p))
        qqdir = os.path.join(mdir, "qq")
        if os.path.isdir(qqdir):
            for f in sorted(os.listdir(qqdir)):
                if f.endswith(".json"):
                    files.append((f"qq/{f}", os.path.join(qqdir, f)))
        return files

    def _file_stats(self, path):
        """返回 (大小字节, 条数, 更新时间字符串)"""
        size = os.path.getsize(path) if os.path.exists(path) else 0
        count = 0
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "history" in data:
                entries = data.get("history") or []
            elif isinstance(data, list):
                entries = data
            else:
                entries = []
            count = len(entries)
        except Exception:
            pass
        try:
            mtime = time.strftime("%m-%d %H:%M", time.localtime(os.path.getmtime(path)))
        except Exception:
            mtime = "?"
        return size, count, mtime

    # ===== 界面刷新与操作 =====
    def _refresh(self):
        while self._mem_layout.count():
            item = self._mem_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                PCLMemoryManager._clear_layout(item.layout())

        files = self._list_memory_files()
        if not files:
            empty = QLabel("暂无记忆文件")
            empty.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(12*S)}px;")
            self._mem_layout.addWidget(empty)
        else:
            for rel, path in files:
                size, count, mtime = self._file_stats(path)
                if rel.startswith("qq/group_"):
                    label_text = f"👥 群聊记忆 {rel[8:-5]}"
                elif rel.startswith("qq/"):
                    label_text = f"👤 私聊记忆 {rel[3:-5]}"
                elif rel == "long_history.json":
                    label_text = "🧠 长文本记忆（与 QQ 大号共享）"
                else:
                    label_text = "💬 短文本记忆"

                row = QHBoxLayout()
                lbl = QLabel(f"{label_text}（{count} 条 / {size/1024:.1f} KB / {mtime}）")
                lbl.setStyleSheet(f"color: {Color1.name()}; font-size: {int(12*S)}px;")
                row.addWidget(lbl, 1)

                btn_view = QPushButton("查看")
                btn_view.setFixedWidth(int(52 * S))
                btn_view.setStyleSheet(self._btn_style("#2f6fbf"))
                btn_view.clicked.connect(lambda checked, p=path, r=rel: self._preview_file(p, r))
                row.addWidget(btn_view)

                btn_del = QPushButton("清除")
                btn_del.setFixedWidth(int(52 * S))
                btn_del.setStyleSheet(self._btn_style("#e03030"))
                btn_del.clicked.connect(lambda checked, p=path, r=rel: self._clear_file(p, r))
                row.addWidget(btn_del)

                self._mem_layout.addLayout(row)
        self._refresh_offline()

    def _preview_file(self, path, rel):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "history" in data:
                entries = data.get("history") or []
            elif isinstance(data, list):
                entries = data
            else:
                entries = []
            lines = []
            for e in entries[-20:]:
                if isinstance(e, dict):
                    role = str(e.get("role", "?"))
                    content = str(e.get("content", ""))[:100]
                    lines.append(f"[{role}] {content}")
                else:
                    lines.append(str(e)[:100])
            self._preview.setPlainText(f"文件：{rel}\n" + ("\n".join(lines) if lines else "（空）"))
        except Exception as e:
            self._preview.setPlainText(f"读取失败：{e}")

    def _clear_file(self, path, rel):
        try:
            if rel in ("history.json", "long_history.json"):
                # 覆盖为空结构（读取端要求 {"history": [...]} 格式，不能写裸列表）
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({"history": []}, f, ensure_ascii=False)
            else:
                os.remove(path)
            print(f"[PCL] 已清除记忆: {rel}")
            self._refresh()
        except Exception as e:
            print(f"[PCL] 清除记忆失败: {e}")

    def _clear_pet_all(self):
        from PyQt5.QtWidgets import QMessageBox
        pet = self._current_pet() or "当前角色"
        if QMessageBox.question(self, "确认", f"确定清空「{pet}」的全部记忆吗？（不可恢复）") != QMessageBox.Yes:
            return
        for rel, path in self._list_memory_files():
            self._clear_file(path, rel)
        self._refresh()

    def _backup_pet(self):
        pet = self._current_pet()
        mdir = self._pet_memory_dir(pet) if pet else ""
        if not mdir or not os.path.isdir(mdir):
            print("[PCL] 无记忆可备份")
            return
        import zipfile
        dst = os.path.join(
            os.path.expanduser("~"), "Desktop",
            f"AIpet_记忆备份_{pet or 'pet'}_{time.strftime('%Y%m%d_%H%M%S')}.zip")
        try:
            with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
                for root, _dirs, files in os.walk(mdir):
                    for f in files:
                        fp = os.path.join(root, f)
                        z.write(fp, os.path.relpath(fp, mdir))
            print(f"[PCL] 记忆已备份到: {dst}")
        except Exception as e:
            print(f"[PCL] 备份失败: {e}")

    # ===== QQ 离线补拉状态 =====
    def _refresh_offline(self):
        from tool.paths import data_path
        st = data_path("data", "qq_offline_state.json")
        pidf = data_path("data", "qq_processed_ids.json")
        last = "无记录"
        try:
            with open(st, "r", encoding="utf-8") as f:
                last = (json.load(f) or {}).get("last_exit_time", "无记录")
        except Exception:
            pass
        cnt = 0
        try:
            with open(pidf, "r", encoding="utf-8") as f:
                cnt = len((json.load(f) or {}).get("ids", []))
        except Exception:
            pass
        self._off_label.setText(f"上次退出时间：{last}\n已处理消息 ID 数：{cnt}")

    def _clear_processed_ids(self):
        from PyQt5.QtWidgets import QMessageBox
        from tool.paths import data_path
        if QMessageBox.question(self, "确认", "清空已处理消息 ID？（下次启动会重新补拉离线消息）") != QMessageBox.Yes:
            return
        try:
            pidf = data_path("data", "qq_processed_ids.json")
            os.makedirs(os.path.dirname(pidf), exist_ok=True)
            with open(pidf, "w", encoding="utf-8") as f:
                json.dump({"ids": []}, f, ensure_ascii=False)
            print("[PCL] 已清空处理 ID")
            self._refresh_offline()
        except Exception as e:
            print(f"[PCL] 清空失败: {e}")


# ==================== 启动按钮 ====================

class PCLLaunchButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__("  启动 AIpet 桌宠", parent)
        self.setFixedHeight(int(48 * S))
        self.setStyleSheet(f"""
            QPushButton {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 {THEME_COLORS['blue']['btn_start']},stop:1 {THEME_COLORS['blue']['btn_end']});
                color: white; border: none; font-size: {int(14*S)}px; font-weight: bold;
                font-family: 'Microsoft YaHei'; border-radius: {int(8*S)}px; }}
            QPushButton:hover {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 {THEME_COLORS['blue']['btn_end']},stop:1 {THEME_COLORS['blue']['btn_start']}); }}
        """)
        self.setIcon(QIcon(block_icon("Anvil")))
        self.setIconSize(QPixmap(block_icon("Anvil")).scaled(int(28 * S), int(28 * S)).size())


# ==================== 加载动画 ====================

class PCLLoadingOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self._angle = 0; self.hide()

    def showEvent(self, event):
        self._angle = 0; super().showEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 160))
        icon = QPixmap(block_icon("Anvil")).scaled(int(64 * S), int(64 * S), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        cx, cy = self.width() // 2, self.height() // 2 - int(20 * S)
        painter.translate(cx, cy); painter.rotate(self._angle)
        painter.drawPixmap(-int(32 * S), -int(32 * S), icon)
        painter.resetTransform()
        painter.setPen(Qt.white)
        font = QFont("Microsoft YaHei", int(14 * S)); font.setBold(True)
        painter.setFont(font)
        painter.drawText(self.rect().adjusted(0, 0, 0, -cy + int(50 * S)), Qt.AlignHCenter | Qt.AlignBottom, "正在启动桌宠...")

    def tick(self, angle): self._angle = angle; self.update()


# ==================== 桌宠管理面板 ====================

class PCLPetManager(QScrollArea):
    """多桌宠管理面板：查看/设为活动/添加/删除/打开文件夹"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.NoFrame)
        self.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        container = QWidget()
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(int(30 * S), int(30 * S), int(30 * S), int(30 * S))
        self._layout.setSpacing(int(12 * S))
        self.setWidget(container)

        title = QLabel("  🐾 桌宠管理")
        title.setFont(QFont("Microsoft YaHei", int(16 * S), QFont.Bold))
        title.setStyleSheet(f"color: {Color1.name()};")
        self._layout.addWidget(title)

        desc = QLabel("管理你的桌宠角色。设为活动后，启动桌宠 / QQ 将使用该角色的人设、声音与形象。")
        desc.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(12*S)}px;")
        desc.setWordWrap(True)
        self._layout.addWidget(desc)

        # 桌宠列表
        self._pet_list = QWidget()
        self._pet_layout = QVBoxLayout(self._pet_list)
        self._pet_layout.setContentsMargins(0, int(4*S), 0, 0)
        self._pet_layout.setSpacing(int(8*S))
        self._layout.addWidget(self._pet_list)

        # 添加桌宠按钮
        btn_add = QPushButton("  + 添加新桌宠（从模板创建）")
        btn_add.setStyleSheet(f"""
            QPushButton {{ background: {Color3.name()}; color: white; border: none;
                padding: {int(8*S)}px {int(16*S)}px; font-size: {int(13*S)}px;
                border-radius: {int(6*S)}px; font-family: 'Microsoft YaHei'; }}
            QPushButton:hover {{ background: {Color4.name()}; }}
        """)
        btn_add.clicked.connect(self._add_pet)
        self._layout.addWidget(btn_add)

        self._layout.addStretch()
        self._refresh()

    def _refresh(self):
        """刷新桌宠列表"""
        while self._pet_layout.count():
            w = self._pet_layout.takeAt(0)
            if w.widget():
                w.widget().deleteLater()
            elif w.layout():
                self._clear_layout(w.layout())

        try:
            from pets.pet_registry import get_all_pets_summary
            pets = get_all_pets_summary()
        except Exception as e:
            print(f"[PCL] 加载桌宠列表失败: {e}")
            pets = []

        if not pets:
            empty = QLabel("暂未发现任何桌宠角色。")
            empty.setStyleSheet(f"color: {Gray3.name()}; font-size: {int(12*S)}px;")
            self._pet_layout.addWidget(empty)
            return

        for p in pets:
            self._pet_layout.addWidget(self._make_pet_card(p))

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                PCLPetManager._clear_layout(item.layout())

    def _make_pet_card(self, p):
        """构造单个桌宠卡片"""
        card = QWidget()
        card.setStyleSheet(f"""
            QWidget {{ background: {Color8.name()}; border: 1px solid {Color5.name()};
                border-radius: {int(8*S)}px; }}
        """)
        v = QVBoxLayout(card)
        v.setContentsMargins(int(14*S), int(12*S), int(14*S), int(12*S))
        v.setSpacing(int(6*S))

        # 名称行 + 头像 + 活动标记
        hdr = QHBoxLayout()
        avatar_path = ""
        if p.get("avatar"):
            from pets.pet_registry import PETS_DIR
            cand = os.path.join(PETS_DIR, p["id"], p["avatar"])
            if os.path.exists(cand):
                avatar_path = cand
        if avatar_path:
            av = QLabel()
            av.setFixedSize(int(40 * S), int(40 * S))
            av.setScaledContents(True)
            av.setStyleSheet("border: none; background: transparent;")
            av.setPixmap(QPixmap(avatar_path).scaled(
                int(40 * S), int(40 * S), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            hdr.addWidget(av)
        name = QLabel(p.get("display_name") or p.get("name", "?"))
        name.setFont(QFont("Microsoft YaHei", int(14*S), QFont.Bold))
        name.setStyleSheet(f"color: {Color1.name()}; border: none;")
        hdr.addWidget(name)
        if p.get("is_active"):
            badge = QLabel(" 活动 ")
            badge.setStyleSheet(f"""
                background: {GreenDark.name()}; color: white; border: none;
                padding: {int(2*S)}px {int(8*S)}px; font-size: {int(10*S)}px;
                border-radius: {int(4*S)}px; font-weight: bold;
            """)
            hdr.addWidget(badge)
        hdr.addStretch()
        v.addLayout(hdr)

        # 简介
        intro = p.get("intro", "")
        if intro:
            lbl_intro = QLabel(intro)
            lbl_intro.setWordWrap(True)
            lbl_intro.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(11*S)}px; border: none;")
            v.addWidget(lbl_intro)

        # 能力徽章
        caps = p.get("capabilities", {})
        badges = []
        if caps.get("has_fgimages"):
            badges.append(("2D", "#1370f3"))
        if caps.get("has_live2d"):
            badges.append(("Live2D", "#d4a020"))
        if caps.get("short_tts"):
            badges.append(("短语音", "#30a030"))
        if caps.get("long_tts"):
            badges.append(("长语音", "#30a030"))
        if caps.get("has_fgimages") is False and not caps.get("has_live2d"):
            badges.append(("纯文本", "#808080"))
        if badges:
            cap_row = QHBoxLayout()
            cap_row.setSpacing(int(4*S))
            for text, color in badges:
                b = QLabel(f" {text} ")
                b.setStyleSheet(f"""
                    background: {color}; color: white; border: none;
                    padding: {int(2*S)}px {int(6*S)}px; font-size: {int(10*S)}px;
                    border-radius: {int(4*S)}px; font-weight: bold;
                """)
                cap_row.addWidget(b)
            cap_row.addStretch()
            v.addLayout(cap_row)

        # 操作按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(int(8*S))

        if not p.get("is_active"):
            btn_active = QPushButton("⭐ 设为活动")
            btn_active.setStyleSheet(self._btn_style(GreenDark.name()))
            btn_active.clicked.connect(lambda checked, pid=p["id"]: self._set_active(pid))
            btn_row.addWidget(btn_active)

        btn_open = QPushButton("📂 打开文件夹")
        btn_open.setStyleSheet(self._btn_style(Color3.name()))
        btn_open.clicked.connect(lambda checked, pid=p["id"]: self._open_dir(pid))
        btn_row.addWidget(btn_open)

        btn_del = QPushButton("🗑 删除")
        btn_del.setStyleSheet(self._btn_style("#e03030"))
        btn_del.clicked.connect(lambda checked, pid=p["id"], nm=p.get("name",""): self._delete_pet(pid, nm))
        btn_row.addWidget(btn_del)

        btn_row.addStretch()
        v.addLayout(btn_row)

        return card

    @staticmethod
    def _btn_style(bg):
        return f"""
            QPushButton {{ background: {bg}; color: white; border: none;
                padding: {int(5*S)}px {int(12*S)}px; font-size: {int(11*S)}px;
                border-radius: {int(5*S)}px; font-family: 'Microsoft YaHei'; }}
            QPushButton:hover {{ opacity: 0.85; }}
        """

    def _set_active(self, pet_id):
        from pets.pet_registry import set_active_pet_id
        if set_active_pet_id(pet_id):
            print(f"[PCL] 已设活动桌宠: {pet_id}")
        self._refresh()

    def _open_dir(self, pet_id):
        from pets.pet_registry import get_pet_dir
        d = get_pet_dir(pet_id)
        if os.path.isdir(d):
            try:
                os.startfile(d)  # Windows
            except Exception:
                subprocess.Popen(["explorer", d])
        else:
            print(f"[PCL] 目录不存在: {d}")

    def _add_pet(self):
        """从模板创建新桌宠"""
        from PyQt5.QtWidgets import QInputDialog, QMessageBox
        pet_id, ok = QInputDialog.getText(
            self, "新建桌宠", "请输入桌宠 ID（英文/数字，将作为文件夹名）：")
        if not ok or not pet_id.strip():
            return
        pet_id = pet_id.strip()
        # 校验：仅英文数字下划线
        import re
        if not re.fullmatch(r"[A-Za-z0-9_\-]+", pet_id):
            QMessageBox.warning(self, "无效 ID", "桌宠 ID 只能包含英文字母、数字、下划线或连字符。")
            return

        from pets.pet_registry import PETS_DIR, get_pet_ids
        if pet_id in get_pet_ids():
            QMessageBox.warning(self, "ID 已存在", f"桌宠 ID「{pet_id}」已存在。")
            return

        name, ok2 = QInputDialog.getText(self, "桌宠名称", "请输入显示名称（如：丛雨）：")
        name = name.strip() or pet_id

        # 若存在模板目录则复制，否则新建空目录
        import shutil
        dst = os.path.join(PETS_DIR, pet_id)
        tpl = os.path.join(PETS_DIR, "_template")
        try:
            os.makedirs(dst, exist_ok=True)
            if os.path.isdir(tpl):
                shutil.copytree(tpl, dst, dirs_exist_ok=True)
        except Exception as e:
            QMessageBox.warning(self, "创建失败", f"创建目录失败: {e}")
            return

        # 写入最小 pet.json
        import json
        pet_json = {
            "id": pet_id,
            "name": name,
            "display_name": name,
            "intro": "",
            "avatar": "",
            "prompt": {"short": "prompt.txt", "long": "longtext_prompt.txt"},
            "model": {
                "default": "2d",
                "has_live2d": False,
                "has_fgimages": False,
                "fgimages_prefix": "",
                "fgimages_sets": [],
                "live2d_dir": "live2d/"
            },
            "languages": {"primary": "ja", "secondary": "zh", "dialog_language": "zh"},
            "voices": {
                "short_emotions": [],
                "short_ref_dir": "voices/short/",
                "long_ref_audio": "",
                "long_ref_text": ""
            },
            "sticker": {"dir": "biaoqingbao/"},
            "memory": {"isolated": True, "dir": "memory/"},
            "capabilities": {
                "chat": True, "short_tts": False, "long_tts": False,
                "screen_vision": True, "camera_vision": True,
                "face_recognition": True, "qq": True
            }
        }
        pet_json_path = os.path.join(dst, "pet.json")
        with open(pet_json_path, "w", encoding="utf-8") as f:
            json.dump(pet_json, f, ensure_ascii=False, indent=2)

        # 写空 prompt
        prompt_path = os.path.join(dst, "prompt.txt")
        if not os.path.exists(prompt_path):
            with open(prompt_path, "w", encoding="utf-8") as f:
                f.write(f"你是{name}，一个可爱的 AI 桌宠角色。\n请自然、亲切地与主人交流。")

        # 注册进 pet_list.json（注册表是 PCL 列表的权威来源）
        from pets.pet_registry import register_pet
        register_pet(pet_id)

        self._refresh()
        print(f"[PCL] 已创建新桌宠: {pet_id}")

    def _delete_pet(self, pet_id, name):
        from PyQt5.QtWidgets import QMessageBox
        from pets.pet_registry import PETS_DIR, get_active_pet_id
        # 丛雨保护：默认桌宠不可删除（用户明确要求）
        if pet_id == "murasame":
            QMessageBox.warning(self, "无法删除", "「丛雨」是默认桌宠，不允许删除。")
            return
        if pet_id == get_active_pet_id():
            QMessageBox.warning(self, "无法删除", "不能删除当前活动的桌宠，请先切换到其他桌宠。")
            return
        ret = QMessageBox.question(
            self, "确认删除",
            f"确定删除桌宠「{name}」({pet_id}) 吗？\n其目录（含人设/立绘/记忆）将被永久删除。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if ret != QMessageBox.Yes:
            return
        import shutil
        d = os.path.join(PETS_DIR, pet_id)
        try:
            shutil.rmtree(d, ignore_errors=True)
            print(f"[PCL] 已删除桌宠: {pet_id}")
        except Exception as e:
            QMessageBox.warning(self, "删除失败", f"删除失败: {e}")
        # 从 pet_list.json 移除条目
        from pets.pet_registry import unregister_pet
        unregister_pet(pet_id)
        self._refresh()


# ==================== Live2D 显示调参面板（本地滑块 + 点保存写入 pet.json） ====================

class PCLLive2DTunePanel(QWidget):
    """Live2D 显示调参：滑块只在本地改动，「保存到角色」写入 pet.json（桌宠运行中则同时实时应用）。
    与设置页其他选项一致——不自动联网，避免卡顿。"""

    _BASE = "http://localhost:28565"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sliders = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, int(18 * S), 0, 0)
        layout.setSpacing(int(10 * S))

        title = QLabel("  🎭 Live2D 显示调参")
        title.setFont(QFont("Microsoft YaHei", int(14 * S), QFont.Bold))
        title.setStyleSheet(f"color: {Color1.name()};")
        layout.addWidget(title)
        desc = QLabel("拖动滑块设置数值，点击「保存到角色」写入 pet.json（下次启动生效；桌宠运行中会同时实时应用）。")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(11 * S)}px;")
        layout.addWidget(desc)

        row = QHBoxLayout()
        lbl_pet = QLabel("角色:")
        lbl_pet.setStyleSheet(f"color: {Color1.name()}; font-size: {int(13*S)}px;")
        self.combo = QComboBox()
        self.combo.setMinimumWidth(int(160 * S))
        try:
            from pets.pet_registry import get_all_pets_summary, get_active_pet_id
            active = get_active_pet_id()
            for p in get_all_pets_summary():
                self.combo.addItem(p.get("display_name") or p.get("name", "?"), p["id"])
            idx = self.combo.findData(active)
            if idx >= 0:
                self.combo.setCurrentIndex(idx)
        except Exception:
            pass
        self.combo.currentIndexChanged.connect(self._load_from_pet_json)
        row.addWidget(lbl_pet)
        row.addWidget(self.combo)
        row.addStretch()
        layout.addLayout(row)

        self._add_slider(layout, "scale", "模型缩放", 0.1, 4.0, 0.05)
        self._add_slider(layout, "offset_x", "模型水平偏移", -800, 800, 10)
        self._add_slider(layout, "offset_y", "模型垂直偏移", -800, 800, 10)
        self._add_slider(layout, "window_ratio", "窗口宽高比", 0.2, 2.0, 0.05)
        self._add_slider(layout, "window_height_ratio", "窗口高度占屏比", 0.15, 0.95, 0.05)
        self._add_slider(layout, "font_scale", "字号缩放", 0.05, 1.5, 0.05)
        self._add_slider(layout, "text_offset_x", "文本框水平偏移", -600, 600, 20)
        self._add_slider(layout, "text_offset_y", "文本框垂直偏移", -600, 600, 20)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(int(10 * S))
        btn_live = QPushButton(" 🔄 读取桌宠当前值")
        btn_save = QPushButton(" 💾 保存到角色")
        btn_reset = QPushButton(" 🎯 重置位置")
        for b in (btn_live, btn_save, btn_reset):
            b.setStyleSheet(f"""
                QPushButton {{ background: {Color6.name()}; color: {Color1.name()};
                    border: 1px solid {Color5.name()}; padding: {int(8*S)}px {int(14*S)}px;
                    font-size: {int(12*S)}px; font-family: 'Microsoft YaHei'; border-radius: {int(6*S)}px; }}
                QPushButton:hover {{ background: {Color4.name()}; color: white; border: 1px solid {Color3.name()}; }}
            """)
        btn_live.clicked.connect(self._load_from_live)
        btn_save.clicked.connect(self._save)
        btn_reset.clicked.connect(self._reset)
        btn_row.addWidget(btn_live)
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_reset)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(11*S)}px;")
        layout.addWidget(self.lbl_status)

        self._load_from_pet_json()

    def _current_pet_id(self):
        return self.combo.currentData()

    def _add_slider(self, layout, key, label, lo, hi, step):
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setFixedWidth(int(115 * S))
        lbl.setStyleSheet(f"color: {Color1.name()}; font-size: {int(12*S)}px;")
        slider = QSlider(Qt.Horizontal)
        slider.setRange(int(lo / step), int(hi / step))
        val = QLabel("")
        val.setFixedWidth(int(60 * S))
        val.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(11*S)}px;")
        slider.valueChanged.connect(lambda v, lab=val, st=step: lab.setText(f"{v * st:g}"))
        self._sliders[key] = (slider, step)
        row.addWidget(lbl)
        row.addWidget(slider, 1)
        row.addWidget(val)
        layout.addLayout(row)

    def _current_values(self):
        out = {}
        for key, (slider, step) in self._sliders.items():
            out[key] = round(slider.value() * step, 2)
        return out

    def _set_slider_value(self, key, value):
        slider, step = self._sliders[key]
        slider.blockSignals(True)
        try:
            slider.setValue(int(round(float(value) / step)))
        except (TypeError, ValueError):
            pass
        slider.blockSignals(False)

    def _load_from_pet_json(self):
        """从角色 pet.json 本地读取显示参数（不联网、不卡顿）"""
        pid = self._current_pet_id()
        if not pid:
            return
        try:
            from pets.pet_registry import get_live2d_display
            d = get_live2d_display(pid)
            for key in self._sliders:
                if key in d:
                    self._set_slider_value(key, d[key])
            self.lbl_status.setText(f"已加载 {pid} 的已保存参数")
        except Exception as e:
            self.lbl_status.setText(f"读取失败: {e}")

    def _post(self, path, payload=None):
        try:
            data = json.dumps(payload).encode("utf-8") if payload is not None else b""
            req = urllib.request.Request(
                f"{self._BASE}{path}", data=data, method="POST",
                headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=2).read()
            return True
        except Exception:
            return False

    def _get(self, path):
        try:
            with urllib.request.urlopen(f"{self._BASE}{path}", timeout=2) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            return None

    def _save(self):
        """写入 pet.json（核心）；桌宠运行中则同时实时应用"""
        pid = self._current_pet_id()
        if not pid:
            return
        try:
            from pets.pet_registry import save_live2d_display
            save_live2d_display(pid, **self._current_values())
        except Exception as e:
            self.lbl_status.setText(f"保存失败: {e}")
            return
        if self._post("/live2d/display", self._current_values()):
            self.lbl_status.setText("✅ 已保存到 pet.json 并实时应用（桌宠 Live2D 模式可见）")
        else:
            self.lbl_status.setText("✅ 已保存到 pet.json（重启桌宠生效；当前桌宠未运行）")

    def _reset(self):
        self._set_slider_value("offset_x", 0)
        self._set_slider_value("offset_y", 0)
        self.lbl_status.setText("位置滑块已归零，点「保存到角色」生效")

    def _load_from_live(self):
        """手动读取运行中桌宠的当前参数（点击时才联网）"""
        data = self._get("/live2d/display")
        if not data or not isinstance(data.get("state"), dict):
            self.lbl_status.setText("⚠ 无法读取（桌宠未运行？）")
            return
        state = data["state"]
        for key in self._sliders:
            if key in state:
                self._set_slider_value(key, state[key])
        self.lbl_status.setText("✅ 已读取桌宠当前显示参数")


# ==================== 提示词编辑器 ====================

class PCLPromptEditor(QWidget):
    """提示词编辑器：查看/编辑各角色短文本与长文本人设"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(int(30 * S), int(30 * S), int(30 * S), int(30 * S))
        layout.setSpacing(int(12 * S))

        title = QLabel("  📝 提示词编辑器")
        title.setFont(QFont("Microsoft YaHei", int(16 * S), QFont.Bold))
        title.setStyleSheet(f"color: {Color1.name()};")
        layout.addWidget(title)
        desc = QLabel("编辑各角色的人设提示词。短文本=桌面短句模式；长文本=长文本模式与 QQ 聊天。保存后下次对话生效。")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(12*S)}px;")
        layout.addWidget(desc)

        row = QHBoxLayout()
        lbl_pet = QLabel("角色:")
        lbl_pet.setStyleSheet(f"color: {Color1.name()}; font-size: {int(13*S)}px;")
        self.combo = QComboBox()
        self.combo.setMinimumWidth(int(180 * S))
        try:
            from pets.pet_registry import get_all_pets_summary
            for p in get_all_pets_summary():
                self.combo.addItem(p.get("display_name") or p.get("name", "?"), p["id"])
        except Exception:
            pass
        self.combo.currentIndexChanged.connect(self._load)
        row.addWidget(lbl_pet)
        row.addWidget(self.combo)
        row.addStretch()
        layout.addLayout(row)

        lbl_short = QLabel("短文本提示词 (prompt.txt)")
        lbl_short.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(12*S)}px;")
        layout.addWidget(lbl_short)
        self.edit_short = QTextEdit()
        layout.addWidget(self.edit_short, 1)

        lbl_long = QLabel("长文本提示词 (longtext_prompt.txt)")
        lbl_long.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(12*S)}px;")
        layout.addWidget(lbl_long)
        self.edit_long = QTextEdit()
        layout.addWidget(self.edit_long, 1)

        btn_row = QHBoxLayout()
        btn_save = QPushButton(" 💾 保存")
        btn_reload = QPushButton(" 🔄 重新加载")
        for b in (btn_save, btn_reload):
            b.setStyleSheet(f"""
                QPushButton {{ background: {Color3.name()}; color: white; border: none;
                    padding: {int(8*S)}px {int(16*S)}px; font-size: {int(13*S)}px;
                    border-radius: {int(6*S)}px; font-family: 'Microsoft YaHei'; }}
                QPushButton:hover {{ background: {Color4.name()}; }}
            """)
        btn_save.clicked.connect(self._save)
        btn_reload.clicked.connect(self._load)
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(12*S)}px;")
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_reload)
        btn_row.addWidget(self.lbl_status)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._load()

    def _current_pet_id(self):
        return self.combo.currentData()

    def _load(self):
        try:
            from pets.pet_registry import get_prompt_path
            pid = self._current_pet_id()
            if not pid:
                return
            for edit, kind in ((self.edit_short, "short"), (self.edit_long, "long")):
                p = get_prompt_path(kind, pid)
                text = ""
                if os.path.exists(p):
                    with open(p, "r", encoding="utf-8") as f:
                        text = f.read()
                edit.setPlainText(text)
            self.lbl_status.setText(f"已加载 {pid}")
        except Exception as e:
            self.lbl_status.setText(f"加载失败: {e}")

    def _save(self):
        try:
            from pets.pet_registry import get_prompt_path
            pid = self._current_pet_id()
            for edit, kind in ((self.edit_short, "short"), (self.edit_long, "long")):
                p = get_prompt_path(kind, pid)
                with open(p, "w", encoding="utf-8") as f:
                    f.write(edit.toPlainText())
            self.lbl_status.setText("✅ 已保存")
        except Exception as e:
            self.lbl_status.setText(f"保存失败: {e}")
