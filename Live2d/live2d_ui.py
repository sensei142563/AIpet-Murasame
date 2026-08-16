"""
Live2D 渲染窗口
- 独立的 QOpenGLWidget 窗口，透明背景
- 使用 live2d.v3 渲染丛雨的 Live2D 模型
- 支持呼吸、随机眨眼、头发飘动、口型同步、物理模拟、点击触发动作和表情
- 表情系统：动态扫描模型目录 exp/ 下的 .exp3.json（不再硬编码 exp1~exp7）
- 与 Murasame(QLabel) 桌宠窗口配合使用
"""
import os
import sys
import time
import json
import struct
import math
import random
import wave

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtWidgets import QOpenGLWidget

# === 提前加载 DLL 目录 ===
_dll_dir = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(_dll_dir):
    os.environ.setdefault("PATH", "")
    os.environ["PATH"] = _dll_dir + os.pathsep + os.environ["PATH"]
    try:
        os.add_dll_directory(_dll_dir)
    except Exception:
        pass

_live2d_imported = False


def _ensure_live2d():
    global _live2d_imported
    if not _live2d_imported:
        import live2d.v3 as l2d
        l2d.init()
        _live2d_imported = True


# ============== 表情管理器 ==============
# 情感名 → exp3 文件名组合（丛雨的 exp1.exp3 ~ exp7.exp3）
# 新角色（如 noir）exp 是中文/英文名，可直接用 exp 文件名 set_emotion，
# 不必匹配这里的 COMBO 表。
COMBO_CONFIG = {
    "微笑": ["exp1.exp3.json", "exp6.exp3.json"],
    "高兴": ["exp1.exp3.json", "exp6.exp3.json"],
    "平静": ["exp1.exp3.json"],
    "友好": ["exp1.exp3.json"],
    "惊讶": ["exp5.exp3.json"],
    "好奇": ["exp5.exp3.json"],
    "可爱": ["exp6.exp3.json"],
    "害羞": ["exp6.exp3.json", "exp1.exp3.json"],
    "脸红": ["exp6.exp3.json"],
    "难过": ["exp2.exp3.json"],
    "生气": ["exp2.exp3.json", "exp4.exp3.json"],
    "阴沉": ["exp4.exp3.json", "exp3.exp3.json"],
    "疑惑": ["exp2.exp3.json"],
    "认真": ["exp2.exp3.json"],
    "睡觉": ["exp7.exp3.json"],
}


class EmotionManager:
    def __init__(self, model, exp_dir, emotion_map=None):
        self.model = model
        self.exp_dir = exp_dir
        self.emotion_map = emotion_map or {}   # 角色级映射：情绪 → [exp3 文件名]（阶段 E）
        self.current_combo = []
        self.exp_names = self._scan_expressions()

    def _scan_expressions(self):
        """动态扫描模型目录 exp/ 下的 .exp3.json，返回文件名列表（排序）"""
        names = []
        if os.path.isdir(self.exp_dir):
            for f in sorted(os.listdir(self.exp_dir)):
                if f.endswith(".exp3.json"):
                    names.append(f)
        return names

    def _apply_exp(self, fname: str):
        """应用单个 exp3 预设（按文件名；model3.json 未登记表情时用 LoadExtraExpression 运行时注册）"""
        exp_path = os.path.join(self.exp_dir, fname)
        if not os.path.exists(exp_path):
            return
        try:
            self.model.LoadExtraExpression(fname, exp_path)
            self.model.SetExpression(fname)
        except Exception:
            pass

    def set_emotion(self, name: str):
        """
        切换到指定表情：
        1. 若 name 是 exp 文件名（如 "生气.exp3.json"、"tears.exp3.json"）→ 直接应用
        2. 角色级情绪映射（pet.json model.emotions）
        3. 内置 COMBO_CONFIG 情感名映射（丛雨）
        返回是否发生变化。
        """
        # 1) 直接文件名（新角色 / 任意 exp 文件）
        if name in self.exp_names:
            combo = [name]
        # 2) 角色情绪映射
        elif name in self.emotion_map:
            combo = list(self.emotion_map[name] or [])
        # 3) 内置映射
        else:
            combo = COMBO_CONFIG.get(name, [])

        if combo == self.current_combo:
            return False

        # 重置现有表情
        try:
            self.model.ResetExpressions()
        except Exception:
            pass

        for fname in combo:
            self._apply_exp(fname)

        self.current_combo = combo
        return True

    def all_expressions(self):
        """返回所有可用表情：COMBO 情感名 + exp 文件名"""
        return sorted(set(COMBO_CONFIG.keys()) | set(self.exp_names))


# ============== Live2D 渲染窗口 ==============
class Live2DWidget(QOpenGLWidget):
    # 信号：通知 pet 窗口操作
    trigger_text = pyqtSignal(str)                   # 点击触发文本
    trigger_touch_head = pyqtSignal()                 # 摸头触发
    trigger_input_mode = pyqtSignal()                 # 点击下半身 → 输入模式
    trigger_drag_move = pyqtSignal(int, int)          # 中键拖拽 → (dx, dy)
    interacted = pyqtSignal()                         # 任何鼠标交互（重排文字层 z 序用）

    def __init__(self, parent=None, model_dir=None, model_json=None,
                 window_ratio=0.67, model_scale=1.0, offset_x=0.0, offset_y=0.0,
                 head_top=0.0, head_bottom=0.18, talk_top=0.5, talk_bottom=1.0,
                 edge_margin_x=0.12, emotion_map=None, motion_map=None,
                 default_expression="", eye_open_max=1.0, mouth_open_max=1.0,
                 window_height_ratio=0.85):
        super().__init__(parent)
        self.model_dir = model_dir or os.path.dirname(os.path.abspath(__file__))
        # 优先使用调用方传入的 model_json（pet.json 钉死 / 注册中心校验后的），
        # 否则动态查找模型目录下任意 .model3.json（不硬编码 Murasame.model3.json）
        self.model_json_path = model_json or self._find_model_json()

        # ===== 按角色显示/交互配置（阶段 E，来自 get_live2d_display）=====
        self.window_ratio = window_ratio
        self.window_height_ratio = window_height_ratio  # 窗口高度占屏比（F2/F3 调，消除上下空白画布）
        self.model_scale = model_scale
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.head_top = head_top
        self.head_bottom = head_bottom
        self.talk_top = talk_top
        self.talk_bottom = talk_bottom
        self.edge_margin_x = edge_margin_x
        # 情绪→表情/动作（阶段 E）
        self.emotion_map = emotion_map or {}
        self.motion_map = motion_map or {}
        self.default_expression = default_expression
        # 参数输出范围（从 vtube.json 提取，修复 0~1 硬编码）
        self.eye_open_max = eye_open_max
        self.mouth_open_max = mouth_open_max
        # 调参参考线（F9 开关：显示画布边界+中线，便于对齐模型与窗口边距）
        self.show_tuning_guides = False

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAutoFillBackground(False)

        self.model = None
        self._render_ready = False
        self._failed = False
        self.is_speaking = False
        self.emotion_manager = None
        self.mouth_open = 0.0
        # 情绪动作状态（阶段 E 修复：动作播放期间让位给 motion，播完恢复默认表情）
        self._motion_playing = False
        self._motion_hold = False        # 句子播放期间保持动作（播完定格姿态，直到收尾）
        self._motion_key = None          # 当前情绪动作 (组, 序号)
        self._emotion_motions = {}   # 动作文件名 -> ("emotion", 组内序号)
        # 定格姿态：动作播完句内保持时，快照姿态参数持续施加（前倾就保持前倾），
        # 收尾时按权重衰减释放回默认姿态。
        self._POSE_PARAMS = (
            "ParamAngleX", "ParamAngleY", "ParamAngleZ",
            "ParamBodyAngleX", "ParamBodyAngleY", "ParamBodyAngleZ",
        )
        self._pose_snapshot = {}         # 播放中的姿态快照
        self._frozen_params = {}         # 定格中：参数名 -> (值, 权重)
        self._frozen_releasing = False
        self._pose_frozen_flag = False   # 本句是否已定格（防每帧重复定格+刷日志）

        # 自然动作状态
        self._breath_time = 0.0
        self._last_blink_time = time.time()
        self._blinking = False
        self._blink_start_time = 0.0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)
        self.timer.setInterval(16)

        self.setMouseTracking(True)
        self._mouse_drag_offset = None
        self._touch_head = False
        self._head_press_x = None

    def _find_model_json(self):
        """在 model_dir 下查找 .model3.json（优先 Murasame，其次任意）"""
        if not os.path.isdir(self.model_dir):
            return os.path.join(self.model_dir, "Murasame.model3.json")
        # 优先 Murasame
        murasame = os.path.join(self.model_dir, "Murasame.model3.json")
        if os.path.exists(murasame):
            return murasame
        # 否则任意 .model3.json
        for f in sorted(os.listdir(self.model_dir)):
            if f.endswith(".model3.json"):
                return os.path.join(self.model_dir, f)
        return murasame

    def initializeGL(self):
        if self._failed:
            return
        try:
            _ensure_live2d()
            from OpenGL.GL import (
                glEnable, GL_BLEND, GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA,
                glBlendFunc, glClearColor, glClear, GL_COLOR_BUFFER_BIT
            )
            import live2d.v3 as l2d

            l2d.glInit()
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            glClearColor(0, 0, 0, 0)

            model_path = os.path.normpath(self.model_json_path).replace("\\", "/")
            if os.path.exists(model_path):
                self.model = l2d.LAppModel()
                try:
                    self.model.LoadModelJson(model_path)
                    # ===== 按角色显示调整（修复半身模型偏小/头顶鞋子被裁）=====
                    if self.model_scale != 1.0 or self.offset_x != 0.0 or self.offset_y != 0.0:
                        try:
                            self.model.SetScale(self.model_scale)
                            self.model.SetOffset(self.offset_x, self.offset_y)
                            print(f"[Live2D] 应用显示调整 scale={self.model_scale} offset=({self.offset_x},{self.offset_y})")
                        except Exception as _ex:
                            print(f"[Live2D] 应用显示调整失败: {_ex}")
                    exp_dir = os.path.join(self.model_dir, "exp")
                    self.emotion_manager = EmotionManager(self.model, exp_dir, self.emotion_map)
                    print(f"[Live2D] 表情扫描到 {len(self.emotion_manager.exp_names)} 个 exp3")
                    # 默认表情（如 noir 的 white.exp3.json）
                    if self.default_expression:
                        try:
                            self.emotion_manager.set_emotion(self.default_expression)
                            print(f"[Live2D] 已应用默认表情: {self.default_expression}")
                        except Exception as _ex:
                            print(f"[Live2D] 应用默认表情失败: {_ex}")
                    # 注册动作文件（model3.json 未登记 Motions → LoadExtraMotion 运行时注册）
                    self._register_motions()
                    self._render_ready = True
                    self.resize_to_screen()
                    print("[Live2D] 模型加载成功:", self.model_json_path)
                except Exception as exc:
                    self._failed = True
                    print(f"[Live2D] LoadModelJson 异常: {exc}")
            else:
                self._failed = True
                print("[Live2D] 模型文件不存在:", self.model_json_path)

        except Exception as e:
            self._failed = True
            import traceback
            print(f"[Live2D] 初始化失败: {e}")
            traceback.print_exc()

    def paintGL(self):
        if not self._render_ready or self._failed:
            return
        try:
            from OpenGL.GL import glClearColor, glClear, GL_COLOR_BUFFER_BIT
            glClearColor(0, 0, 0, 0)
            glClear(GL_COLOR_BUFFER_BIT)
            if self.model:
                self.model.Update()
                self.model.Draw()
        except Exception as e:
            print(f"[Live2D] 渲染错误: {e}")
            self._failed = True
        # ===== 调参参考线（F9）：画布边界 + 中线，用于对齐模型左右/上下边距 =====
        if self.show_tuning_guides:
            try:
                from PyQt5.QtGui import QPainter, QColor, QPen
                from PyQt5.QtCore import Qt as _Qt
                p = QPainter(self)
                pen = QPen(QColor(255, 90, 90, 230))
                pen.setWidth(2)
                pen.setStyle(_Qt.DashLine)
                p.setPen(pen)
                w, h = self.width(), self.height()
                p.drawRect(1, 1, w - 3, h - 3)
                p.drawLine(w // 2, 0, w // 2, h - 1)
                p.drawLine(0, h // 2, w - 1, h // 2)
                p.end()
            except Exception:
                pass

    def resizeGL(self, width, height):
        if self.model and self._render_ready:
            self.model.Resize(width, height)

    def _on_tick(self):
        if not self._render_ready or self._failed:
            return
        try:
            self._breath_time += 0.016

            # ===== 口型 =====
            if self.is_speaking:
                base = 0.1 + 0.1 * math.sin(self._breath_time * 8)
                self.mouth_open = min(self.mouth_open_max, base * self.mouth_open_max)
            else:
                self.mouth_open = 0.0
            self.model.SetParameterValue("ParamMouthOpenY", self.mouth_open, 0.8)

            # ===== 呼吸（小幅，避免身体缩放感） =====
            breathe = 0.5 + 0.12 * math.sin(self._breath_time * 0.5)
            try:
                self.model.SetParameterValue("ParamBreath", breathe, 1.0)
            except Exception:
                pass

            # ===== 头发/轻微晃动（仅无情绪动作且无定格姿态时轻幅待机）=====
            if not self._motion_playing and not self._frozen_params:
                hair_x = 2.0 * math.sin(self._breath_time * 0.8)
            else:
                hair_x = 0.0
            hair_z = 1.5 * math.sin(self._breath_time * 0.9 + 0.5)
            try:
                self.model.SetParameterValue("ParamAngleX", hair_x, 0.3)
                self.model.SetParameterValue("ParamAngleZ", hair_z, 0.3)
            except Exception:
                pass

            # ===== 随机眨眼（16~30 秒一次） =====
            self._update_blink()

            # ===== 情绪动作状态机：播放 → 定格(句内保持) → 收尾恢复 =====
            if self._motion_playing:
                try:
                    finished = self.model.IsMotionFinished()
                except Exception:
                    finished = False
                if not finished:
                    # 播放中：持续记录姿态快照（定格用）
                    self._snapshot_pose()
                elif self._motion_hold and not self._pose_frozen_flag:
                    # 句子还在播 → 定格在动作结束姿态（只定格一次，不刷日志）
                    self._frozen_params = dict(self._pose_snapshot)
                    self._pose_frozen_flag = True
                    if self._frozen_params:
                        print(f"[Live2D] 动作定格：句内保持姿态（{len(self._frozen_params)} 参数）")
                    else:
                        print("[Live2D] 动作定格：句内保持表情")
                elif not self._motion_hold:
                    # 收尾：释放定格并恢复默认表情
                    self._motion_playing = False
                    self._motion_key = None
                    self._unfreeze_pose()
                    self.set_emotion("")
                    print("[Live2D] 情绪动作播完，恢复默认表情")
            # 定格姿态持续施加（收尾时按权重衰减释放）
            if self._frozen_params:
                for pid in list(self._frozen_params.keys()):
                    val, w = self._frozen_params[pid]
                    try:
                        self.model.SetParameterValue(pid, val, w)
                    except Exception:
                        pass
                    if self._frozen_releasing:
                        w -= 0.05
                        if w <= 0:
                            del self._frozen_params[pid]
                        else:
                            self._frozen_params[pid] = (val, w)
                if not self._frozen_params:
                    self._frozen_releasing = False

            self.update()
        except Exception:
            pass

    def _update_blink(self):
        eye_value = self.eye_open_max
        now = time.time()
        if not self._blinking:
            if now - self._last_blink_time > random.uniform(16, 30):
                self._blinking = True
                self._blink_start_time = now
        else:
            elapsed = now - self._blink_start_time
            blink_duration = 0.12
            if elapsed < blink_duration:
                t = elapsed / blink_duration
                eye_value = self.eye_open_max * ((1.0 - t * 2) if t < 0.5 else ((t - 0.5) * 2))
                eye_value = max(0, min(self.eye_open_max, eye_value))
            else:
                self._blinking = False
                self._last_blink_time = now
                eye_value = self.eye_open_max
        try:
            self.model.SetParameterValue("ParamEyeLOpen", eye_value, 1.0)
            self.model.SetParameterValue("ParamEyeROpen", eye_value, 1.0)
        except Exception:
            pass

    # ========== 公共接口 ==========
    def start_live2d(self):
        if self._failed:
            return
        self.show()
        if not self.timer.isActive():
            self.timer.start()
        self._render_ready = True

    def stop_live2d(self):
        if self.timer.isActive():
            self.timer.stop()
        self.hide()

    def set_speaking(self, speaking: bool, voice_path: str = ""):
        self.is_speaking = speaking
        if not speaking:
            self.mouth_open = 0.0

    def toggle_tuning_guides(self):
        """开关调参参考线（画布边界 + 中线）"""
        self.show_tuning_guides = not self.show_tuning_guides
        print(f"[Live2D] 参考线: {'开' if self.show_tuning_guides else '关'}")
        self.update()

    def set_emotion(self, name: str):
        """切换表情 + 触发情绪动作（阶段 E）。name 为空 → 恢复默认表情。"""
        target = name or self.default_expression or ""
        if self.emotion_manager:
            self.emotion_manager.set_emotion(target)
        self._play_emotion_motion(name)

    def _register_motions(self):
        """把模型目录下所有 .motion3.json 注册进 "emotion" 组。
        （四个角色的 model3.json 都没登记 Motions → 运行时注册才能 StartMotion）"""
        if not self.model:
            return
        found = {}
        for root, _dirs, files in os.walk(self.model_dir):
            for f in files:
                if f.endswith(".motion3.json"):
                    found.setdefault(f, os.path.join(root, f))
        for fname, fpath in sorted(found.items()):
            try:
                no = self.model.LoadExtraMotion("emotion", fpath)
                self._emotion_motions[fname] = ("emotion", no)
            except Exception as e:
                print(f"[Live2D] 动作注册失败 {fname}: {e}")
        if self._emotion_motions:
            print(f"[Live2D] 已注册动作 {len(self._emotion_motions)} 个")

    def _play_emotion_motion(self, name: str):
        """按情绪播放动作（pet.json model.motions: 情绪 → [动作文件名] 或 [组名, 序号]）。
        文件名形式 → 走 "emotion" 组（运行时注册）；组名形式 → 模型原生组。"""
        if not name or not self.motion_map or not self.model:
            return
        entry = self.motion_map.get(name)
        if not entry:
            return
        if isinstance(entry, str):
            entry = [entry]
        if not entry:
            return
        group = str(entry[0])
        no = int(entry[1]) if len(entry) > 1 else 0
        try:
            native = self.model.GetMotionGroups()
        except Exception:
            native = {}
        try:
            self.model.StopAllMotions()
            # 旧定格姿态：衰减释放（与新动作平滑过渡，而不是瞬间回正再重来）
            if self._frozen_params:
                self._frozen_releasing = True
            self._pose_frozen_flag = False
            if group in (native or {}):
                self.model.StartMotion(group, no, 3)
                self._motion_key = (group, no)
                print(f"[Live2D] 情绪动作: {name} → 原生组 {group}[{no}]")
            else:
                fname = group if group.endswith(".motion3.json") else group + ".motion3.json"
                if fname in self._emotion_motions:
                    g, idx = self._emotion_motions[fname]
                    self.model.StartMotion(g, idx, 3)
                    self._motion_key = (g, idx)
                    print(f"[Live2D] 情绪动作: {name} → {fname} (emotion[{idx}])")
                else:
                    print(f"[Live2D] 动作文件不存在或未注册: {fname}")
                    return
            self._motion_playing = True
        except Exception as e:
            print(f"[Live2D] 情绪动作失败: {e}")

    def _snapshot_pose(self):
        """记录当前姿态参数值（动作播放期间每帧更新，用于播完定格）。"""
        if not self.model:
            return
        try:
            for pid in self._POSE_PARAMS:
                try:
                    self._pose_snapshot[pid] = (float(self.model.GetParameterValue(pid)), 0.8)
                except Exception:
                    pass
        except Exception:
            pass

    def _unfreeze_pose(self):
        """释放定格姿态（按权重衰减，避免瞬间弹回）。"""
        self._frozen_releasing = True
        self._pose_snapshot = {}
        self._pose_frozen_flag = False

    def hold_emotion_motion(self, hold: bool):
        """句子播放期间保持当前情绪动作：hold=True 时动作播完自动重播
        （呼吸/眨眼/物理继续运转）；hold=False 收尾（播完自然结束并回默认表情）。"""
        self._motion_hold = bool(hold)

    def stop_emotion_action(self):
        """立即结束情绪动作并恢复默认表情（回复整体结束的收尾用）。"""
        self._motion_hold = False
        self._motion_playing = False
        self._motion_key = None
        self._frozen_params = {}
        self._frozen_releasing = False
        self._pose_frozen_flag = False
        if self.model:
            try:
                self.model.StopAllMotions()
            except Exception:
                pass
        self.set_emotion("")

    def reset_params(self):
        if self.model:
            try:
                self.model.ResetParameters()
                self.model.ResetExpressions()
            except Exception:
                pass
            self.mouth_open = 0.0

    # ========== 区域判定参数（按需调整） ==========
    # 七头身比例：
    HEAD_TOP = 0.0        # 头部起始 (相对于窗口高度)
    HEAD_BOTTOM = 0.18     # 头部结束（约 18% 是头）
    TALK_TOP = 0.50        # 对话区域起始（上半身不触发）
    TALK_BOTTOM = 1.0      # 对话区域结束
    EDGE_MARGIN_X = 0.12   # 左右边缘不响应（12% 边距，避免误触）

    def _in_zone(self, y, top, bottom):
        """y 是否在 [top, bottom) 比例范围内"""
        return self.height() * top <= y < self.height() * bottom

    def _in_x_range(self, x):
        """x 是否在有效横向范围内（排除边缘）"""
        margin = self.width() * self.edge_margin_x
        return margin <= x <= self.width() - margin

    # ========== 鼠标交互 ==========
    def mousePressEvent(self, event):
        if not self._render_ready:
            return
        self.interacted.emit()
        if event.button() == Qt.LeftButton:
            x, y = event.x(), event.y()
            self.setCursor(Qt.ArrowCursor)

            if self._in_zone(y, self.head_top, self.head_bottom) and self._in_x_range(x):
                # 头部区域 → 摸头
                self._touch_head = True
                self._head_press_x = x
                self.setCursor(Qt.OpenHandCursor)
            elif self._in_zone(y, self.talk_top, self.talk_bottom) and self._in_x_range(x):
                # 下半身区域 → 对话
                self.trigger_input_mode.emit()
            else:
                self._touch_head = False
                self._head_press_x = None
        elif event.button() == Qt.MiddleButton:
            self._mouse_drag_offset = event.pos()
            self.setCursor(Qt.SizeAllCursor)

    def mouseMoveEvent(self, event):
        self.interacted.emit()
        if self._touch_head and self._head_press_x is not None:
            if abs(event.x() - self._head_press_x) > 50:
                self.trigger_touch_head.emit()
                self._touch_head = False
                self._head_press_x = None
        if self._mouse_drag_offset and event.buttons() == Qt.MiddleButton:
            delta = event.pos() - self._mouse_drag_offset
            self.move(self.pos() + delta)
            self.trigger_drag_move.emit(delta.x(), delta.y())

    def mouseReleaseEvent(self, event):
        self.interacted.emit()
        if event.button() == Qt.LeftButton:
            self._touch_head = False
            self._head_press_x = None
            self.setCursor(Qt.ArrowCursor)
        elif event.button() == Qt.MiddleButton:
            self._mouse_drag_offset = None
            self.setCursor(Qt.ArrowCursor)

    # ========== 窗口缩放 ==========
    def resize_to_screen(self, screen_index: int = 0):
        screens = QGuiApplication.screens()
        if 0 <= screen_index < len(screens):
            screen = screens[screen_index]
        else:
            screen = QGuiApplication.primaryScreen()
        if screen:
            h = int(screen.availableGeometry().height() * self.window_height_ratio)
            w = int(h * self.window_ratio)
            self.resize(w, h)
            return (w, h)
        return (800, int(800 / max(self.window_ratio, 0.1)))

    def closeEvent(self, event):
        self.stop_live2d()
        super().closeEvent(event)