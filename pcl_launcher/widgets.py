"""PCL 风格 UI 控件"""

import os
import json
import subprocess
import urllib.request

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPixmap
from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QSpinBox, QScrollArea,
    QLineEdit, QSlider, QDoubleSpinBox, QComboBox, QTextEdit,
    QDialog, QPlainTextEdit, QMessageBox, QFileDialog
)

from .colors import *
from .colors import _app_base_dir
# 顶层导入：确保 PyInstaller 一定把立绘工坊打进包内
# （函数内相对导入曾导致打包遗漏 → 点击按钮静默无反应）
from .portrait_studio import PortraitStudio  # noqa: F401

S = 1.0

# ==================== 标题栏 ====================









class PCLSettingsPanel(QWidget):
    size_changed = pyqtSignal(int, int)
    color_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        # 外壳布局：上 = 可滚动设置内容区，下 = 固定底部条
        # （保存按钮固定在右下角、不随内容滚动；本面板为全局唯一设置宿主，
        #   所有分类共用，非单个主题专属）
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._widgets = {}
        self._config_path = None

        # 可滚动内容区（样式与原 QScrollArea 一致：透明、无边框）
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        outer.addWidget(self._scroll, 1)

        container = QWidget()
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(int(30 * S), int(30 * S), int(30 * S), int(30 * S))
        self._layout.setSpacing(int(14 * S))
        self._scroll.setWidget(container)

        title = QLabel("  ⚙ 桌宠配置")
        title.setFont(QFont("Microsoft YaHei", int(16 * S), QFont.Bold))
        title.setStyleSheet(f"color: {Color1.name()};")
        self._layout.addWidget(title)

        # ===== 顶部分类标签：全部配置 / 桌宠配置 / QQ配置 / 微信配置 =====
        self._cat_entries = []
        self._cat_filter = "all"
        self._cur_layout = self._layout
        chip_style = f"""
            QPushButton {{ background: rgba(255,255,255,150); color: {Color1.name()};
                border: 1px solid {Gray5.name()}; padding: {int(5*S)}px {int(14*S)}px;
                font-size: {int(12*S)}px; border-radius: {btn_radius()}px;
                font-family: 'Microsoft YaHei'; }}
            QPushButton:hover {{ background: rgba(255,255,255,220); }}
            QPushButton:checked {{ background: {Color3.name()}; color: white;
                border-color: {Color3.name()}; font-weight: bold; }}
        """
        cat_row = QHBoxLayout(); cat_row.setSpacing(int(6 * S))
        self._cat_btns = {}
        for _key, _label in (("all", "全部配置"), ("pet", "桌宠配置"),
                             ("qq", "QQ配置"), ("wx", "微信配置"),
                             ("other", "其他配置")):
            _b = QPushButton(f"  {_label}")
            _b.setCheckable(True)
            _b.setCursor(Qt.PointingHandCursor)
            _b.setStyleSheet(chip_style)
            _b.clicked.connect(lambda _=False, k=_key: self._switch_cat(k))
            self._cat_btns[_key] = _b
            cat_row.addWidget(_b)
        cat_row.addStretch()
        self._layout.addLayout(cat_row)
        self._cat_btns["all"].setChecked(True)
        # 桌宠配置 = 基础/对话/语音/立绘/桌宠显示 等桌宠侧分区
        self._open_box(("all", "pet"))

        # ===== ① 基础信息与密钥 =====
        self._section("基础信息与密钥", "🔑")
        self._add_text_input("user_name", "使用者名称", "")
        self._add_text_input("deepseek_api_key", "DeepSeek API Key", "", placeholder="sk-...")
        self._add_text_input("qwen_api_key", "Qwen API Key", "", placeholder="sk-...")

        # ===== ② 对话模型与推理 =====
        self._section("对话模型与推理", "🤖")
        self._add_slider("model_type", "对话模型", ["local", "deepseek", "qwen"], "qwen")
        self._add_model_combo(
            "short_model_name", "短文本模型名",
            ["qwen-plus", "qwen3.7-plus", "qwen3.7-flash", "qwen3.6-flash", "qwen3.5-flash",
             "deepseek-v4-flash", "deepseek-v4-pro", "deepseek-chat"],
            "qwen-plus",
            hint="可编辑：仅限 deepseek/qwen 两族模型名"
        )
        self._add_slider("reasoning_level", "推理等级", ["off", "low", "high", "max"], "off")
        self._add_slider("force_gpu_check", "强制 GPU 检查", ["false", "true"], "false")

        # ===== ③ 长文本输出 =====
        self._section("长文本输出", "📝")
        self._add_slider("longtext_enabled", "长文本输出模式", ["false", "true"], "true")
        self._add_slider("longtext_model", "长文本对话模型", ["qwen", "deepseek"], "deepseek")
        self._add_model_combo(
            "longtext_model_name", "长文本模型名",
            ["deepseek-v4-flash", "deepseek-v4-pro", "deepseek-chat",
             "qwen-plus", "qwen3.7-plus", "qwen3.7-flash", "qwen3.6-flash"],
            "deepseek-v4-flash",
            hint="可编辑：仅限 deepseek/qwen 两族模型名"
        )

        # ===== ④ 语音与视觉识别 =====
        self._section("语音合成与识别", "🗣")
        self._add_slider("voice_synthesis_enable", "启用语音合成（关闭可加快对话回复）",
                         ["false", "true"], "true",
                         hint="开启时每条回复都会合成语音（较慢）；关闭后只显示文字，回复明显更快")
        self._add_slider("tts_type", "TTS 语音合成", ["local", "cloud"], "local")
        self._add_model_combo(
            "vision_model_name", "视觉识别模型名",
            ["qwen3-vl-plus", "qwen3-vl-flash", "deepseek-v4-flash-vision-exp",
             "qwen-vl-max", "qwen-vl-plus"],
            "qwen3-vl-plus",
            hint="可编辑：QQ识图/摄像头/微信识图统一使用"
        )
        self._add_slider("screen_type", "屏幕识别", ["false", "true"], "false")
        self._add_slider("voice_trigger", "语音识别", ["false", "true"], "false")

        # ===== ⑤ Live2D 与立绘 =====
        self._section("Live2D 与立绘", "🎭")
        # 人脸识别相关设置已迁移至「插件 → 人脸识别 → 设置」（face_recognition_enabled/
        # camera_enabled/camera_id/camera_interval 由插件设置界面统一管理）
        self._add_slider("live2d_enabled", "Live2D 模式", ["false", "true"], "true")
        self._add_slider("portrait", "立绘类型", ["a", "b"], "b")
        # 立绘自动切换（a/b 两套之间的灵动切换）属于「Live2D 与立绘」这一区
        self._add_slider("portrait_auto_switch", "自动切换立绘类型（a / b 两套）",
                         ["false", "true"], "true",
                         hint="开启时：说话时会按概率在 a/b 两套立绘间平滑切换（灵动效果）。\n"
                              "只有两套立绘都有当前这身衣服时才会切换，衣服保持不变。\n"
                              "关闭后立绘类型固定不动，可用桌宠右键菜单手动切换。")

        # ===== ⑥ QQ 聊天配置 =====
        self._open_box(("all", "qq"))
        self._section("QQ 聊天配置", "💬")
        self._add_text_input("qq_owner_id", "主主人 QQ 号（共享记忆）", "", placeholder="如：123456789（白名单第一位）")
        self._add_text_input("qq_master_ids_text", "额外主人白名单 QQ 号", "",
                             placeholder="逗号分隔，最多 4 个，如：111111,222222")

        # ===== 对话调节 =====
        cap_lbl = QLabel("  📐 对话调节")
        cap_lbl.setFont(QFont("Microsoft YaHei", int(12 * S), QFont.Bold))
        cap_lbl.setStyleSheet(f"color: {Color1.name()}; margin-top: {int(14*S)}px;")
        self._cur_layout.addWidget(cap_lbl)
        self._add_spin("qq_max_reply_chars", "单条回复最多字数（0=不限）", 0, 2000, 0,
                       hint="不是把话截断：AI 会尽量在这个字数内把意思表达完整；"
                            "实在说不完时自动拆成 2~3 条短消息依次发出（内容不丢）。")
        self._add_spin("qq_max_replies_per_conversation",
                       "单条回复最多发几条消息（0=不限）", 0, 30, 0,
                       hint="一次回复最多拆成几条消息发出（防刷屏）；"
                            "超出条数时多余句子会合并进最后一条，内容不丢。")
        # 对话调节改动即写盘（运行中的 QQ 桥接实时读取生效，无需重启 QQ）
        self._wire_autosave("spin", "qq_max_reply_chars")
        self._wire_autosave("spin", "qq_max_replies_per_conversation")

        # ===== 私信回复范围 =====
        pm_lbl = QLabel("  📨 私信回复范围")
        pm_lbl.setFont(QFont("Microsoft YaHei", int(12 * S), QFont.Bold))
        pm_lbl.setStyleSheet(f"color: {Color1.name()}; margin-top: {int(14*S)}px;")
        self._cur_layout.addWidget(pm_lbl)
        self._add_slider("qq_private_enable", "允许回复私信（总开关）", ["true", "false"], "true",
                         hint="关闭后完全不回复任何私信（连主人也不回）。改动即时生效，无需重启 QQ。")
        self._add_slider("qq_private_reply_stranger", "回复陌生人私信", ["true", "false"], "true",
                         hint="非好友（临时会话/陌生网友）发来的私信是否回复。"
                              "关闭后只忽略陌生人，好友与主人不受影响。")
        self._add_slider("qq_private_reply_friend", "回复好友私信", ["true", "false"], "true",
                         hint="好友（含从群里点开的临时会话）发来的私信是否回复。")
        self._add_slider("qq_private_master_only", "只回复主人私信", ["false", "true"], "false",
                         hint="开启后仅回复主人白名单里的 QQ 私信（覆盖上面两个范围开关）。")
        for _pk in ("qq_private_enable", "qq_private_reply_stranger",
                    "qq_private_reply_friend", "qq_private_master_only"):
            self._wire_autosave("slider", _pk)

        self._add_slider("qq_enabled", "QQ 功能总开关", ["false", "true"], "false")
        self._add_slider("qq_send_sticker", "QQ 表情包", ["false", "true"], "true")
        self._add_slider("qq_send_voice", "QQ 语音消息 (F5-TTS)", ["false", "true"], "false")
        self._add_slider("qq_vision_enabled", "QQ 图片识别", ["false", "true"], "true")
        self._add_slider("qq_allow_groups", "QQ 群聊 (需@)", ["false", "true"], "true")
        self._add_slider("qq_offline_enable", "QQ 离线补拉", ["true", "false"], "true",
                         hint="启动时补回离线期间的消息。依赖 NapCat 支持 get_friend_msg_history；"
                              "若你的 NapCat 不支持导致启动慢/连接异常，可在此关闭")
        self._add_slider("qq_auto_offline_enable", "QQ 空闲自动离线", ["false", "true"], "false",
                         hint="开启：长时间没人说话后自动进入离线模式（状态显示「离开」、暂停自动回复不打扰），"
                              "主人发消息立即恢复在线正常回复。关闭：始终保持活跃，不会自动离线导致不回复")
        self._add_spin("qq_auto_offline_minutes", "空闲自动离线等待 (分钟)", 1, 180, 30)
        self._add_slider("qq_lively_enable", "QQ 活泼模式", ["false", "true"], "false",
                         hint="开启：自动读取所在群聊的消息，间隔冷却后主动接一句话活跃群气氛"
                              "（不会 @ 人、不会每条都回）。关闭：仅在被 @ 时回复群聊")
        self._add_spin("qq_lively_interval", "活泼接话间隔 (分钟)", 1, 120, 15)

        # ===== ⑦ 微信 ClawBot 配置 =====
        self._open_box(("all", "wx"))
        self._section("微信 ClawBot 配置", "💬")
        self._add_slider("wechat_enabled", "微信 ClawBot 总开关", ["false", "true"], "false")
        self._add_slider("wechat_send_voice", "微信语音回复（尚不支持此功能）", ["false", "true"], "false")
        self._add_text_input("wechat_owner_id", "微信白名单（xxx@im.wechat，空=回复所有人）", "",
                             placeholder="如：wxid_xxx@im.wechat")

        # ===== ⑧ 桌宠显示与空闲行为 =====
        self._open_box(("all", "pet"))
        self._section("桌宠显示与空闲行为", "🖥")
        self._add_spin("screen_interval", "屏幕截图间隔 (秒)", 60, 3600, 300)
        self._add_spin("screen_index", "桌宠显示屏幕编号", 0, 3, 0)
        self._add_spin("idle_thinking_minutes", "空闲发呆阈值 (分钟)", 1, 60, 3)
        self._add_spin("idle_away_minutes", "空闲离屏阈值 (分钟)", 2, 120, 10)
        self._add_double_spin("DEFAULT_PORTRAIT_SCREEN_RATIO", "立绘高度比例", 0.1, 1.0, 0.8, 0.05)

        # 通用区（Live2D 调参面板）：全部与桌宠分类可见
        self._open_box(("all", "pet"))

        self._cur_layout.addSpacing(int(10 * S))

        # Live2D 显示调参面板（PCL → 桌宠 API 实时应用/保存）
        self._cur_layout.addWidget(PCLLive2DTunePanel())

        # ===== 「其他」分类：更新日志（查看 / 导出 / 打开目录）=====
        self._open_box(("all", "other"))
        log_label = QLabel("  📜 更新日志")
        log_label.setFont(QFont("Microsoft YaHei", int(13 * S), QFont.Bold))
        log_label.setStyleSheet(f"color: {Color1.name()}; margin-top: {int(16*S)}px;")
        self._cur_layout.addWidget(log_label)
        log_row = QHBoxLayout(); log_row.setSpacing(int(8 * S))
        log_style = f"""
            QPushButton {{ background: {Color6.name()}; color: {Color1.name()};
                border: 1px solid {Color5.name()}; padding: {int(7*S)}px {int(14*S)}px;
                font-size: {int(12*S)}px; border-radius: {btn_radius()}px;
                font-family: 'Microsoft YaHei'; }}
            QPushButton:hover {{ background: {Color4.name()}; color: white; }}
        """
        btn_view_log = QPushButton("  📖 查看日志")
        btn_export_log = QPushButton("  📤 导出日志")
        btn_open_log = QPushButton("  📂 打开目录")
        for _b in (btn_view_log, btn_export_log, btn_open_log):
            _b.setStyleSheet(log_style)
            _b.setCursor(Qt.PointingHandCursor)
        btn_view_log.setToolTip("阅读「更新日志」文件夹中最新一篇日志")
        btn_export_log.setToolTip("把最新一篇日志另存为副本")
        btn_open_log.setToolTip("打开「更新日志」文件夹")
        btn_view_log.clicked.connect(self._view_changelog)
        btn_export_log.clicked.connect(self._export_changelog)
        btn_open_log.clicked.connect(self._open_changelog_dir)
        log_row.addWidget(btn_view_log)
        log_row.addWidget(btn_export_log)
        log_row.addWidget(btn_open_log)
        log_row.addStretch()
        self._cur_layout.addLayout(log_row)

        self._layout.addStretch()

        # ===== 固定底部条：保存按钮固定在面板右下角 =====
        # 位于滚动区之外 → 不随设置内容滚动；全局所有分类（全部/桌宠/QQ/微信/其他）下始终可见。
        # 圆形按钮样式：正圆（半径=边长一半），只放图标，hover/悬停有 tooltip 说明
        _save_d = int(60 * S)          # 圆形按钮直径
        _save_r = int(_save_d / 2)     # 圆角 = 直径一半 → 正圆
        btn_save = QPushButton("💾")
        btn_save.setFixedSize(_save_d, _save_d)
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setToolTip("保存全部配置（不随滚动移动，始终固定在此）")
        btn_save.setStyleSheet(f"""
            QPushButton {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                stop:0 {Color4.name()}, stop:1 {Color3.name()});
                color: white; border: 2px solid rgba(255,255,255,0.65);
                font-size: {int(26*S)}px; border-radius: {_save_r}px; }}
            QPushButton:hover {{ border-color: white;
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                stop:0 {Color3.name()}, stop:1 {Color4.name()}); }}
            QPushButton:pressed {{ background: {Color2.name()}; }}
        """)
        btn_save.clicked.connect(self._save_config)
        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(int(30 * S), int(6 * S), int(30 * S), int(14 * S))
        bottom_row.addStretch(1)
        bottom_row.addWidget(btn_save)
        outer.addLayout(bottom_row)

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

    def _open_box(self, cats):
        """开启一个可被顶部分类标签显隐的分区框；后续 _add_*/_section 都进该框"""
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(int(14 * S))
        self._layout.addWidget(box)
        self._cat_entries.append((box, set(cats)))
        self._cur_layout = lay

    def _switch_cat(self, key):
        self._cat_filter = key
        for _k, _b in getattr(self, "_cat_btns", {}).items():
            _b.setChecked(_k == key)
        self._apply_cat_filter()

    def _apply_cat_filter(self):
        f = getattr(self, "_cat_filter", "all")
        for box, cats in getattr(self, "_cat_entries", []):
            box.setVisible(f in cats)

    def _auto_persist(self, key, value):
        """单项即时写盘（对话调节/自动登录等不需要点保存）"""
        try:
            p = self._config_path_resolve()
            cfg = {}
            if os.path.isfile(p):
                with open(p, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            cfg[key] = value
            tmp = p + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            os.replace(tmp, p)
        except Exception as e:
            print(f"[PCL] 自动保存失败 {key}: {e}")

    def _wire_autosave(self, kind, key):
        """把控件改动即时绑定到写盘（spin/slider/text）"""
        try:
            w = self._widgets.get(key)
            if w is None:
                return
            if kind == "spin":
                w.valueChanged.connect(lambda v, k=key: self._auto_persist(k, int(v)))
            elif kind == "slider":
                slider, options, _lbl = w
                slider.valueChanged.connect(
                    lambda v, o=options, k=key: self._auto_persist(k, o[v]))
            else:
                w.editingFinished.connect(
                    lambda k=key: self._auto_persist(k, w.text().strip()))
        except Exception as e:
            print(f"[PCL] 自动保存绑定失败 {key}: {e}")

    def _section(self, text, icon="🎯"):
        """设置页分区标题（左侧主题色条 + 半透明底，视觉上把功能归类）"""
        lbl = QLabel(f"  {icon} {text}")
        lbl.setFont(QFont("Microsoft YaHei", int(13 * S), QFont.Bold))
        lbl.setStyleSheet(
            f"color: {Color3.name()}; margin-top: {int(18*S)}px;"
            f"padding: {int(5*S)}px {int(10*S)}px;"
            f"background: rgba(255,255,255,120);"
            f"border-left: 4px solid {Color3.name()}; border-radius: {int(4*S)}px;")
        self._cur_layout.addWidget(lbl)
        return lbl

    def _add_text_input(self, key, label, default="", placeholder="", secure=False):
        lbl = QLabel(f"  {label}")
        lbl.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(12*S)}px;")
        self._cur_layout.addWidget(lbl)
        inp = QLineEdit()
        inp.setText(str(default))
        inp.setPlaceholderText(placeholder)
        if secure:
            inp.setEchoMode(QLineEdit.Password)
        inp.setStyleSheet(f"""
            QLineEdit {{ border: 1px solid {Gray5.name()}; padding: {int(6*S)}px;
                font-size: {int(12*S)}px; border-radius: {int(4*S)}px;
                background: rgba(255,255,255,190); font-family: 'Microsoft YaHei'; }}
            QLineEdit:focus {{ border: 1px solid {Color3.name()}; }}
        """)
        self._cur_layout.addWidget(inp)
        self._widgets[key] = inp

    def _block_wheel(self, obj):
        obj.setFocusPolicy(Qt.StrongFocus)
        obj.wheelEvent = lambda e: e.ignore()

    def _add_slider(self, key, label, options, default, hint=None):
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
        if hint:
            slider.setToolTip(hint)
            lbl.setToolTip(hint)
        slider.valueChanged.connect(lambda v: lbl.setText(f"{label}：{options[v]}"))
        row.addWidget(slider)
        row.addStretch()
        self._cur_layout.addLayout(row)
        self._widgets[key] = (slider, options, lbl)

    def _add_spin(self, key, label, min_val, max_val, default, hint=None):
        row = QHBoxLayout()
        lbl = QLabel(f"{label}")
        lbl.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(14*S)}px; min-width: 160px;")
        row.addWidget(lbl)
        spin = QSpinBox()
        spin.setRange(min_val, max_val); spin.setValue(default)
        spin.setFixedWidth(int(90 * S))
        spin.setStyleSheet(f"QSpinBox {{ border:1px solid {Gray5.name()}; padding:{int(4*S)}px; font-size:{int(13*S)}px; border-radius:{int(3*S)}px; }}")
        self._block_wheel(spin)
        if hint:
            spin.setToolTip(hint)
            lbl.setToolTip(hint)
        row.addWidget(spin); row.addStretch()
        self._cur_layout.addLayout(row)
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
        self._cur_layout.addLayout(row)
        self._widgets[key] = spin

    def _add_model_combo(self, key, label, options, default, hint=""):
        """可编辑模型名下选框（预设 + 自由输入）"""
        row = QHBoxLayout()
        lbl = QLabel(f"{label}")
        lbl.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(14*S)}px; min-width: 120px;")
        row.addWidget(lbl)
        combo = QComboBox()
        combo.setEditable(True)
        combo.addItems(options)
        combo.setCurrentText(str(default))
        combo.setFixedWidth(int(200 * S))
        combo.setStyleSheet(f"""
            QComboBox {{ border: 1px solid {Gray5.name()}; padding: {int(4*S)}px;
                font-size: {int(12*S)}px; border-radius: {int(4*S)}px;
                background: rgba(255,255,255,190); font-family: 'Microsoft YaHei'; }}
            QComboBox:focus {{ border: 1px solid {Color3.name()}; }}
            QComboBox QAbstractItemView {{ background: rgba(255,255,255,190); selection-background-color: {Color3.name()}; }}
        """)
        self._block_wheel(combo)
        if hint:
            combo.setToolTip(hint)
        row.addWidget(combo)
        row.addStretch()
        self._cur_layout.addLayout(row)
        self._widgets[key] = combo

    def _load_current_config(self):
        try:
            path = self._config_path_resolve()
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            self._set_if("user_name", cfg.get("user_name", ""))
            self._set_if("deepseek_api_key", cfg.get("APIKEY", {}).get("deepseek", ""))
            self._set_if("qwen_api_key", cfg.get("APIKEY", {}).get("qwen", ""))
            self._set_slider("model_type", cfg.get("model_type", "qwen"))
            self._set_if("short_model_name", cfg.get("short_model_name", "qwen-plus"))
            self._set_slider("tts_type", cfg.get("tts_type", "local"))
            self._set_slider("voice_synthesis_enable", cfg.get("voice_synthesis_enable", "true"))
            self._set_slider("portrait_auto_switch", cfg.get("portrait_auto_switch", "true"))
            self._set_slider("portrait", cfg.get("portrait", "b"))
            self._set_slider("screen_type", cfg.get("screen_type", "false"))
            self._set_slider("voice_trigger", cfg.get("voice_trigger", "false"))
            self._set_slider("live2d_enabled", cfg.get("live2d_enabled", "true"))
            self._set_slider("force_gpu_check", cfg.get("force_gpu_check", "false"))
            self._set_slider("longtext_enabled", cfg.get("longtext_enabled", "true"))
            self._set_slider("longtext_model", cfg.get("longtext_model", "deepseek"))
            self._set_if("longtext_model_name", cfg.get("longtext_model_name", "deepseek-v4-flash"))
            self._set_if("vision_model_name", cfg.get("vision_model_name", "qwen3-vl-plus"))
            self._set_slider("reasoning_level", cfg.get("reasoning_level", "off"))
            self._set_if("qq_owner_id", cfg.get("qq_owner_id", ""))
            # 额外主人白名单：数组/字符串 → 逗号分隔文本
            _masters_raw = cfg.get("qq_master_ids", [])
            if isinstance(_masters_raw, list):
                self._set_if("qq_master_ids_text", ", ".join(str(x) for x in _masters_raw))
            else:
                self._set_if("qq_master_ids_text", str(_masters_raw))
            self._set_slider("qq_enabled", cfg.get("qq_enabled", "false"))
            self._set_slider("qq_send_sticker", cfg.get("qq_send_sticker", "true"))
            self._set_slider("qq_send_voice", cfg.get("qq_send_voice", "false"))
            self._set_slider("qq_vision_enabled", cfg.get("qq_vision_enabled", "true"))
            self._set_slider("qq_allow_groups", cfg.get("qq_allow_groups", "true"))
            self._set_slider("qq_offline_enable", cfg.get("qq_offline_enable", "true"))
            self._set_slider("qq_private_enable", cfg.get("qq_private_enable", "true"))
            self._set_slider("qq_private_reply_stranger", cfg.get("qq_private_reply_stranger", "true"))
            self._set_slider("qq_private_reply_friend", cfg.get("qq_private_reply_friend", "true"))
            self._set_slider("qq_private_master_only", cfg.get("qq_private_master_only", "false"))
            self._set_slider("qq_auto_offline_enable", cfg.get("qq_auto_offline_enable", "false"))
            self._set_slider("qq_lively_enable", cfg.get("qq_lively_enable", "false"))
            self._set_slider("wechat_enabled", cfg.get("wechat_enabled", "false"))
            self._set_slider("wechat_send_voice", cfg.get("wechat_send_voice", "false"))
            self._set_if("wechat_owner_id", cfg.get("wechat_owner_id", ""))
            for k in ["screen_interval", "screen_index", "idle_thinking_minutes", "idle_away_minutes",
                      "qq_auto_offline_minutes", "qq_lively_interval",
                      "qq_max_reply_chars", "qq_max_replies_per_conversation"]:
                self._set_if(k, cfg.get(k, 0))
            self._set_if("DEFAULT_PORTRAIT_SCREEN_RATIO", cfg.get("DEFAULT_PORTRAIT_SCREEN_RATIO", 0.8))
        except Exception:
            pass

    def _set_if(self, key, val):
        w = self._widgets.get(key)
        if isinstance(w, QLineEdit): w.setText(str(val))
        elif isinstance(w, QComboBox): w.setCurrentText(str(val))
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
            cfg["short_model_name"] = self._get_combo("short_model_name")
            cfg["tts_type"] = self._get_slider("tts_type")
            cfg["portrait"] = self._get_slider("portrait")
            cfg["screen_type"] = self._get_slider("screen_type")
            cfg["voice_trigger"] = self._get_slider("voice_trigger")
            cfg["voice_synthesis_enable"] = self._get_slider("voice_synthesis_enable")
            cfg["portrait_auto_switch"] = self._get_slider("portrait_auto_switch")
            cfg["live2d_enabled"] = self._get_slider("live2d_enabled")
            cfg["force_gpu_check"] = self._get_slider("force_gpu_check")
            cfg["longtext_enabled"] = self._get_slider("longtext_enabled")
            cfg["longtext_model"] = self._get_slider("longtext_model")
            cfg["longtext_model_name"] = self._get_combo("longtext_model_name")
            cfg["vision_model_name"] = self._get_combo("vision_model_name")
            cfg["reasoning_level"] = self._get_slider("reasoning_level")
            cfg["qq_owner_id"] = self._get_text("qq_owner_id")
            # 额外主人白名单：解析逗号/空格分隔数字，去重，最多 4 个（含主主人总计 ≤5）
            _masters = []
            import re as _re
            for _part in _re.split(r"[,，;；\s]+", self._get_text("qq_master_ids_text")):
                _p = _part.strip()
                if _p.isdigit() and _p not in _masters:
                    _masters.append(_p)
            cfg["qq_master_ids"] = _masters[:4]
            cfg["qq_enabled"] = self._get_slider("qq_enabled")
            cfg["qq_send_sticker"] = self._get_slider("qq_send_sticker")
            cfg["qq_send_voice"] = self._get_slider("qq_send_voice")
            cfg["qq_vision_enabled"] = self._get_slider("qq_vision_enabled")
            cfg["qq_allow_groups"] = self._get_slider("qq_allow_groups")
            cfg["qq_offline_enable"] = self._get_slider("qq_offline_enable")
            cfg["qq_private_enable"] = self._get_slider("qq_private_enable")
            cfg["qq_private_reply_stranger"] = self._get_slider("qq_private_reply_stranger")
            cfg["qq_private_reply_friend"] = self._get_slider("qq_private_reply_friend")
            cfg["qq_private_master_only"] = self._get_slider("qq_private_master_only")
            cfg["qq_auto_offline_enable"] = self._get_slider("qq_auto_offline_enable")
            cfg["qq_lively_enable"] = self._get_slider("qq_lively_enable")
            cfg["wechat_enabled"] = self._get_slider("wechat_enabled")
            cfg["wechat_send_voice"] = self._get_slider("wechat_send_voice")
            cfg["wechat_owner_id"] = self._get_text("wechat_owner_id")

            for k in ["screen_interval", "screen_index", "idle_thinking_minutes", "idle_away_minutes",
                      "qq_auto_offline_minutes", "qq_lively_interval",
                      "qq_max_reply_chars", "qq_max_replies_per_conversation"]:
                w = self._widgets.get(k)
                if isinstance(w, QSpinBox): cfg[k] = w.value()
            w = self._widgets.get("DEFAULT_PORTRAIT_SCREEN_RATIO")
            if isinstance(w, QDoubleSpinBox): cfg["DEFAULT_PORTRAIT_SCREEN_RATIO"] = w.value()

            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)

            # 重启桌宠
            self._restart_pet()
            show_save_toast(True)
        except Exception as e:
            print(f"[PCL] 保存配置失败: {e}")
            show_save_toast(False)

    def _get_text(self, key):
        w = self._widgets.get(key)
        return w.text().strip() if isinstance(w, QLineEdit) else ""

    def _get_combo(self, key):
        w = self._widgets.get(key)
        return w.currentText().strip() if isinstance(w, QComboBox) else ""

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

    # ---- 更新日志（查看 / 导出 / 打开目录）----
    def _changelog_dir(self) -> str:
        return os.path.join(_app_base_dir(), "更新日志")

    def _latest_log_file(self, folder: str):
        """返回文件夹中最新的 md/txt 日志路径；无则 None"""
        try:
            cands = [f for f in os.listdir(folder)
                     if f.lower().endswith((".md", ".txt"))]
        except Exception:
            return None
        if not cands:
            return None
        cands.sort(key=lambda f: os.path.getmtime(os.path.join(folder, f)), reverse=True)
        return os.path.join(folder, cands[0])

    def _view_changelog(self):
        folder = self._changelog_dir()
        newest = self._latest_log_file(folder)
        if not newest:
            QMessageBox.information(self, "更新日志", f"更新日志文件夹为空：\n{folder}")
            return
        try:
            with open(newest, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception as e:
            QMessageBox.warning(self, "读取失败", str(e))
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f"📜 更新日志 — {os.path.basename(newest)}")
        dlg.resize(int(780 * S), int(560 * S))
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(int(14 * S), int(12 * S), int(14 * S), int(12 * S))
        lay.setSpacing(int(10 * S))
        txt = QPlainTextEdit()
        txt.setReadOnly(True)
        txt.setPlainText(text)
        txt.setStyleSheet(
            f"QPlainTextEdit {{ background: #fbfbfb; color: #333333; border: 1px solid {Gray5.name()};"
            f" border-radius: {int(6*S)}px; font-family: 'Microsoft YaHei'; font-size: {int(13*S)}px; }}")
        lay.addWidget(txt)
        btn_close = QPushButton("  关闭")
        btn_close.setStyleSheet(f"""
            QPushButton {{ background: {Color3.name()}; color: white; border: none;
                padding: {int(7*S)}px {int(20*S)}px; font-size: {int(13*S)}px;
                border-radius: {btn_radius()}px; font-family: 'Microsoft YaHei'; }}
            QPushButton:hover {{ background: {Color4.name()}; }}
        """)
        btn_close.clicked.connect(dlg.accept)
        lay.addWidget(btn_close, 0, Qt.AlignRight)
        dlg.exec_()

    def _export_changelog(self):
        folder = self._changelog_dir()
        newest = self._latest_log_file(folder)
        if not newest:
            QMessageBox.information(self, "导出日志", f"更新日志文件夹为空：\n{folder}")
            return
        try:
            with open(newest, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception as e:
            QMessageBox.warning(self, "读取失败", str(e))
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出更新日志",
                                              os.path.join(folder, os.path.basename(newest)),
                                              "Markdown (*.md);;文本文件 (*.txt);;所有文件 (*.*)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            QMessageBox.information(self, "导出成功", f"已导出到：\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "导出失败", str(e))

    def _open_changelog_dir(self):
        folder = self._changelog_dir()
        try:
            os.makedirs(folder, exist_ok=True)
            os.startfile(folder)  # noqa
        except Exception as e:
            QMessageBox.warning(self, "打开失败", str(e))


# ==================== 人脸管理面板 ====================

class PCLFaceManager(QScrollArea):
    """人脸库管理（主人/其他人照片添加与删除）"""

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
                border-radius: {btn_radius()}px; font-family: 'Microsoft YaHei'; }}
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
                border-radius: {btn_radius()}px; font-family: 'Microsoft YaHei'; }}
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
    """多角色记忆管理：查看/预览/清除/备份各角色记忆 + QQ 离线补拉状态 + 微信登录入口"""

    # 微信「重新扫码登录」请求（主窗口统一执行：停进程→清凭据→重启弹码）
    wechat_relogin_requested = pyqtSignal()

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
        # ⚠ 默认选中「当前活动角色」：以前固定停在列表第一项（如 murasame），
        #   而记忆是按角色分目录存的 → 切到别的角色时看着像"一条记录都没有"。
        try:
            from pets.pet_registry import get_active_pet_id
            _act = str(get_active_pet_id() or "")
            if _act:
                _i = self._pet_combo.findData(_act)
                if _i >= 0:
                    self._pet_combo.setCurrentIndex(_i)
        except Exception:
            pass
        self._pet_combo.currentIndexChanged.connect(lambda _: self._refresh())
        # 每次显示本页都校正一次（切角色后进来能看到对应的记忆）
        try:
            self._sync_combo_to_active = True
        except Exception:
            pass
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
            f"border: 1px solid {Color5.name()}; border-radius: {btn_radius()}px; "
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

        # ===== 微信 ClawBot 登录卡片 =====
        self._build_wechat_card()

        self._layout.addStretch()
        self._refresh()

    # ===== 微信登录卡片（换绑/登录异常时在这里重新扫码）=====
    def _build_wechat_card(self):
        card = QWidget()
        card.setStyleSheet(f"""
            QWidget#wxCard {{ background: rgba({Color8.red()},{Color8.green()},{Color8.blue()},110);
                border: 1px solid {Color5.name()}; border-radius: {int(10*S)}px; }}
        """)
        card.setObjectName("wxCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(int(16 * S), int(12 * S), int(16 * S), int(14 * S))
        lay.setSpacing(int(8 * S))

        head = QHBoxLayout()
        head_title = QLabel("💬 微信 ClawBot")
        head_title.setFont(QFont("Microsoft YaHei", int(14 * S), QFont.Bold))
        head_title.setStyleSheet(f"color: {Color1.name()}; border: none; background: transparent;")
        head.addWidget(head_title)
        head.addStretch()
        # 状态徽标
        self._wx_status = QLabel("")
        self._wx_status.setStyleSheet(
            f"color: {Gray2.name()}; font-size: {int(12*S)}px; border: none; background: transparent;")
        head.addWidget(self._wx_status)
        lay.addLayout(head)

        tip = QLabel("机器人以你的微信身份收发消息。换绑微信号 / 登录异常 / token 失效时，"
                     "点击下方按钮清除本地登录态并重新扫码。")
        tip.setWordWrap(True)
        tip.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(12*S)}px; border: none; background: transparent;")
        lay.addWidget(tip)

        row = QHBoxLayout()
        self._wx_detail = QLabel("")
        self._wx_detail.setStyleSheet(f"color: {Color1.name()}; font-size: {int(12*S)}px; border: none; background: transparent;")
        row.addWidget(self._wx_detail, 1)
        btn_relogin = QPushButton("  🔄 重新扫码登录")
        btn_relogin.setStyleSheet(self._btn_style("#2f6fbf"))
        btn_relogin.setToolTip("清除本地登录凭据并重新扫码（换绑/换手机/登录异常时使用）")
        btn_relogin.clicked.connect(lambda: self.wechat_relogin_requested.emit())
        row.addWidget(btn_relogin, 0, Qt.AlignBottom)
        lay.addLayout(row)

        self._layout.addWidget(card)
        self._refresh_wx_card()

    def _wx_cred_state(self):
        """返回 (是否已登录, bot_id/user_id 详情, 是否启用)"""
        enabled = False
        try:
            from tool.config import get_config
            cfg = get_config("./config.json")
            enabled = str(cfg.get("wechat_enabled", "false")).lower() == "true"
        except Exception:
            pass
        creds = None
        try:
            from wechat.ilink_client import load_credentials
            creds = load_credentials()
        except Exception:
            creds = None
        return enabled, creds

    def _refresh_wx_card(self):
        try:
            enabled, creds = self._wx_cred_state()
            if not enabled:
                self._wx_status.setText("未启用")
                self._wx_detail.setText("config.json 中 wechat_enabled=false，微信功能未开启。")
                return
            if creds:
                bot = creds.get("bot_id") or ""
                user = creds.get("user_id") or ""
                self._wx_status.setText("● 已登录")
                self._wx_status.setStyleSheet(
                    f"color: {THEME_COLORS['green']['btn_start']}; font-size: {int(12*S)}px;"
                    f" border: none; background: transparent;")
                detail = f"bot: {bot}" if bot else ""
                if user:
                    detail = (detail + "  ·  " if detail else "") + f"微信: {user}"
                self._wx_detail.setText(detail or "本地已保存登录凭据")
            else:
                self._wx_status.setText("○ 未登录")
                self._wx_status.setStyleSheet(
                    f"color: {Gray2.name()}; font-size: {int(12*S)}px; border: none; background: transparent;")
                self._wx_detail.setText("未找到登录凭据——点击右侧按钮开始扫码登录。")
        except Exception:
            pass

    def showEvent(self, event):
        """每次切到记忆页：刷新微信登录状态 + 把角色下拉校正到「当前活动角色」"""
        try:
            from pets.pet_registry import get_active_pet_id
            act = str(get_active_pet_id() or "")
            if act:
                i = self._pet_combo.findData(act)
                if i >= 0 and i != self._pet_combo.currentIndex():
                    self._pet_combo.setCurrentIndex(i)   # 会触发 _refresh()
        except Exception:
            pass
        try:
            self._refresh_wx_card()
        except Exception:
            pass
        super().showEvent(event)

    @staticmethod
    def _btn_style(bg):
        return f"""
            QPushButton {{ background: {bg}; color: white; border: none;
                padding: {int(8*S)}px {int(16*S)}px; font-size: {int(13*S)}px;
                border-radius: {btn_radius()}px; font-family: 'Microsoft YaHei'; }}
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



class PCLPetManager(QScrollArea):
    """多桌宠管理面板：查看/设为活动/添加/删除/打开文件夹"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.NoFrame)
        self.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        container = QWidget()
        self._layout = QVBoxLayout(container)
        # 桌宠页：左右贴边与目录条同宽
        self._layout.setContentsMargins(0, int(20 * S), 0, int(20 * S))
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

        # 添加桌宠按钮 → 打开分步引导向导
        btn_add = QPushButton("  + 添加新桌宠（跟着引导一步步来）")
        btn_add.setStyleSheet(f"""
            QPushButton {{ background: {Color3.name()}; color: white; border: none;
                padding: {int(8*S)}px {int(16*S)}px; font-size: {int(13*S)}px;
                border-radius: {btn_radius()}px; font-family: 'Microsoft YaHei'; }}
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
        # 卡片底色用半透明（壁纸能透出来）—— 从源头避免"遮挡背景"
        _c8 = Color8
        _card_bg = f"rgba({_c8.red()},{_c8.green()},{_c8.blue()},90)"
        card.setStyleSheet(f"""
            QWidget {{ background: {_card_bg}; border: 1px solid {Color5.name()};
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

        # ⚙ 设置：打开桌宠向导（类型/立绘/Live2D/语音/人设 都能改）
        btn_settings = QPushButton("⚙ 设置")
        btn_settings.setStyleSheet(self._btn_style("#3f8fd8"))
        btn_settings.clicked.connect(lambda checked, pid=p["id"]: self._open_pet_wizard(pid))
        btn_row.addWidget(btn_settings)
        # 立绘工坊：换服装/表情/装饰，预览并保存为该角色的默认立绘
        btn_portrait = QPushButton("🎨 立绘工坊")
        btn_portrait.setStyleSheet(self._btn_style("#c8506e"))
        btn_portrait.clicked.connect(
            lambda checked, pid=p["id"], nm=p.get("name", ""): self._open_portrait_studio(pid, nm))
        btn_row.addWidget(btn_portrait)

        btn_del = QPushButton("🗑 删除")
        btn_del.setStyleSheet(self._btn_style("#e03030"))
        btn_del.clicked.connect(lambda checked, pid=p["id"], nm=p.get("name",""): self._delete_pet(pid, nm))
        btn_row.addWidget(btn_del)

        btn_row.addStretch()
        v.addLayout(btn_row)

        return card

    def _open_pet_wizard(self, pet_id, pet_name=""):
        """打开桌宠设置向导（编辑模式，可直接改 类型/立绘/Live2D/语音/人设）"""
        try:
            from .pet_wizard import PCLPetWizard
            # ⚠ 同一个角色只保留一个设置窗口：以前每点一次就新开一个（越点越多、
            #   互相盖住 → 分不清哪个能点）。已存在就置前复用。
            _win = self.window()
            cache = getattr(_win, "_pet_wizards", None)
            if cache is None:
                cache = {}
                try:
                    _win._pet_wizards = cache
                except Exception:
                    pass
            dlg = cache.get(pet_id)
            if dlg is not None:
                try:
                    dlg.isHidden()          # C++ 对象还活着吗
                except Exception:
                    dlg = None
                if dlg is not None and not dlg.isVisible():
                    dlg.reload_for_pet(pet_id) if hasattr(dlg, "reload_for_pet") else None
            else:
                dlg = None
            if dlg is None:
                dlg = PCLPetWizard(pet_id, _win)
                dlg.saved.connect(lambda _pid: self._refresh())
                try:
                    cache[pet_id] = dlg
                except Exception:
                    pass
            # ⚠ 用 show()（非模态）而不是 exec_()：模态会把 Live2D 预览窗口一起锁住
            #   （表现：预览窗口拖不动、关不上，必须先关设置）
            # ⚠ 置顶：启动器窗口较大，普通对话框容易被它盖住 → 「看到的是启动器，点的是设置」
            try:
                dlg.setWindowFlag(Qt.WindowStaysOnTopHint, True)
            except Exception:
                pass
            dlg.show(); dlg.raise_(); dlg.activateWindow()
            try:
                from PyQt5.QtCore import QTimer as _QT
                _QT.singleShot(160, lambda: (dlg.raise_(), dlg.activateWindow()))
            except Exception:
                pass
            self._refresh()
        except Exception as e:
            import traceback
            from PyQt5.QtWidgets import QMessageBox
            print(f"[PCL] ⚠ 打开桌宠设置失败: {e}\n{traceback.format_exc()[:500]}")
            QMessageBox.warning(self, "桌宠设置", f"打开设置失败：{e}")

    def _open_portrait_studio(self, pet_id, pet_name=""):
        """打开立绘工坊（按卡片角色编辑自己的立绘素材）"""
        from PyQt5.QtCore import Qt as _Qt
        globals().setdefault("Qt", _Qt)

        def _dbg(msg):
            try:
                import time as _t
                base = _app_base_dir()
                with open(os.path.join(base, "tmp", "pcl_debug.log"), "a", encoding="utf-8") as f:
                    f.write(f"[{_t.strftime('%m-%d %H:%M:%S')}] [立绘工坊] {msg}\n")
            except Exception:
                pass
        try:
            from pets.pet_registry import get_active_pet_id
            active = get_active_pet_id()
            _dbg(f"点击 pid={pet_id} active={active}")
            # 不再强制「先设为活动」：直接按这张卡片对应的角色打开工坊（各自独立编辑）
            if pet_id and active and pet_id != active:
                print(f"[PCL] 立绘工坊：按卡片角色 {pet_id} 打开（当前活动 {active}）")
            from .portrait_studio import PortraitStudio
            _dbg("import PortraitStudio OK")
            # 工坊实例挂在外壳窗口上（换肤会重建本页 → 重建后仍是同一个工坊，不会开出第二个）
            _win = self.window()
            st = getattr(_win, "_portrait_studio", None)
            if st is None:
                # ⚠ 用「无父窗口」构造：作为父窗口的子对话框时会被启动器盖住/不显示
                #   （Live2D 预览窗口就是这么做的、显示正常）
                st = PortraitStudio(None, pet_id=pet_id)
                # ⚠ 置顶 + 独立顶层窗口：启动器是自带背景的不透明窗口，普通对话框很容易
                #   被它盖住 → 用户「看到的是启动器的内容，可点的是下面的工坊」，
                #   表现就是「显示的位置和实际点击的位置不一样」。预览窗口同款处理。
                st.setWindowFlag(Qt.Window, True)
                st.setWindowFlag(Qt.WindowStaysOnTopHint, True)
                _win._portrait_studio = st
                _dbg("构造 PortraitStudio OK（顶层窗口）")
            else:
                # ⚠ 关键：复用窗口时必须「重新加载这个角色的素材」，否则界面还停在上一个
                #   角色的立绘/Live2D（反馈：点别人的工坊显示的是活动角色的立绘）。
                try:
                    st.reload_for_pet(pet_id)
                except Exception as _e:
                    print(f"[PCL] ⚠ 切换工坊角色失败: {_e}")
                    try:
                        st._pet_id = pet_id
                        st._loaded_pet = None
                    except Exception:
                        pass
            st.show()
            st.raise_()
            st.activateWindow()
            try:
                from PyQt5.QtWidgets import QApplication as _QA
                print(f"[PCL] 立绘工坊可见={st.isVisible()} 尺寸={st.width()}x{st.height()} "
                      f"| 前台窗口={(_QA.activeWindow().__class__.__name__ if _QA.activeWindow() else '无')}")
            except Exception:
                pass
            # 再补两次置前（启动器是置顶/亚克力窗口时容易把它盖住 → 看着像"打不开"）
            try:
                from PyQt5.QtCore import QTimer as _QT
                _QT.singleShot(150, lambda: (st.raise_(), st.activateWindow()))
                _QT.singleShot(600, lambda: (st.raise_(), st.activateWindow()))
            except Exception:
                pass
            _dbg("show OK")
            print(f"[PCL] 🎨 立绘工坊已打开（角色: {active or '未知'}）")
        except Exception as e:
            import traceback
            _dbg("异常: " + repr(e) + "\n" + traceback.format_exc())
            print(f"[PCL] ⚠ 打开立绘工坊失败: {e}")

    @staticmethod
    def _btn_style(bg):
        return f"""
            QPushButton {{ background: {bg}; color: white; border: none;
                padding: {int(5*S)}px {int(12*S)}px; font-size: {int(11*S)}px;
                border-radius: {int(5*S)}px; font-family: 'Microsoft YaHei'; }}
            QPushButton:hover {{ opacity: 0.85; }}
        """

    def _set_active(self, pet_id):
        from pets.pet_registry import set_active_pet_id, get_active_pet_id
        ok = set_active_pet_id(pet_id)
        print(f"[PCL] 设为活动桌宠 {pet_id}: {'成功' if ok else '失败'}")
        if ok:
            # 卡片状态 + 活动标记刷新（以前点了看不到变化，像没生效）
            try:
                self._refresh()
            except Exception:
                pass
            try:
                # 刷新后重新透明化，避免重建的卡片把启动器背景挡住
                from .silicon_window import _make_transparent
                w = self.window()
                pg = getattr(w, "pages", {}).get("pets")
                if pg is not None:
                    _make_transparent(pg)
            except Exception as _e:
                print(f"[PCL] ⚠ 设为活动后透明化失败: {_e}")
            try:
                from .widgets import show_save_toast as _toast
                _toast(self, f"已把「{pet_id}」设为活动桌宠（重启桌宠后生效）")
            except Exception:
                pass
            print(f"[PCL] 当前活动桌宠: {get_active_pet_id()}")
        else:
            try:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(self, "设为活动", "设置失败：角色不存在或配置不可写")
            except Exception:
                pass

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
        """打开「添加新桌宠」引导向导（分步：类型 → 立绘/Live2D → 语音 → 人设）"""
        try:
            from .pet_wizard import PCLPetWizard
            dlg = PCLPetWizard(None, self.window())
            dlg.saved.connect(lambda _pid: self._refresh())
            # 非模态：模态会把 Live2D 预览窗口一起锁住（拖不动/关不上）
            dlg.show(); dlg.raise_(); dlg.activateWindow()
            return
        except Exception as e:
            import traceback
            print(f"[PCL] ⚠ 打开桌宠向导失败: {e}\n{traceback.format_exc()[:500]}")
            # 兜底：仍然允许用最简方式创建
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


class PCLPromptEditor(QWidget):
    """提示词编辑器：查看/编辑各角色短文本与长文本人设"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        # 提示词页：左右贴边与顶部目录条同宽
        layout.setContentsMargins(0, int(16 * S), 0, int(16 * S))
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
                    border-radius: {btn_radius()}px; font-family: 'Microsoft YaHei'; }}
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

def show_save_toast(ok: bool, text: str = ""):
    """屏幕中央弹出"保存成功/保存失败"提示，约 2 秒自动消失（健壮版）"""
    try:
        from PyQt5.QtWidgets import QApplication, QLabel
        from PyQt5.QtCore import Qt, QTimer
        app = QApplication.instance()
        if app is None:
            return
        win = app.activeWindow()
        scr = (win.screen() if win and win.screen() else app.primaryScreen())
        if scr is None:
            scr = app.primaryScreen()
        geo = scr.availableGeometry()
        parent = win if win is not None else None
        lab = QLabel(parent)
        if parent is None:
            lab.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                               | Qt.Tool | Qt.WindowDoesNotAcceptFocus)
        lab.setAttribute(Qt.WA_TranslucentBackground)
        from PyQt5.QtGui import QColor
        from PyQt5.QtWidgets import QGraphicsDropShadowEffect
        bg = "#2e7d32" if ok else "#c62828"   # 不透明深底，白字更清晰
        lab.setStyleSheet(f"background:{bg};color:#ffffff;border-radius:12px;"
                          "padding:14px 32px;font-size:18px;font-weight:bold;"
                          "font-family:'Microsoft YaHei';")
        lab.setText(text or ("✅ 保存成功" if ok else "❌ 保存失败"))
        # 黑色投影，模拟描边，白字在任何背景下都清楚
        _sh = QGraphicsDropShadowEffect(lab)
        _sh.setBlurRadius(1)
        _sh.setOffset(1, 1)
        _sh.setColor(QColor(0, 0, 0, 230))
        lab.setGraphicsEffect(_sh)
        lab.adjustSize()
        lab.move(geo.center().x() - lab.width() // 2,
                 geo.center().y() - lab.height() // 2)
        if parent is None:
            lab.show()
            lab.raise_()
            lab.activateWindow()
        else:
            # 子控件式浮层：父窗内居中置顶
            lab.setStyleSheet(lab.styleSheet() +
                              f"background:{bg};")
            lab.move((parent.width() - lab.width()) // 2,
                     (parent.height() - lab.height()) // 2)
            lab.show()
            lab.raise_()
        # 保持引用直至关闭
        _ref = {"lab": lab}
        QTimer.singleShot(2000, lambda: (_ref["lab"].close()))
        QTimer.singleShot(2600, _ref["lab"].deleteLater)
        print("[PCL] Toast 已显示:", "保存成功" if ok else "保存失败")
    except Exception as e:
        print(f"[PCL] Toast 显示失败: {e}")

