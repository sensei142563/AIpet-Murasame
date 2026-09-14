"""PCL 风格主窗口 — Live2D 预览（回退 2D 立绘）+ 所有动画 + 模型管理"""

import os
import sys
import math
import socket
import time
import threading
import subprocess
import urllib.request

from PyQt5.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve,
    QAbstractAnimation, QRect, QRectF
)
from PyQt5.QtGui import (
    QPainter, QColor, QPainterPath, QFont, QPixmap, QIcon, QSurfaceFormat,
    QImage, QRegion
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
        # 预览背景：主题壁纸以纹理整图拉伸画进 GL（不再与整窗壁纸对齐裁剪，确保整图可见）
        self._bg_tex = 0
        self._bg_tex_size = (0, 0)
        self._bg_tex_ok = False

    def _bg_image(self):
        """主题壁纸 QImage（RGBA）；无则 None"""
        try:
            kind, path, _op = background_info()
            if kind == "image" and path and os.path.isfile(path):
                img = QImage(path)
                if not img.isNull():
                    return img.convertToFormat(QImage.Format_RGBA8888).mirrored()
        except Exception:
            pass
        return None

    def _clear_color(self):
        """无壁纸时的清屏色（主题预览底色）"""
        return (PREVIEW_BG.redF(), PREVIEW_BG.greenF(), PREVIEW_BG.blueF(), 1.0)

    def _ensure_bg_tex(self):
        """把壁纸上传为 GL 纹理（视口变化时重传），失败则回退纯色"""
        try:
            from OpenGL.GL import (glGenTextures, glBindTexture, glTexImage2D,
                                   GL_TEXTURE_2D, GL_RGBA, GL_UNSIGNED_BYTE,
                                   GL_TEXTURE_MIN_FILTER, GL_TEXTURE_MAG_FILTER, GL_LINEAR,
                                   glTexParameteri, glPixelStorei, GL_UNPACK_ALIGNMENT,
                                   glDeleteTextures)
            img = self._bg_image()
            w, h = self.width(), self.height()
            if img is None:
                if self._bg_tex:
                    glDeleteTextures(1, [self._bg_tex])
                    self._bg_tex = 0
                self._bg_tex_ok = False
                return
            iw, ih = img.width(), img.height()
            if not self._bg_tex or self._bg_tex_size != (iw, ih):
                if not self._bg_tex:
                    self._bg_tex = glGenTextures(1)
                glBindTexture(GL_TEXTURE_2D, self._bg_tex)
                glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
                # PyOpenGL 需要 buffer 对象：用 asstring 转 bytes（bits() 指针直接传会失败）
                _raw = img.constBits()
                if hasattr(_raw, "asstring"):
                    _raw = _raw.asstring(iw * ih * 4)
                glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, iw, ih, 0,
                             GL_RGBA, GL_UNSIGNED_BYTE, _raw)
                self._bg_tex_size = (iw, ih)
            self._bg_tex_ok = True
        except Exception as e:
            print(f"[PCL] 壁纸纹理加载失败（用纯色预览底）: {e}")
            self._log_bg_err(f"纹理上传失败: {e}")
            self._bg_tex_ok = False

    def _sync_video_tex(self):
        """主题为视频背景时：把最新视频帧上传为 GL 纹理，live2d 区域与视频同步"""
        try:
            win = self.window()
            if win is None:
                return
            serial = getattr(win, "_bg_video_serial", 0)
            img = getattr(win, "_bg_video_frame", None)
            if serial == getattr(self, "_bg_video_serial_done", -1):
                return
            if img is None or img.isNull():
                return
            rgba = img.convertToFormat(QImage.Format_RGBA8888).mirrored()
            iw, ih = rgba.width(), rgba.height()
            from OpenGL.GL import (glBindTexture, glTexImage2D, glPixelStorei,
                                   glGenTextures, glTexParameteri,
                                   GL_TEXTURE_2D, GL_RGBA, GL_UNSIGNED_BYTE,
                                   GL_UNPACK_ALIGNMENT, GL_TEXTURE_MIN_FILTER,
                                   GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            if not self._bg_tex:
                self._bg_tex = glGenTextures(1)
                glBindTexture(GL_TEXTURE_2D, self._bg_tex)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glBindTexture(GL_TEXTURE_2D, self._bg_tex)
            glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
            _raw = rgba.constBits()
            if hasattr(_raw, "asstring"):
                _raw = _raw.asstring(iw * ih * 4)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, iw, ih, 0,
                         GL_RGBA, GL_UNSIGNED_BYTE, _raw)
            self._bg_tex_size = (iw, ih)
            self._bg_tex_ok = True
            self._bg_video_serial_done = serial
            if getattr(self, "_vt", 0) < 3:
                self._vt = getattr(self, "_vt", 0) + 1
                self._log_bg_err(f"视频帧同步到 GL 纹理 #{self._vt}")
        except Exception as e:
            self._log_bg_err(f"视频纹理同步失败: {e}")

    def _log_bg_err(self, msg):
        try:
            _p = os.path.join(_app_base_dir(), "data", "preview_bg.log")
            os.makedirs(os.path.dirname(_p), exist_ok=True)
            with open(_p, "a", encoding="utf-8") as f:
                import datetime as _dt
                f.write(f"{_dt.datetime.now():%H:%M:%S} {msg}\n")
        except Exception:
            pass

    def _init_bg_shader(self):
        """初始化背景纹理着色器（core/compat 通用）；失败则回退 legacy"""
        self._bg_prog = 0
        self._bg_vao = 0
        self._bg_vbo = 0
        self._use_shader = False
        try:
            from OpenGL.GL import (glGetString, GL_SHADING_LANGUAGE_VERSION,
                                   glCreateShader, glShaderSource, glCompileShader,
                                   glCreateProgram, glAttachShader, glLinkProgram,
                                   glGetShaderiv, glGetProgramiv, GL_COMPILE_STATUS,
                                   GL_LINK_STATUS, glDeleteShader, glGetUniformLocation,
                                   glGenVertexArrays, glGenBuffers)
            import ctypes
            glsl = (glGetString(GL_SHADING_LANGUAGE_VERSION) or b"1.0")
            ver = float(glsl.split(b" ")[0][:3])
            self._log_bg_err(f"GLSL 版本: {glsl!r}")
            vs = """#version 330
            layout(location=0) in vec2 aPos;
            layout(location=1) in vec2 aUV;
            out vec2 vUV;
            void main(){ vUV = aUV; gl_Position = vec4(aPos, 0.0, 1.0); }"""
            fs = """#version 330
            in vec2 vUV;
            uniform sampler2D tex;
            out vec4 frag;
            void main(){ frag = texture(tex, vUV); }"""
            if ver < 3.3:
                self._log_bg_err("GLSL < 3.3 → 使用 legacy 绘制")
                return
            vs_id = glCreateShader(0x8B31)  # GL_VERTEX_SHADER
            glShaderSource(vs_id, vs)
            glCompileShader(vs_id)
            if not glGetShaderiv(vs_id, GL_COMPILE_STATUS):
                self._log_bg_err("VS 编译失败（legacy 兜底）")
                return
            fs_id = glCreateShader(0x8B30)  # GL_FRAGMENT_SHADER
            glShaderSource(fs_id, fs)
            glCompileShader(fs_id)
            if not glGetShaderiv(fs_id, GL_COMPILE_STATUS):
                self._log_bg_err("FS 编译失败（legacy 兜底）")
                return
            prog = glCreateProgram()
            glAttachShader(prog, vs_id)
            glAttachShader(prog, fs_id)
            glLinkProgram(prog)
            glDeleteShader(vs_id)
            glDeleteShader(fs_id)
            if not glGetProgramiv(prog, GL_LINK_STATUS):
                self._log_bg_err("Program 链接失败（legacy 兜底）")
                return
            self._bg_prog = prog
            self._bg_vao = glGenVertexArrays(1)
            self._bg_vbo = glGenBuffers(1)
            self._use_shader = True
            self._log_bg_err("着色器路径已启用")
        except Exception as e:
            self._log_bg_err(f"shader 初始化失败→legacy: {e}")
            self._use_shader = False

    def _draw_bg_shader(self):
        """着色器路径绘制全屏纹理背景"""
        try:
            import ctypes
            from OpenGL.GL import (glUseProgram, glActiveTexture, glBindTexture,
                                   glBindVertexArray, glBindBuffer, glBufferData,
                                   glVertexAttribPointer, glEnableVertexAttribArray,
                                   glDrawArrays, glUniform1i, glDisable, glGetUniformLocation,
                                   GL_ARRAY_BUFFER, GL_TEXTURE0, GL_TEXTURE_2D,
                                   GL_TRIANGLE_STRIP, GL_FLOAT, GL_BLEND, GL_DEPTH_TEST)
            import array
            # cover 中心裁切填满：保持宽高比放大到铺满整个区域，
            # 画面四周超出的部分自然裁掉，无空白、不变形
            iw, ih = self._bg_tex_size
            w, h = max(1, self.width()), max(1, self.height())
            u0, u1, v0, v1 = 0.0, 1.0, 0.0, 1.0
            if iw > 0 and ih > 0:
                s = max(w / iw, h / ih)
                hx = (iw * s) / w
                hy = (ih * s) / h
            else:
                hx = hy = 1.0
            verts = array.array("f", [
                -hx, -hy, u0, v0,
                 hx, -hy, u1, v0,
                -hx,  hy, u0, v1,
                 hx,  hy, u1, v1,
            ])
            glUseProgram(self._bg_prog)
            glBindVertexArray(self._bg_vao)
            glBindBuffer(GL_ARRAY_BUFFER, self._bg_vbo)
            glBufferData(GL_ARRAY_BUFFER, verts.tobytes(), 0x88E4)  # GL_STREAM_DRAW
            pos_loc = 0
            uv_loc = 1
            glEnableVertexAttribArray(pos_loc)
            glVertexAttribPointer(pos_loc, 2, GL_FLOAT, False, 16, None)
            glEnableVertexAttribArray(uv_loc)
            glVertexAttribPointer(uv_loc, 2, GL_FLOAT, False, 16,
                                  ctypes.c_void_p(8))
            glActiveTexture(GL_TEXTURE0)
            glBindTexture(GL_TEXTURE_2D, self._bg_tex)
            glUniform1i(glGetUniformLocation(self._bg_prog, b"tex"), 0)
            glDisable(GL_BLEND)
            glDisable(GL_DEPTH_TEST)
            glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
            glBindVertexArray(0)
            glUseProgram(0)
            try:
                from OpenGL.GL import glGetError
                _err = glGetError()
                if _err:
                    self._log_bg_err(f"背景绘制后 GL error: 0x{_err:x}")
            except Exception:
                pass
            return True
        except Exception as e:
            self._log_bg_err(f"shader 绘制失败: {e}")
            return False

    def _draw_bg_legacy(self):
        """legacy（GLSL<1.5）绘制背景"""
        try:
            from OpenGL.GL import (glEnable, glDisable, glBindTexture, glBegin, glEnd,
                                   glColor4f, glTexCoord2f, glVertex2f, glMatrixMode,
                                   glLoadIdentity, glOrtho, glPushMatrix, glPopMatrix,
                                   GL_TEXTURE_2D, GL_QUADS, GL_PROJECTION, GL_MODELVIEW,
                                   GL_DEPTH_TEST)
            iw, ih = self._bg_tex_size
            w, h = max(1, self.width()), max(1, self.height())
            # cover 中心裁切填满：等比放大到铺满，无空白不变形（超出的部分被裁掉）
            u0, v0, u1, v1 = 0.0, 0.0, 1.0, 1.0
            if iw > 0 and ih > 0:
                s = max(w / iw, h / ih)
                dw, dh = iw * s, ih * s
            else:
                dw, dh = w, h
            x0 = (w - dw) / 2.0
            y0 = (h - dh) / 2.0
            glPushMatrix()
            glMatrixMode(GL_PROJECTION)
            glPushMatrix()
            glLoadIdentity()
            glOrtho(0, w, 0, h, -1, 1)
            glMatrixMode(GL_MODELVIEW)
            glPushMatrix()
            glLoadIdentity()
            glDisable(GL_DEPTH_TEST)
            glEnable(GL_TEXTURE_2D)
            glBindTexture(GL_TEXTURE_2D, self._bg_tex)
            glColor4f(1, 1, 1, 1)
            glBegin(GL_QUADS)
            glTexCoord2f(u0, v0); glVertex2f(x0, y0)
            glTexCoord2f(u1, v0); glVertex2f(x0 + dw, y0)
            glTexCoord2f(u1, v1); glVertex2f(x0 + dw, y0 + dh)
            glTexCoord2f(u0, v1); glVertex2f(x0, y0 + dh)
            glEnd()
            glDisable(GL_TEXTURE_2D)
            glPopMatrix()
            glMatrixMode(GL_PROJECTION)
            glPopMatrix()
            glMatrixMode(GL_MODELVIEW)
            glPopMatrix()
            return True
        except Exception as e:
            self._log_bg_err(f"legacy 绘制失败: {e}")
            return False

    def _draw_bg_quad(self):
        """把背景（图片/视频帧）按原比例 fit 画在预览区中央：优先着色器，GLSL<1.5 回退 legacy"""
        if not self._bg_tex_ok or not self._bg_tex:
            return False
        if getattr(self, "_use_shader", False):
            return self._draw_bg_shader()
        return self._draw_bg_legacy()

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
            glClearColor(*self._clear_color())
            self._init_bg_shader()

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
            glClearColor(*self._clear_color())
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            # 先把主题背景画满预览区，再叠 Live2D —— 背景不缺失、不穿透桌面
            # 视频主题：与解码线程的最新帧同步；图片/无背景：静态壁纸纹理
            try:
                _win = self.window()
                if _win is not None and getattr(_win, "_bg_reader", None) is not None:
                    self._sync_video_tex()
                else:
                    self._ensure_bg_tex()
            except Exception:
                pass
            self._draw_bg_quad()
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
        # 透明底：有主题壁纸时透出背景（原 Color8 大块纯色面板已去除）
        self.setStyleSheet("background: transparent;")
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
            # 穿该套当前保存的服装（a/b 两套素材各自独立，跨套图层自动换算）
            try:
                from tool.portrait_outfit import normalize_layers, apply_outfit
                first = apply_outfit(normalize_layers(first, self._portrait_type),
                                     self._portrait_type)
            except Exception:
                pass
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
            self.setStyleSheet(f"color: {Gray3.name()}; font-size: 13px; background: transparent;")

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

def _vlog_reset():
    """清空视频背景调试日志（每次进入视频分支时调用一次）"""
    try:
        import os as _os
        with open(_os.path.join(_app_base_dir(), "data", "video_bg.log"), "w",
                  encoding="utf-8") as _f:
            _f.write("")
    except Exception:
        pass


def _vlog(*args):
    """视频背景调试日志（data/video_bg.log），故障排查用"""
    try:
        import os as _os
        import datetime as _dt
        with open(_os.path.join(_app_base_dir(), "data", "video_bg.log"), "a",
                  encoding="utf-8") as _f:
            _f.write("%s %s\n" % (_dt.datetime.now().strftime("%H:%M:%S.%f")[:-3],
                                  " ".join(str(a) for a in args)))
    except Exception:
        pass


class _VideoBgReader(QThread):
    """视频背景解码线程（OpenCV）。

    为什么不用 QtMultimedia：本机 Win11 26200 上 Qt5.15 的 WMF/DirectShow 引擎对
    H.264 mp4 打开即 InvalidMedia/崩溃（Qt5Multimedia.dll 0xC00000FD 栈溢出），
    OpenCV(ffmpeg) 实测可稳定解码。线程内循环读取 → 发 QImage → 主线程刷 QLabel。"""

    frame_ready = pyqtSignal(object)

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self._path = path
        self._running = True

    def stop(self):
        self._running = False
        try:
            self.wait(2000)
        except Exception:
            pass

    def run(self):
        cap = None
        try:
            import cv2
            import time as _t
            cap = cv2.VideoCapture(self._path)
            if not cap.isOpened():
                _vlog("cv2 open FAIL:", self._path)
                return
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            fps = max(1.0, min(60.0, fps))
            period = 1.0 / fps
            _vlog("cv2 opened ok fps=%.2f" % fps)
            n = 0
            while self._running:
                ok, frame = cap.read()
                if not ok:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # 循环重播
                    continue
                n += 1
                if n <= 2 or n % 300 == 0:
                    _vlog("cv2 frame #%d" % n)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w = rgb.shape[:2]
                img = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy()
                if self._running:
                    self.frame_ready.emit(img)
                self.msleep(int(period * 1000))
        except Exception as e:
            import traceback as _tb
            _vlog("reader EXC:", repr(e), _tb.format_exc(limit=3).replace("\n", " | "))
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
            _vlog("reader exit")


class _RoundedBgLabel(QLabel):
    """背景标签（图片/视频壁纸用）：绘制时按窗口全局圆角裁切。
    否则正方形标签会把父层画好的圆角区重新盖成方形角。"""

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        try:
            _r = int(26 * S)          # 满铺窗口：圆角半径=窗口圆角
            _path = QPainterPath()
            _path.addRoundedRect(QRectF(self.rect()), _r, _r)
            p.setClipPath(_path)
        except Exception:
            pass
        pm = self.pixmap()
        if pm is not None and not pm.isNull():
            p.drawPixmap(0, 0, pm)
        p.end()


class _RoundBackWidget(QWidget):
    """窗口圆角底色层（透明窗口下父窗口 paintEvent 不可靠，
    用普通子控件自绘最稳定）：整窗圆角路径填充主题 Color8，
    四角外保持透明 → 与壁纸/标题栏各自圆角裁切拼成整体圆角轮廓。"""

    def paintEvent(self, event):
        try:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing, True)
            r = int(26 * S)
            path = QPainterPath()
            path.addRoundedRect(QRectF(self.rect()), r, r)
            p.fillPath(path, QColor(Color8))
            p.end()
        except Exception:
            pass


class PCLMainWindow(QWidget):

    napcat_relogin_done = pyqtSignal(bool)   # True=已恢复/已提示扫码; False=失败
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
        self._wechat_process = None
        self._wechat_pet_id = None

        self._setup_window()
        # 全窗底色层：无壁纸主题时铺满整窗（= 与目录条同宽），壁纸/视频主题会被盖住
        self._round_back = _RoundBackWidget(self)
        self._round_back.setGeometry(0, 0, self.width(), self.height())
        self._round_back.show()
        self.pan_back = QWidget(self)
        self.pan_back.setGeometry(0, 0, self.width(), self.height())
        self._build_ui()

        self._fade_timer = QTimer(self); self._fade_step = 0; self._fade_max = 0; self._fade_cb = None; self._fade_effect = None
        # 主题默认强调色（accent）——主题切换/重启后生效
        try:
            _acc = ACCENT_ID if ACCENT_ID in THEME_COLORS else "blue"
        except Exception:
            _acc = "blue"
        self._color_old = (_acc, THEME_COLORS[_acc]); self._color_new = (_acc, THEME_COLORS[_acc]); self._color_step = 0; self._color_max = 30
        self._color_timer = QTimer(self); self._color_timer.timeout.connect(self._color_tick)
        self._drag_pos = None
        self._animating = False

        # 标题栏渐变直接以主题强调色起步（避免从蓝色闪变）
        try:
            _tc = THEME_COLORS[_acc]
            self.titlebar.set_accent_direct(_tc["title_start"], _tc["title_end"])
            self.sidebar.set_theme(_acc)
        except Exception:
            pass

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
        try:
            if not getattr(self, "_silicon_applied", False):
                self._silicon_applied = True
                self._apply_silicon_ui()
        except Exception as _e:
            print(f"[PCL] ⚠ Silicon 界面应用异常: {_e}")
        self._apply_round_mask()
        if self._model_queue and self._preview_widget is None:
            pet_id, path = self._model_queue.pop(0)
            self._preview_pet(pet_id, path)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        try:
            self._round_back.setGeometry(0, 0, self.width(), self.height())
        except Exception:
            pass
        self._apply_round_mask()

    def _apply_round_mask(self):
        # 窗口不做整体圆角（仅顶部目录条圆角，见 PCLTitleBar），保留透明窗口叠层
        try:
            self.update()
        except Exception:
            pass

    def _setup_window(self):
        # 不再置顶：PCL 是普通窗口，可通过任务栏正常最小化（用户反馈）
        self.setWindowFlags(Qt.FramelessWindowHint)
        # 保持透明窗口：主题壁纸/视频/半透明控件正常叠层
        self.setAttribute(Qt.WA_TranslucentBackground)
        w, h = int(1200 * S), int(900 * S)
        self.setMinimumSize(int(950 * S), int(700 * S))
        self.resize(w, h)

    def _build_background(self):
        """主题背景层：支持图片（cover）或视频（循环播放）；无则白色底"""
        self._bg_kind = ""
        self._bg_label = None
        self._bg_pixmap = None
        self._bg_reader = None       # 视频背景：OpenCV 解码线程
        self._bg_video_frame = None  # 最新视频帧（供 Live2D 预览区 GL 同步）
        self._bg_video_serial = 0    # 帧序号（新帧 +1）
        try:
            kind, path, opacity = background_info()
            self._bg_kind = kind
            if kind == "image" and path:
                self._bg_label = _RoundedBgLabel(self.pan_back)
                self._bg_label.setAttribute(Qt.WA_TransparentForMouseEvents)
                self._bg_label.setGeometry(0, 0, self.pan_back.width(), self.pan_back.height())
                if opacity < 1.0:
                    _eff = QGraphicsOpacityEffect(self._bg_label)
                    _eff.setOpacity(opacity)
                    self._bg_label.setGraphicsEffect(_eff)
                self._bg_pixmap = QPixmap(path)
                self._bg_label.show()
                self._bg_label.lower()
            elif kind == "video" and path:
                try:
                    _vlog_reset()
                    _vlog("video branch start:", path)
                    # 视频解码用 OpenCV(ffmpeg) 线程，完全绕开 QtMultimedia：
                    # 本机 Win11 26200 上 Qt5.15 WMF/DirectShow 引擎打开 H.264 mp4
                    # 即 InvalidMedia 或 Qt5Multimedia.dll 栈溢出(0xC00000FD)，不可用。
                    self._bg_label = _RoundedBgLabel(self.pan_back)
                    self._bg_label.setAttribute(Qt.WA_TransparentForMouseEvents)
                    self._bg_label.setGeometry(0, 0, self.pan_back.width(), self.pan_back.height())
                    if opacity < 1.0:
                        _eff2 = QGraphicsOpacityEffect(self._bg_label)
                        _eff2.setOpacity(opacity)
                        self._bg_label.setGraphicsEffect(_eff2)
                    self._bg_label.show()
                    self._bg_label.lower()
                    self._bg_reader = _VideoBgReader(path, self)
                    self._bg_reader.frame_ready.connect(self._on_bg_video_frame)
                    self._bg_reader.start()
                    print(f"[PCL] 视频背景播放中（OpenCV 解码）: {path}")
                except Exception as e:
                    print(f"[PCL] 视频背景不可用（已跳过）: {e}")
                    self._bg_reader = None
                    self._bg_kind = ""
        except Exception:
            pass

    def _update_background(self):
        """窗口尺寸变化时更新背景（cover 裁剪 / 视频铺满）"""
        try:
            w = self.pan_back.width()
            h = self.pan_back.height()
            if self._bg_label is not None:
                self._bg_label.setGeometry(0, 0, w, h)
                if self._bg_pixmap and not self._bg_pixmap.isNull() and w > 0 and h > 0:
                    pw, ph = self._bg_pixmap.width(), self._bg_pixmap.height()
                    sc = max(w / pw, h / ph)
                    tw, th = int(pw * sc + 0.5), int(ph * sc + 0.5)
                    scaled = self._bg_pixmap.scaled(
                        tw, th, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                    self._bg_label.setPixmap(scaled.copy((tw - w) // 2, (th - h) // 2, w, h))
                self._bg_label.lower()
        except Exception:
            pass

    def _on_bg_video_frame(self, img):
        """OpenCV 解码线程送来一帧 → cover 裁切 → 刷到背景 QLabel"""
        try:
            if img is None or img.isNull():
                return
            # 供 Live2D 预览区 GL 同步取用（paintGL 里上传为纹理）
            self._bg_video_frame = img
            self._bg_video_serial += 1
            if self._bg_label is None:
                return
            self._tick_count = getattr(self, "_tick_count", 0) + 1
            if self._tick_count <= 2 or self._tick_count % 300 == 0:
                _vlog("frame->label #%d %dx%d" % (self._tick_count, img.width(), img.height()))
            w = self.pan_back.width()
            h = self.pan_back.height()
            if w <= 0 or h <= 0:
                return
            pw, ph = img.width(), img.height()
            if pw <= 0 or ph <= 0:
                return
            sc = max(w / pw, h / ph)
            tw, th = int(pw * sc + 0.5), int(ph * sc + 0.5)
            pm = QPixmap.fromImage(img).scaled(
                tw, th, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            self._bg_label.setPixmap(pm.copy((tw - w) // 2, (th - h) // 2, w, h))
        except Exception:
            pass

    def _build_ui(self):
        self._build_background()
        self.titlebar = PCLTitleBar(self)
        self.titlebar.setParent(self.pan_back)
        self.titlebar.setGeometry(0, 0, self.pan_back.width(), int(48 * S))
        self.titlebar.nav_changed.connect(self._switch_page)

        content = QWidget(self.pan_back)
        content.setGeometry(0, int(48 * S), self.pan_back.width(), self.pan_back.height() - int(48 * S))
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0); content_layout.setSpacing(0)

        # ===== SiliconUI 布局：左侧竖向导航栏（新主题启用；旧主题仍用顶部横排）=====
        self.nav_rail = None
        try:
            from .colors import current_theme_id
            if current_theme_id() == "silicon":
                from .silicon_ui import PCLNavRail
                from .colors import block_icon
                _items = [
                    ("模型", block_icon("GoldBlock"), 0),
                    ("设置", block_icon("RedstoneBlock"), 1),
                    ("记忆", block_icon("DiamondBlock"), 3),
                    ("桌宠", block_icon("Grass"), 4),
                    ("提示词", block_icon("CommandBlock"), 5),
                    ("插件", block_icon("Anvil"), 6),
                    ("主题", block_icon("DiamondBlock"), 7),
                ]
                self.nav_rail = PCLNavRail(_items)
                self.nav_rail.nav_changed.connect(self._switch_page)
                content_layout.addWidget(self.nav_rail)
                # 顶部横排导航让位给左侧竖栏（保留控件对象，仅隐藏）
                for _b in (self.titlebar.btn_model, self.titlebar.btn_settings,
                           self.titlebar.btn_memory, self.titlebar.btn_pets,
                           self.titlebar.btn_prompt, self.titlebar.btn_plugins,
                           self.titlebar.btn_themes):
                    _b.setVisible(False)
                print("[PCL] SiliconUI 布局：左侧竖向导航栏已启用")
        except Exception as _e:
            print(f"[PCL] ⚠ 竖向导航栏创建失败（回退顶部导航）: {_e}")
            self.nav_rail = None

        self.sidebar = PCLSidebar()
        # 阶段 B：点卡片 → 设为活动角色 + 预览对应模型
        self.sidebar.model_selected.connect(self._on_model_selected)
        content_layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack, 1)

        # ===== 预览页（模型页）：左右贴边与顶部目录条同宽 =====
        self.preview_page = QWidget()
        self.preview_layout = QVBoxLayout(self.preview_page)
        self.preview_layout.setContentsMargins(0, int(14 * S), 0, int(10 * S))
        self.preview_layout.setSpacing(int(12 * S))

        # ===== 双启动按钮（桌宠 + QQ）=====
        self._qq_process = None
        self._napcat_proc = None             # 本启动器拉起的 start_napcat.bat 控制台进程（Popen 句柄）
        self._napcat_started_by_us = False   # 本次会话 NapCat 是否由本启动器拉起（关闭 QQ 时连带关闭）
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
                color: white; border: 2px solid rgba(255,255,255,0.5); font-size: {int(14*S)}px; font-weight: bold;
                font-family: 'Microsoft YaHei'; border-radius: {int(14*S)}px; }}
            QPushButton:hover {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 {THEME_COLORS['blue']['btn_end']},stop:1 {THEME_COLORS['blue']['btn_start']}); }}
        """)
        self.qq_btn.setFixedHeight(int(48 * S))
        self.qq_btn.clicked.connect(self._on_qq_clicked)
        if qq_enabled:
            btn_row.addWidget(self.qq_btn, 1)

        # 微信按钮（config wechat_enabled="true" 才显示）
        wechat_enabled = str(self._config.get("wechat_enabled", "false")).lower() == "true"
        self.wechat_btn = QPushButton("  💬 启动微信 AIpet")
        self.wechat_btn.setToolTip("启动微信 ClawBot 聊天模块（首次需扫码登录）")
        self._wechat_btn_styled(False)
        self.wechat_btn.setFixedHeight(int(48 * S))
        self.wechat_btn.clicked.connect(self._on_wechat_clicked)
        if wechat_enabled:
            btn_row.addWidget(self.wechat_btn, 1)

        # ===== QQ 工具按钮行（仅 QQ AIpet 启动后显示）=====
        self.qq_tools_row = QWidget()
        qq_tools_lay = QHBoxLayout(self.qq_tools_row)
        qq_tools_lay.setContentsMargins(0, 0, 0, 0)
        qq_tools_lay.setSpacing(int(8 * S))
        qq_tools_lay.addStretch(1)
        qq_tool_style = f"""
            QPushButton {{ background: rgba(255,255,255,160); color: {Color1.name()};
                border: 1px solid {Color5.name()};
                padding: {int(6*S)}px {int(14*S)}px; font-size: {int(12*S)}px;
                font-family: 'Microsoft YaHei'; border-radius: {btn_radius()}px; }}
            QPushButton:hover {{ background: {Color4.name()}; color: white; }}
        """
        self.qq_relogin_btn = QPushButton("  🔄 重新扫码登录 NapCat")
        self.qq_relogin_btn.setToolTip("QQ 被平台下线/登录失效时，强制重启 NapCat；如需授权会弹出二维码")
        self.qq_relogin_btn.setCursor(Qt.PointingHandCursor)
        self.qq_relogin_btn.setStyleSheet(qq_tool_style)
        self.qq_relogin_btn.clicked.connect(self._on_napcat_relogin)
        qq_tools_lay.addWidget(self.qq_relogin_btn)
        self.qq_webui_btn = QPushButton("  🌐 NapCat 配置")
        self.qq_webui_btn.setToolTip("打开 NapCat 配置界面（浏览器）")
        self.qq_webui_btn.setCursor(Qt.PointingHandCursor)
        self.qq_webui_btn.setStyleSheet(qq_tool_style)
        self.qq_webui_btn.clicked.connect(self._on_napcat_webui)
        qq_tools_lay.addWidget(self.qq_webui_btn)
        self.qq_tools_row.hide()

        # Token 复制行(工具行上方)：直接进入配置页若仍要求输入 token，可一键复制
        self.qq_token_row = QWidget()
        tok_lay = QHBoxLayout(self.qq_token_row)
        tok_lay.setContentsMargins(0, 0, 0, 0)
        tok_lay.addStretch(1)
        self.qq_token_btn = QPushButton("  📋 复制 NapCat Token")
        self.qq_token_btn.setToolTip("点击复制 WebUI Token 到剪贴板（配置页要求输入时粘贴即可）")
        self.qq_token_btn.setCursor(Qt.PointingHandCursor)
        self.qq_token_btn.setStyleSheet(qq_tool_style)
        self.qq_token_btn.clicked.connect(self._on_copy_token)
        tok_lay.addWidget(self.qq_token_btn)
        self.qq_token_row.hide()

        btn_row.addStretch(0)
        self.preview_layout.addWidget(self.qq_token_row)
        self.preview_layout.addWidget(self.qq_tools_row)
        self.preview_layout.addLayout(btn_row)
        # 立绘相关入口在「🐾 桌宠管理」页的角色卡片上（🎨 立绘工坊 / 📂 打开文件夹）
        self._qq_btn_visible = qq_enabled
        # 恢复逻辑在按钮事件 connect 之后注册一次(在 __init__ 后段或事件处)
        self.napcat_relogin_done.connect(self._on_napcat_relogin_done)

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
                border-radius: {btn_radius()}px;
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

        # 人脸库管理页（添加/删除主人与他人照片；识别参数在 插件 → 人脸识别 → 设置）
        from .widgets import PCLFaceManager
        self.face_page = PCLFaceManager()
        self.stack.addWidget(self.face_page)

        # 记忆管理页（分仓记忆 + 共享记忆清理 + 微信登录入口）
        self.memory_page = PCLMemoryManager()
        # 记忆页「微信登录」入口 → 主窗口统一执行清凭据+重启扫码
        try:
            self.memory_page.wechat_relogin_requested.connect(self._on_wechat_relogin_clicked)
        except Exception:
            pass
        self.stack.addWidget(self.memory_page)

        # 桌宠管理页（多桌宠：设为活动/添加/删除/打开文件夹）
        self.pet_page = PCLPetManager()
        self.stack.addWidget(self.pet_page)

        # 提示词编辑器页
        self.prompt_page = PCLPromptEditor()
        self.stack.addWidget(self.prompt_page)

        # 插件管理页（QQ 新增功能统一管控：启用/停用/导入/删除/打开位置）
        from .plugins_panel import PCLPluginsPanel
        self.plugins_page = PCLPluginsPanel()
        self.plugins_page.plugin_toggled.connect(self._on_plugin_toggled)
        self.stack.addWidget(self.plugins_page)

        # 主题目录页（内置/自定义主题切换、导入导出、主题色切换）
        from .themes_panel import PCLThemesPanel
        self.themes_page = PCLThemesPanel()
        self.themes_page.theme_applied.connect(self._on_theme_applied)
        self.themes_page.accent_changed.connect(self._start_color_anim)
        self.stack.addWidget(self.themes_page)

        # 人脸库导航显隐：跟随「人脸识别」插件启用状态（停用则隐藏顶部目录）
        try:
            from .plugins_panel import scan_plugins as _sp, is_enabled as _pe
            _face = next((p for p in _sp() if p.get("id") == "face"), None)
            self._apply_face_nav(_face is not None and _pe(_face))
        except Exception:
            pass

        # 主题角落装饰（如散落樱花）：置于内容层之上但穿透鼠标
        self._corner_decor = None
        try:
            _cp = corner_decor_path()
            if _cp:
                self._corner_decor = QLabel(self.pan_back)
                _pix = QPixmap(_cp)
                self._corner_decor.setPixmap(_pix)
                self._corner_decor.setFixedSize(_pix.size())
                self._corner_decor.setAttribute(Qt.WA_TransparentForMouseEvents)
                self._corner_decor.show()
                self._place_corner_decor()
        except Exception:
            pass
        self._update_background()

    def _apply_silicon_ui(self):
        """新主题 silicon：亚克力模糊 + Win11 圆角 + 深色标题栏"""
        try:
            from .colors import current_theme_id
            if current_theme_id() != "silicon":
                return
            from . import silicon_ui
            ok = silicon_ui.apply_acrylic(self)
            print(f"[PCL] 亚克力窗口效果: {'已启用' if ok else '不可用（回退纯色）'}")
            # 顶部导航胶囊化
            try:
                from .colors import ACCENT_ID, THEME_COLORS
                acc = THEME_COLORS.get(str(ACCENT_ID), {}).get("title_start", "#4c8dff")
                for b in (self.titlebar.btn_model, self.titlebar.btn_settings,
                          self.titlebar.btn_memory, self.titlebar.btn_pets,
                          self.titlebar.btn_prompt, self.titlebar.btn_plugins,
                          self.titlebar.btn_themes):
                    b.setStyleSheet(silicon_ui.nav_pill_qss(accent=acc))
            except Exception as _e:
                print(f"[PCL] 导航胶囊化失败: {_e}")
        except Exception as e:
            print(f"[PCL] ⚠ Silicon 界面应用失败: {e}")

    def _place_corner_decor(self):
        """角落装饰贴右下（内容层之上）"""
        if getattr(self, "_corner_decor", None) is None:
            return
        try:
            w = self._corner_decor.width()
            h = self._corner_decor.height()
            x = self.pan_back.width() - w - int(10 * S)
            y = self.pan_back.height() - h - int(10 * S)
            self._corner_decor.move(x, y)
            self._corner_decor.raise_()
        except Exception:
            pass

    def _on_plugin_toggled(self, plugin_id, enabled):
        """插件开关联动：人脸识别停用 → 隐藏顶部「人脸」目录"""
        try:
            _log = os.path.join(_app_base_dir(), "data", "launcher_ui.log")
            os.makedirs(os.path.dirname(_log), exist_ok=True)
            with open(_log, "a", encoding="utf-8") as f:
                import datetime as _dt
                f.write(f"{_dt.datetime.now():%H:%M:%S} plugin_toggled {plugin_id} -> {enabled}\n")
        except Exception:
            pass
        if plugin_id == "face":
            self._apply_face_nav(bool(enabled))

    def _on_theme_applied(self, theme_id):
        """主题已写入 config：重启启动器让新配色生效（先拉起新进程再关闭自己）"""
        print(f"[PCL] 应用主题 {theme_id}，重启启动器...")
        try:
            import subprocess as _sp
            if getattr(sys, "frozen", False):
                _sp.Popen([sys.executable])
            else:
                _py = _find_python(_app_base_dir())
                _sp.Popen([_py, os.path.join(_app_base_dir(), "run_launcher.py")],
                          cwd=_app_base_dir())
        except Exception as e:
            print(f"[PCL] 重启失败（请手动重新打开启动器）: {e}")
            return
        QTimer.singleShot(500, self._start_fade_close)

    def _apply_face_nav(self, show: bool):
        """控制「人脸」导航按钮显隐；隐藏时若正停留人脸页则切回模型页"""
        try:
            self.titlebar.set_face_nav_visible(bool(show))
            print(f"[PCL] 人脸导航 {'显示' if show else '隐藏'}")
        except Exception as e:
            print(f"[PCL] 人脸导航切换异常: {e}")
        if not show and getattr(self, "face_page", None) is not None:
            try:
                if self.stack.currentWidget() is self.face_page:
                    self.stack.setCurrentIndex(0)
            except Exception:
                pass

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
                        color: white; border: 2px solid rgba(255,255,255,0.5); font-size: {int(14*S)}px; font-weight: bold;
                        font-family: 'Microsoft YaHei'; border-radius: {int(14*S)}px; }}
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
                color: white; border: 2px solid rgba(255,255,255,0.5); font-size: {int(14*S)}px; font-weight: bold;
                border-radius: {int(14*S)}px; }}
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

    def _set_qq_tools_visible(self, on: bool):
        """QQ AIpet 运行中才显示 NapCat 工具按钮"""
        try:
            if getattr(self, "qq_tools_row", None) is not None:
                self.qq_tools_row.setVisible(bool(on))
            if getattr(self, "qq_token_row", None) is not None:
                self.qq_token_row.setVisible(bool(on))
        except Exception:
            pass

    def _napcat_webui_url(self) -> str:
        try:
            import json as _json
            base = _app_base_dir()
            with open(os.path.join(base, "NapCat.Shell.Windows.OneKey", "NapCat",
                                   "config", "webui.json"), "r", encoding="utf-8") as f:
                tok = (_json.load(f) or {}).get("token", "")
            if not tok:
                tok = "6bb2d3cc74ea"
            return f"http://127.0.0.1:6099/webui?token={tok}"
        except Exception:
            return "http://127.0.0.1:6099/webui?token=6bb2d3cc74ea"

    def _on_copy_token(self):
        """复制 WebUI Token 到剪贴板，并短暂提示"""
        try:
            tok = self._napcat_token()
            if not tok:
                tok = "6bb2d3cc74ea"
            from PyQt5.QtWidgets import QApplication
            QApplication.clipboard().setText(tok)
            self.qq_token_btn.setText("  ✅ 已复制 Token")
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(2000, lambda: self.qq_token_btn.setText("  📋 复制 NapCat Token"))
            print("[PCL] Token 已复制到剪贴板")
        except Exception as e:
            print(f"[PCL] 复制失败: {e}")

    def _on_napcat_webui(self):
        try:
            import webbrowser
            webbrowser.open(self._napcat_webui_url())
        except Exception as e:
            print(f"[PCL] 打开 NapCat 配置失败: {e}")




    def _on_napcat_relogin(self):
        """强制重启 NapCat：杀进程→重新启动→等待自动登录→未登录则弹二维码+提示"""
        if getattr(self, "_napcat_relogin_busy", False):
            return
        self._napcat_relogin_busy = True
        self.qq_relogin_btn.setEnabled(False)
        self.qq_relogin_btn.setText("  ⏳ 正在重启 NapCat...")
        import threading as _th
        _th.Thread(target=self._napcat_relogin_worker, daemon=True).start()

    def _on_napcat_relogin_done(self, ok: bool):
        """扫码重启线程结束回调(主线程)"""
        self._napcat_relogin_busy = False
        self.qq_relogin_btn.setEnabled(True)
        self.qq_relogin_btn.setText("  🔄 重新扫码登录 NapCat")
        if not ok:
            msg = "NapCat 重启失败" + chr(10) + "请检查后重试，或查看启动器日志。"
            self._show_config_dialog(msg)


    def _napcat_relogin_worker(self):
        """后台线程：杀 NapCat → 重启 → 高频探测(3001就绪≈自动登录成功；
        cache/qrcode.png 更新≈QQ 已出码需扫码 → 立即弹码，不再干等)。
        全流程打印日志；无论成功失败都通过信号恢复按钮。"""
        import subprocess as _sp
        import socket as _sock
        import time as _time
        base = _app_base_dir()
        _done = [False]
        qr_path = os.path.join(base, "NapCat.Shell.Windows.OneKey",
                               "NapCat", "cache", "qrcode.png")

        def _finish(ok):
            if _done[0]:
                return
            _done[0] = True
            try:
                self.napcat_relogin_done.emit(bool(ok))
            except Exception:
                pass

        def _qr_mtime():
            try:
                return os.path.getmtime(qr_path)
            except Exception:
                return 0.0

        try:
            print("[PCL] 🔄 重新扫码登录：停止旧 NapCat...")
            _sp.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-CimInstance Win32_Process | Where-Object { "
                 "$_.Name -eq 'NapCatWinBootMain.exe' -or "
                 "($_.Name -eq 'QQ.exe' -and $_.ExecutablePath -like 'D:\QQ\*') } | "
                 "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"],
                capture_output=True, timeout=25,
                creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0))
            _time.sleep(4)
            nc_dir = os.path.join(base, "NapCat.Shell.Windows.OneKey", "NapCat")
            logf = os.path.join(base, "tmp", "napcat_manual.log")
            _sp.Popen(["cmd.exe", "/c", "launcher-user.bat"], cwd=nc_dir,
                      creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0),
                      stdout=open(logf, "wb"), stderr=_sp.STDOUT)
            print("[PCL] 🔄 NapCat 已重新启动，等待登录(3001就绪 / 出码即弹)...")
        except Exception as e:
            print(f"[PCL] ⚠ NapCat 启动失败: {e}")
            _finish(False)
            return

        def _port_ready():
            try:
                with _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM) as sd:
                    sd.settimeout(2)
                    return sd.connect_ex(("127.0.0.1", 3001)) == 0
            except Exception:
                return False

        # 出码基准：启动前的码文件时间（旧码不算数）
        qr_base = _qr_mtime()
        # 阶段1：最多 70s，每 1.2s 探测；一旦检测到新码立刻弹，不等自动登录超时
        dl = _time.time() + 70
        waited = 0
        while _time.time() < dl:
            if _port_ready():
                print(f"[PCL] ✅ NapCat 已恢复(自动登录成功，耗时约 {waited}s)")
                _finish(True)
                return
            if _qr_mtime() != qr_base and _qr_mtime() > 0:
                # QQ 已出新码 → 立即弹码，进入扫码等待阶段
                print(f"[PCL] 🔄 检测到新二维码(约 {waited}s)，弹出提示...")
                self._prompt_scan_ui(force=True)
                break
            _time.sleep(1.2)
            waited += 1.2
        else:
            # 70s 内既没自动登录也没出码：异常，弹一次码提示兜底
            print("[PCL] 🔄 70s 内未见新码，弹出提示（兜底）...")
            self._prompt_scan_ui(force=True)
        # 阶段2：扫码等待，最多 5 分钟。码文件更新→重开新图；弹窗由 _prompt_scan_ui 45s 节流
        print("[PCL] 🔄 等待扫码(5分钟上限)...")
        last_qr = _qr_mtime()
        dl2 = _time.time() + 300
        while _time.time() < dl2:
            _time.sleep(4)
            if _port_ready():
                print("[PCL] ✅ 扫码登录成功，NapCat 已恢复")
                _finish(True)
                return
            m = _qr_mtime()
            if m > 0 and m != last_qr:
                last_qr = m
                print("[PCL] 🔄 二维码已刷新，重开新图...")
                self._prompt_scan_ui()
        print("[PCL] ⚠ 等待扫码超时(5分钟)，NapCat 仍未登录")
        _finish(False)

    def _napcat_token(self) -> str:
        try:
            import json as _json
            with open(os.path.join(_app_base_dir(), "NapCat.Shell.Windows.OneKey",
                                   "NapCat", "config", "webui.json"),
                      "r", encoding="utf-8") as f:
                return str((_json.load(f) or {}).get("token") or "")
        except Exception:
            return ""

    def _prompt_scan_ui(self, force=False):
        """打开二维码图片 + 系统弹窗提示扫码（线程内可调用）。
        force=True 时立即提示（不限节流）；否则 MessageBox 弹窗节流 45 秒。"""
        try:
            import subprocess as _sp
            import time as _time
            now = _time.time()
            last = getattr(self, "_last_scan_prompt_ts", 0.0)
            qr = os.path.join(_app_base_dir(), "NapCat.Shell.Windows.OneKey",
                              "NapCat", "cache", "qrcode.png")
            if not os.path.exists(qr):
                return False
            # 图片每次调用都重新打开（跟随码刷新）；弹窗 45s 节流防刷屏
            _sp.Popen(["cmd.exe", "/c", "start", "", qr],
                      creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0))
            if force or now - last >= 45:
                self._last_scan_prompt_ts = now
                _sp.run(
                    ["powershell", "-NoProfile", "-Command",
                     "Add-Type -AssemblyName System.Windows.Forms;"
                     "[System.Windows.Forms.MessageBox]::Show("
                     "'QQ 需要重新扫码授权：已打开最新二维码图片，请用手机QQ扫码。"
                     "若图片过期，等待提示再次弹出即可获得更新后的二维码。',"
                     "'QQ 需重新扫码')"],
                    capture_output=True, timeout=15,
                    creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0))
                print("[PCL] 已提示扫码")
            return True
        except Exception as e:
            print(f"[PCL] 扫码提示失败: {e}")
            return False

    def _kill_qq_process(self):
        """关闭 QQ AIpet 进程。
        除启动器跟踪的进程外，还兜底清理从本目录启动的所有 run_qq.py 残留实例
        （多开/历史残留会导致"关了还在回话/抢消息"，一并清掉）。
        NapCat 若由本启动器本次会话拉起（_napcat_started_by_us），连同其
        控制台窗口进程树一起关闭，避免"关了 QQ AIpet 还留着 NapCat 窗口"。"""
        if self._qq_process is not None:
            self._kill_process(self._qq_process)
            self._qq_process = None
        self._set_qq_tools_visible(False)
        try:
            self._kill_stray_run_qq(_app_base_dir())
        except Exception:
            pass
        self._kill_napcat_if_ours()

    def _kill_napcat_if_ours(self):
        """关闭由本启动器拉起的 NapCat（start_napcat.bat 控制台及其进程树）。

        仅在 _napcat_started_by_us 为 True（NapCat 由本启动器这次会话拉起）时动作，
        用户手动启动的 NapCat 保留不动。
        ① 优先按保存的 Popen 句柄用 taskkill /T 树杀（cmd → NapCatWinBootMain → QQ 全家）；
        ② 句柄丢失/已退出但 NapCat 还在 → 按本绿色版目录特征兜底清理主进程。"""
        if not getattr(self, "_napcat_started_by_us", False):
            return
        self._napcat_started_by_us = False
        proc = getattr(self, "_napcat_proc", None)
        if proc is not None:
            self._napcat_proc = None
            try:
                if proc.poll() is None:
                    import subprocess as _sp
                    _sp.run(
                        ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                        capture_output=True, timeout=10,
                        creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0),
                    )
                    print("[PCL] ✅ 已随 QQ AIpet 关闭 NapCat（含控制台窗口）")
                    return
            except Exception:
                pass
        # 兜底：按目录特征清理本绿色版目录内的 NapCat 主进程（不影响别处安装的 QQ/NapCat）
        try:
            import subprocess as _sp
            base = _app_base_dir()
            base_esc = base.replace("'", "''")
            ps_cmd = (
                "Get-CimInstance Win32_Process | Where-Object { "
                "$_.ExecutablePath -like '" + base_esc + "*' -and "
                "($_.Name -eq 'NapCatWinBootMain.exe' -or "
                "($_.Name -eq 'QQ.exe' -and "
                "$_.ExecutablePath -like '*NapCat.Shell.Windows.OneKey\\bootmain*')) } | "
                "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
            )
            _sp.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                capture_output=True, timeout=15,
                creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0),
            )
            print("[PCL] ✅ NapCat 兜底进程清理完成")
        except Exception as e:
            print(f"[PCL] ⚠ NapCat 关闭失败: {e}")

    @staticmethod
    def _kill_stray_run_qq(base: str):
        """终止所有从本绿色版目录启动的 run_qq.py python 进程（按可执行路径+命令行过滤）"""
        try:
            import subprocess as _sp
            base_esc = base.replace("'", "''")
            ps_cmd = (
                "Get-CimInstance Win32_Process | Where-Object { "
                "$_.Name -match '^python(w)?\\.exe$' -and "
                "$_.ExecutablePath -like '" + base_esc + "*' -and "
                "$_.CommandLine -like '*run_qq.py*' } | "
                "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
            )
            _sp.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                capture_output=True, timeout=15,
                creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            pass

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
    def _desktop_qq_running() -> bool:
        """检测桌面正式版 QQ(非 NapCat bootmain)是否在运行。
        NapCat 注入模式与正式版 QQ 共用数据目录，两者不能同时启动。"""
        try:
            import subprocess as _sp
            r = _sp.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-CimInstance Win32_Process -Filter \"Name='QQ.exe'\" | "
                 "Where-Object { $_.ExecutablePath -notlike '*NapCat.Shell.Windows.OneKey*' } | "
                 "Measure-Object | Select-Object -ExpandProperty Count"],
                capture_output=True, text=True, timeout=10,
                creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0),
            )
            return r.stdout.strip() not in ("", "0")
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
        # ⚠ 先清理残留的旧 run_qq.py 实例：旧实例可能还带着过期的 WS token 在空转重连，
        #   不清掉会出现「同时跑好几个实例」「同一条消息被回复多次」（用户反馈过）。
        try:
            self._kill_stray_run_qq(base)
        except Exception as _e:
            print(f"[PCL] ⚠ 清理残留 QQ 实例失败（继续启动）: {_e}")
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
        # 关键：等待 NapCat 期间按钮被禁用，这里必须恢复可用，
        # 否则 run_qq 启动后按钮仍为灰色 → 用户无法点击"关闭 QQ AIpet"（历史 bug）
        self.qq_btn.setEnabled(True)
        self.qq_btn.setText("  ⏹ 关闭 QQ AIpet")
        # QQ AIpet 已运行 → 显示 NapCat 工具按钮
        self._set_qq_tools_visible(True)
        self.qq_btn.setStyleSheet(f"""
            QPushButton {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 #e03030,stop:1 #f06060);
                color: white; border: 2px solid rgba(255,255,255,0.5); font-size: {int(14*S)}px; font-weight: bold;
                border-radius: {int(14*S)}px; }}
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

        # 2a. 桌面正式版 QQ(9.9.30)正在运行会与 NapCat(注入同一 9.9.30)互斥
        #     → 提示用户先关闭正式版 QQ（主人号用手机 QQ）
        if self._desktop_qq_running():
            self._show_config_dialog(
                "检测到正式版 QQ 正在运行\n\n"
                "NapCat 需要独占 QQ 9.9.30 才能自动登录（免扫码）。\n"
                "请先关闭桌面正式版 QQ，再点击启动。\n"
                "（主人号可在手机 QQ 上正常使用，不受影响）")
            return

        # 2b. 注入正式版 QQ 9.9.30（NapCat 4.18.19 配套版本：登录态正常落盘，
        #      重启自动快速登录、无需扫码；9.9.33 独立版不支持登录持久化）
        napcat_bat = os.path.join(base, "NapCat.Shell.Windows.OneKey", "NapCat", "launcher-user.bat")
        if not os.path.exists(napcat_bat):
            print(f"[PCL] ⚠ 未找到 NapCat 启动脚本: {napcat_bat}")
            self._show_config_dialog("NapCat 未安装")
            return

        print(f"[PCL] NapCat 未运行，正在自动启动: {napcat_bat}")
        try:
            self._napcat_proc = subprocess.Popen(
                [napcat_bat],
                cwd=os.path.dirname(napcat_bat),
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            # 记录 NapCat 由本启动器拉起 → 关闭 QQ AIpet 时连带关闭（含控制台窗口）
            self._napcat_started_by_us = True
        except Exception as e:
            print(f"[PCL] ⚠ 启动 NapCat 失败: {e}")
            self._napcat_proc = None
            self._napcat_started_by_us = False
            self._show_config_dialog("NapCat 启动失败")
            return

        # 等待期间：禁用按钮 + 更新文字，防止重复点击
        self.qq_btn.setEnabled(False)
        self.qq_btn.setText("  ⏳ 等待 NapCat...（自动登录中）")

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
        # 正在等待 NapCat 就绪时再次点击 → 取消等待
        # （NapCat 窗口保留给用户手动接管；此后不再由本启动器负责连带关闭）
        if getattr(self, "_napcat_wait_running", False):
            print("[PCL] 已取消等待 NapCat（NapCat 窗口保持运行，再点一次即可直接启动 QQ AIpet）")
            try:
                self._napcat_wait_timer.stop()
            except Exception:
                pass
            self._napcat_wait_running = False
            self._napcat_wait_elapsed = 0
            self._napcat_started_by_us = False  # 用户接管 NapCat，关闭 QQ 时不再连带关闭
            self._napcat_proc = None
            self.qq_btn.setEnabled(True)
            self.qq_btn.setText("  💬 启动 QQ AIpet")
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
                    color: white; border: 2px solid rgba(255,255,255,0.5); font-size: {int(14*S)}px; font-weight: bold;
                    font-family: 'Microsoft YaHei'; border-radius: {int(14*S)}px; }}
            """)
            return

        # 检查子进程解释器可用（QQ 本体由 run_qq.py 子进程运行，
        # websocket-client 由该进程的 Python 环境提供；壳自身无需打包）
        if not _find_python(_app_base_dir()):
            self._show_config_dialog("未找到 Python 解释器")
            return

        # 异步确保 NapCat 运行（不阻塞 UI）
        self._ensure_napcat_async()

    # ===== 微信 ClawBot =====
    def _on_wechat_clicked(self):
        """启动/关闭微信 ClawBot AIpet（无外部服务，直接拉起 run_wechat.py）"""
        if self._wechat_process is not None:
            self._kill_wechat_process()
            self._wechat_pet_id = None
            self._wechat_btn_styled(False)
            return
        base = _app_base_dir()
        py = _find_python(base)
        if not py:
            self._show_config_dialog("未找到 Python 解释器")
            return
        try:
            from pets.pet_registry import get_active_pet_id
            self._wechat_pet_id = get_active_pet_id()
        except Exception:
            self._wechat_pet_id = None
        self._wechat_process = subprocess.Popen(
            [py, os.path.join(base, "run_wechat.py")],
            cwd=base,
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        self._wechat_btn_styled(True)
        print(f"[PCL] 已启动微信 AIpet（角色: {self._wechat_pet_id}）")

    def _kill_wechat_process(self):
        """关闭微信 ClawBot AIpet 进程"""
        if self._wechat_process is None:
            return
        self._kill_process(self._wechat_process)
        self._wechat_process = None

    def _on_wechat_relogin_clicked(self):
        """手动重新登录微信：停进程 → 清本地凭据/游标/待处理收件箱 → 重启 run_wechat 走扫码。

        适用：手机端换绑/登出后电脑版仍显示已连接（旧凭据作废）；
        或 token 失效需重新扫码时，不必手动去删 data/wechat_credentials.json。
        """
        base = _app_base_dir()
        py = _find_python(base)
        if not py:
            self._show_config_dialog("未找到 Python 解释器")
            return
        # 1. 关闭正在运行的微信进程（若在跑）
        if self._wechat_process is not None:
            self._kill_wechat_process()
            self._wechat_pet_id = None
            self._wechat_btn_styled(False)
            print("[PCL] 已关闭微信 AIpet，准备重新登录")
        # 2. 清除本地登录态（凭据 / 游标 / context_token / 待处理收件箱 / 旧二维码）
        from tool.paths import data_path
        cleared = []
        for rel in ("wechat_credentials.json", "wechat_sync_buf.txt",
                    "wechat_context_tokens.json", "wechat_pending.json",
                    "wechat_qrcode.png"):
            p = data_path("data", rel)
            try:
                if os.path.exists(p):
                    os.remove(p)
                    cleared.append(rel)
            except Exception as e:
                print(f"[PCL] 清除 {rel} 失败: {e}")
        print(f"[PCL] 已清除微信登录态：{', '.join(cleared) if cleared else '无残留'}")
        # 3. 重启 → run_wechat 检测无凭据 → 自动弹二维码扫码登录
        try:
            from pets.pet_registry import get_active_pet_id
            self._wechat_pet_id = get_active_pet_id()
        except Exception:
            self._wechat_pet_id = None
        self._wechat_process = subprocess.Popen(
            [py, os.path.join(base, "run_wechat.py")],
            cwd=base,
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        self._wechat_btn_styled(True)
        print("[PCL] 微信 AIpet 已重启（新控制台将弹出二维码，请用手机扫码登录）")

    def _wechat_btn_styled(self, running):
        """微信按钮样式切换（启动绿 / 关闭红）"""
        if running:
            self.wechat_btn.setText("  ⏹ 关闭微信 AIpet")
            self.wechat_btn.setStyleSheet(f"""
                QPushButton {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #e03030,stop:1 #f06060);
                    color: white; border: 2px solid rgba(255,255,255,0.5); font-size: {int(14*S)}px; font-weight: bold;
                    border-radius: {int(14*S)}px; }}
            """)
        else:
            self.wechat_btn.setText("  💬 启动微信 AIpet")
            self.wechat_btn.setStyleSheet(f"""
                QPushButton {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {THEME_COLORS['green']['btn_start']},stop:1 {THEME_COLORS['green']['btn_end']});
                    color: white; border: 2px solid rgba(255,255,255,0.5); font-size: {int(14*S)}px; font-weight: bold;
                    font-family: 'Microsoft YaHei'; border-radius: {int(14*S)}px; }}
                QPushButton:hover {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {THEME_COLORS['green']['btn_end']},stop:1 {THEME_COLORS['green']['btn_start']}); }}
            """)

    def closeEvent(self, event):
        """关闭窗口时终止视频背景解码线程并一并结束桌宠与 QQ/微信进程"""
        if getattr(self, "_bg_reader", None) is not None:
            try:
                self._bg_reader.stop()
            except Exception:
                pass
        self._kill_pet_process()
        self._kill_qq_process()
        self._kill_wechat_process()
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
        # 圆角底：主题有壁纸时几乎透明（仅兜住边缘防露桌面）；无壁纸时接近纯白
        try:
            _has_bg = bool(background_info()[0])
        except Exception:
            _has_bg = False
        painter.fillRect(r, QColor(255, 255, 255, 200 if _has_bg else 255))

    def _switch_page(self, index):
        # 如果正在动画中，直接切页面，跳过动画
        if self._animating:
            self.stack.setCurrentIndex(index)
            try:
                if getattr(self, "nav_rail", None) is not None:
                    self.nav_rail.set_active(index)
            except Exception:
                pass
            return
        self._fade_page_out(lambda: self._do_switch(index))

    def _do_switch(self, index):
        self.stack.setCurrentIndex(index)
        # 仅「模型」页保留左侧模型列表；其余页面隐藏列表 →
        # 页面占满全宽，与顶部目录条同宽（桌宠/提示词等不再短一截）
        try:
            self.sidebar.setVisible(index == 0)
        except Exception:
            pass
        self._fade_page_in()

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
        dlg.setStyleSheet(f"background: rgba(255,255,255,150); border: 1px solid {Color5.name()}; border-radius: 12px;")
        layout = QVBoxLayout(dlg); layout.setContentsMargins(int(24*S), int(20*S), int(24*S), int(16*S)); layout.setSpacing(int(10*S))
        title = QLabel(f"  {feature_name} 未启用")
        title.setStyleSheet(f"color: {Color1.name()}; font-size: {int(15*S)}px; font-weight: bold; font-family: 'Microsoft YaHei'; border: none;")
        body = QLabel("该功能在 config.json 中被设为 false，\n请修改配置后重启桌宠。")
        body.setStyleSheet(f"color: {Gray2.name()}; font-size: {int(12*S)}px; font-family: 'Microsoft YaHei'; border: none;")
        btn = QPushButton("  确定  ")
        btn.setStyleSheet(f"QPushButton {{ background: {Color3.name()}; color: white; border: none; padding: {int(8*S)}px {int(32*S)}px; font-size: {int(13*S)}px; border-radius: {btn_radius()}px; font-family: 'Microsoft YaHei'; }} QPushButton:hover {{ background: {Color4.name()}; }}")
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
        self.pan_back.setGeometry(0, 0, self.width(), self.height())
        self._update_background()
        self._place_corner_decor()