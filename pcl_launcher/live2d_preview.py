# -*- coding: utf-8 -*-
"""Live2D 预览控件（从旧版主窗口 Live2DPreviewWidget 原样抽出）。

立绘工坊用它预览 Live2D 角色（与桌宠同一套渲染：live2d.v3 + OpenGL）。
不依赖旧版主窗口，可独立实例化：Live2DPreviewWidget(model_json_path, parent)。
"""
import os
import math

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap, QSurfaceFormat, QColor, QPainter
from PyQt5.QtWidgets import (QOpenGLWidget, QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton)

# ⚠ 从旧版主窗口抽出来时漏了 colors 里的常量（PREVIEW_BG 等）→ initializeGL 抛 NameError
#   → 预览一直是空白/透明（这就是「Live2D 显示不出来」的真正原因）
from .colors import *            # noqa: F401,F403
from .colors import background_info, PREVIEW_BG   # noqa: F401


# ══════════ 日志（冻结版没有控制台 → 写到 tmp/live2d_window.log，方便排查）══════════
_L2D_INITED = False      # Cubism 的 init/glInit 一个进程只能做一次


def _l2d_log(msg: str):
    try:
        import time as _t
        import sys as _s
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if getattr(_s, "frozen", False):
            base = os.path.dirname(_s.executable)
        d = os.path.join(base, "tmp")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "live2d_window.log"), "a", encoding="utf-8") as f:
            f.write("[" + _t.strftime("%m-%d %H:%M:%S") + "] " + str(msg) + chr(10))
    except Exception:
        pass


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

    def _rebuild_model_in_ctx(self):
        """在**当前（控件的）GL 上下文里**创建模型 + 渲染器。

        ⚠ 为什么必须这样：Cubism 的 `LAppModel.LoadModelJson()` 会 `CreateRenderer()`，
        即把贴图/遮罩等 GL 资源建到「调用时的当前上下文」里。
        旧写法在普通槽函数里直接 LoadModelJson（那时当前上下文不是控件的上下文）→
        资源建错地方 → 第二次打开画面异常（看着像被拉伸/错乱）。
        所以在调用前必须 `makeCurrent()`，或在 paintGL 里（上下文天然是当前的）调用。
        """
        try:
            if not (self._model_path and os.path.exists(self._model_path)):
                self._failed = True
                return False
            import live2d.v3 as l2d
            p = os.path.normpath(os.path.abspath(self._model_path)).replace("\\", "/")
            if self.model is not None:
                try:
                    self.model.DestroyRenderer()      # 释放上一个模型的 GL 资源
                except Exception:
                    pass
                self.model = None
            m = l2d.LAppModel()
            m.LoadModelJson(p)
            self.model = m
            self._apply_transform()
            w, h = max(1, self.width()), max(1, self.height())
            m.Resize(w, h)
            self._last_vp = (w, h)
            self._t = 0.0
            self._render_ready = True
            self._failed = False
            self._model_ctx_ref = self.context()      # 记住资源所属的上下文
            return True
        except Exception as e:
            self._failed = True
            _l2d_log("模型创建失败: " + repr(e))
            print(f"[PCL] Live2D 模型创建失败: {e}")
            return False

    def initializeGL(self):
        global _L2D_INITED
        try:
            from OpenGL.GL import (
                glEnable, GL_BLEND, GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA,
                glBlendFunc, glClearColor, glClear, GL_COLOR_BUFFER_BIT
            )
            import live2d.v3 as l2d
            # ⚠ Cubism 的 init/glInit 一个进程只能做一次：第二次开窗口再调就会报错/崩溃
            #   （这就是「预览第一次正常、第二次出错」的根因）
            if not _L2D_INITED:
                try:
                    l2d.init()
                except Exception as _e:
                    _l2d_log(f"l2d.init 异常（忽略）: {_e}")
                l2d.glInit()
                _L2D_INITED = True
                _l2d_log("Cubism 初始化完成（本进程仅一次）")
            else:
                _l2d_log("复用已初始化的 Cubism（跳过 init/glInit）")
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            glClearColor(*self._clear_color())
            self._init_bg_shader()

            # 模型创建统一走 _rebuild_model_in_ctx（此刻上下文必然是当前上下文）
            if self._rebuild_model_in_ctx():
                _l2d_log(f"模型加载成功: {self._model_path}")
                print(f"[PCL] Live2D 模型加载成功: {self._model_path}")
            self._timer.start()
        except Exception as e:
            self._failed = True
            import traceback as _tb
            _l2d_log("控件初始化失败: " + repr(e) + " | " + _tb.format_exc()[:900])
            print(f"[PCL] Live2D init 失败: {e}")

    def reload_model(self, path: str):
        """按「全新加载」的方式重建模型（用于复用窗口时切换模型）。

        ⚠ 两个关键点（缺一个都会导致「第二次打开和第一次不一样」）：
        1) 模型必须建在控件自己的 GL 上下文里 → `makeCurrent()` 包住创建过程；
        2) 视口/时间/变换全部重置 → 与第一次打开的画面完全一致。
        """
        self._model_path = path
        self._drawn_logged = False
        _cur = False
        try:
            try:
                self.makeCurrent()          # 让控件的上下文成为当前上下文
                _cur = True
            except Exception as _e:
                _l2d_log(f"makeCurrent 失败（改由 paintGL 兜底重建）: {_e}")
            ok = self._rebuild_model_in_ctx()
            if _cur:
                try:
                    self.doneCurrent()
                except Exception:
                    pass
            self.update()
            _l2d_log(f"已按全新方式重建模型（{self.width()}x{self.height()}）ok={ok}")
            print(f"[PCL] Live2D 模型已重建: {os.path.basename(str(path))} ok={ok}")
            return ok
        except Exception as e:
            self._failed = True
            _l2d_log(f"重建模型失败: {e}")
            print(f"[PCL] Live2D 模型重建失败: {e}")
            return False

    def load_model(self, path: str):
        """换模型（与 reload_model 同一条稳健路径）"""
        return self.reload_model(path)

    def set_display(self, scale=None, offset_x=None, offset_y=None):
        """热改缩放/位移（换角色时用：同一个 GL 上下文里换模型 + 换显示参数）。"""
        try:
            if scale is not None:
                self._model_scale = float(scale)
            if offset_x is not None:
                self._offset_x = float(offset_x)
            if offset_y is not None:
                self._offset_y = float(offset_y)
            if self.model is not None:
                self.model.SetScale(self._model_scale)
                self.model.SetOffset(self._offset_x, self._offset_y)
            self.update()
            return True
        except Exception as e:
            _l2d_log(f"set_display 失败: {e}")
            return False

    def paintGL(self):
        try:
            from OpenGL.GL import glClearColor, glClear, GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT
            # ⚠ 预览必须“不透明”：主题没壁纸时 alpha 会让整块看着是透明的（模型像没显示）
            _cc = list(self._clear_color())
            if len(_cc) == 4:
                _cc[3] = 1.0
            else:
                _cc = [0.13, 0.13, 0.16, 1.0]
            glClearColor(*_cc)
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
        # ★ 先铺一层不透明底色：即使模型没画出来，也能看到一块面板
        #   （避免"窗口一片透明像没显示"）
        try:
            from OpenGL.GL import (glMatrixMode, glLoadIdentity, glOrtho,
                                   glBegin, glVertex2f, glColor4f, glEnd, GL_QUADS,
                                   GL_PROJECTION, GL_MODELVIEW)
            glMatrixMode(GL_PROJECTION); glLoadIdentity()
            glOrtho(0, max(1, self.width()), max(1, self.height()), 0, -1, 1)
            glMatrixMode(GL_MODELVIEW); glLoadIdentity()
            glColor4f(0.12, 0.12, 0.16, 1.0)
            glBegin(GL_QUADS)
            glVertex2f(0, 0); glVertex2f(self.width(), 0)
            glVertex2f(self.width(), self.height()); glVertex2f(0, self.height())
            glEnd()
        except Exception as _e:
            _l2d_log(f"底色绘制失败: {_e}")
        # ⚠ 兜底自愈：窗口隐藏/移动后 GL 上下文可能被系统重建，
        #   此时旧模型的 GL 资源已失效（画面空白/错乱）→ 在当前上下文里重建一次。
        try:
            if self._render_ready and self.model is not None \
                    and getattr(self, "_model_ctx_ref", None) is not self.context():
                _l2d_log("GL 上下文已变化 → 在正确的上下文里重建模型")
                self._rebuild_model_in_ctx()
        except Exception as _e:
            _l2d_log(f"上下文自愈失败: {_e}")
        if not self._render_ready or self._failed:
            return
        if self.model and self._render_ready:
            try:
                self.model.Update()
                self.model.Draw()
                if not getattr(self, "_drawn_logged", False):
                    self._drawn_logged = True
                    _l2d_log(f"模型已绘制（控件 {self.width()}x{self.height()}）")
            except Exception as _e:
                _l2d_log(f"模型绘制失败: {_e}")

    def _ensure_viewport(self):
        """把模型画布尺寸对齐控件尺寸。

        ⚠ 只靠 resizeGL 不够：控件嵌在布局/堆叠容器里时，resizeGL 可能早于模型加载
        或根本不触发 → 模型按 0×0 视口绘制（表现就是「Live2D 显示不出来 / 只有一小块」）。"""
        try:
            if self.model is None or not self._render_ready:
                return
            w, h = max(1, self.width()), max(1, self.height())
            if (w, h) != getattr(self, "_last_vp", None):
                self.model.Resize(w, h)
                self._last_vp = (w, h)
        except Exception as e:
            print(f"[PCL] Live2D 画布尺寸对齐失败: {e}")

    def resizeGL(self, width, height):
        if self.model and self._render_ready:
            self.model.Resize(width, height)
            self._last_vp = (max(1, width), max(1, height))

    def _on_tick(self):
        if not self._render_ready:
            self.update()
            return
        self._ensure_viewport()          # 尺寸变了立刻对齐（否则模型会画不出/画偏）
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


# ══════════════════ 独立 Live2D 预览窗口（不透明 → GL 能正常渲染）══════════════════
# 底部工具条按钮样式：画布恒为深色（见 __init__ 的 QColor(30,30,38)），
# 所以按钮也必须恒为「浅字深底」，不能跟着主题走（浅色主题的深字会糊在深画布上）。
_BAR_BTN_QSS = """
QPushButton {
    background: rgba(255, 255, 255, 0.10); color: #eef1f7;
    border: 1px solid rgba(255, 255, 255, 0.24); border-radius: 8px;
    padding: 6px 12px; font-size: 13px;
}
QPushButton:hover { background: rgba(255, 255, 255, 0.18);
    border-color: rgba(255, 255, 255, 0.42); }
QPushButton:pressed { background: rgba(255, 255, 255, 0.06); }
QPushButton:disabled { color: rgba(255, 255, 255, 0.40); }
"""


class Live2DPreviewWindow(QWidget):
    """独立的 Live2D 实时预览窗口。

    ⚠ 为什么单独开窗口：QOpenGLWidget 放在**透明窗口**（亚克力对话框）里渲染不出来，
    旧版启动器的预览之所以正常，就是因为它在一个普通窗口里。这里同样用不透明窗口。
    """

    def __init__(self, model_json: str = "", parent=None, pet_id: str = None):
        # 置顶 + Tool 窗口：不被其它模态对话框锁住，也不会被启动器盖住
        super().__init__(parent, Qt.Tool | Qt.WindowStaysOnTopHint | Qt.WindowTitleHint
                         | Qt.WindowCloseButtonHint)
        self.setWindowModality(Qt.NonModal)
        self.setWindowTitle("Live2D 实时预览（可拖动 = 移动模型）")
        self.setAttribute(Qt.WA_TranslucentBackground, False)   # 必须不透明
        self.setAutoFillBackground(True)
        try:
            from PyQt5.QtGui import QPalette
            pal = self.palette()
            pal.setColor(QPalette.Window, QColor(30, 30, 38))
            self.setPalette(pal)
        except Exception:
            pass
        # ⚠ 画布比例与缩放必须**跟角色走**：以前固定 560x760（竖长）且 model_scale 用默认 1.0，
        #   于是方形半身模型（诺瓦 window_ratio=1.0 / scale=1.53）在竖长画布里被裁掉一截
        #   （用户报"诺瓦显示不完全，毕竟这是个正方形画布"）。
        disp = {}
        try:
            from pets.pet_registry import get_live2d_display
            disp = get_live2d_display(pet_id) or {}
        except Exception as _e:
            print(f"[Live2DPreview] ⚠ 读取角色显示参数失败（用默认比例）: {_e}")
        ratio = float(disp.get("window_ratio") or 0.67)
        ratio = min(max(ratio, 0.3), 2.0)
        _h = 760
        _w = int(_h * ratio)
        self.resize(_w, _h)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.view = Live2DPreviewWidget(
            model_json or None, self,
            model_scale=float(disp.get("scale") or 1.0),
            offset_x=float(disp.get("offset_x") or 0.0),
            offset_y=float(disp.get("offset_y") or 0.0))
        self.view.setMinimumSize(max(240, int(420 * ratio)), 420)
        lay.addWidget(self.view, 1)
        bar = QHBoxLayout()
        bar.setContentsMargins(8, 4, 8, 8)
        self.btn_reload = QPushButton("🔄 重新加载")
        self.btn_reload.clicked.connect(lambda: self.view.load_model(self._model_json) if self._model_json else None)
        self.btn_fit = QPushButton("🎯 适合窗口")
        self.btn_fit.clicked.connect(self._fit)
        for _b in (self.btn_reload, self.btn_fit):
            # ⚠ 画布是**写死的深色**（QColor(30,30,38)），而全局 QSS 给按钮的文字色是
            #   「当前主题的主文字色」——经典/千恋万花是**深色**字，压在深色画布上就成了
            #   深底 + 深字（用户报的"预览窗口左下角的字对比度低"，只剩 emoji 看得见）。
            #   这个窗口永远是深底，所以这里把底和字一起钉死，与主题无关。
            _b.setStyleSheet(_BAR_BTN_QSS)
        bar.addWidget(self.btn_reload)
        bar.addWidget(self.btn_fit)
        bar.addStretch()
        lay.addLayout(bar)
        self._model_json = model_json
        self.show()
        self.raise_()
        self.activateWindow()

    def apply_pet(self, pet_id: str = None):
        """按角色的显示参数重设画布比例 + 缩放/位移（换角色时必须调）。

        ⚠ 预览窗口是**复用**的（同一个 GL 上下文，见 open_live2d_window），
          不复用就画不出来；但复用时光换模型不够 —— 画布比例还是上一个角色的，
          方形半身模型（诺瓦）就会被裁（用户报"诺瓦显示不完全"）。
        """
        try:
            from pets.pet_registry import get_live2d_display
            disp = get_live2d_display(pet_id) or {}
            ratio = min(max(float(disp.get("window_ratio") or 0.67), 0.3), 2.0)
            h = max(420, self.height() or 760)
            self.resize(int(h * ratio), h)
            self.view.setMinimumSize(max(240, int(420 * ratio)), 420)
            self.view.set_display(disp.get("scale"), disp.get("offset_x"), disp.get("offset_y"))
            _l2d_log("按角色调整画布：pet=%s ratio=%.2f scale=%s"
                     % (pet_id, ratio, disp.get("scale")))
            return True
        except Exception as e:
            _l2d_log(f"apply_pet 失败: {e}")
            return False

    def _fit(self):
        try:
            self.view.resize(self.view.width() + 1, self.view.height() + 1)
            self.view._ensure_viewport()
            self.view.update()
        except Exception:
            pass

    def set_model(self, model_json: str):
        self._model_json = model_json
        try:
            if model_json and os.path.exists(model_json):
                # 先让窗口可见（QOpenGLWidget 只有活着才有 GL 上下文）→ 再换模型
                self.show()
                self.view.reload_model(model_json)
        except Exception as e:
            _l2d_log(f"切换模型失败: {e}")
            print(f"[Live2DWindow] ⚠ 切换模型失败: {e}")


_WINDOWS = []


def open_live2d_window(model_json: str = "", parent=None, pet_id: str = None) -> "Live2DPreviewWindow":
    """打开（或复用）Live2D 实时预览窗口；失败返回 None。

    `pet_id`：按这个角色的显示参数调整画布比例与缩放（方形半身模型不会被裁）。
    """
    try:
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        # ⚠ 不再关闭调试器窗口：以前以为"两个 Live2D 画布会互相抢引擎"，其实根因是各画布
        #   用了各自的 GL 上下文；入口打开 Qt 的共享上下文开关后（enable_shared_gl_contexts）
        #   预览窗口与调试器能并排渲染（实测 probe_l2d_two_canvases.py）。
        #   用户拍板允许同时开着 → 这里不关任何窗口。
        # ★ 关键：**复用同一个窗口/同一个 QOpenGLWidget**。
        #   Cubism 的 glInit 是绑定在「当前 GL 上下文」上的；每新建一个 QOpenGLWidget
        #   就是换了一个上下文 → 引擎在那个上下文里没初始化 → 第二/第三次打开就画不出来。
        for w in list(_WINDOWS):
            try:
                if w is not None:
                    if model_json and os.path.exists(model_json):
                        w.set_model(model_json)      # 同一上下文里换模型（安全）
                    w.apply_pet(pet_id)              # 同一上下文里换显示参数（比例/缩放）
                    w.show()
                    w.raise_()
                    w.activateWindow()
                    _l2d_log(f"复用预览窗口（同一 GL 上下文）：{model_json} pet={pet_id}")
                    return w
            except Exception as _e:
                _l2d_log(f"复用失败，改为新建：{_e}")
        win = Live2DPreviewWindow(model_json, parent, pet_id=pet_id)
        _WINDOWS.append(win)
        _l2d_log(f"已打开实时预览窗口：{model_json}")
        print(f"[Live2DWindow] 已打开实时预览窗口（不透明）：{os.path.basename(model_json or '')}")
        return win
    except Exception as e:
        import traceback as _tb
        _l2d_log("打开失败: " + repr(e) + " | " + _tb.format_exc()[:900])
        print(f"[Live2DWindow] ⚠ 打开失败: {e}")
        return None
