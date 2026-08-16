import os
import sys
import site

torch_path = os.path.join(site.getsitepackages()[0], 'torch', 'lib')
if os.path.exists(torch_path):
    os.add_dll_directory(torch_path)
    os.environ['PATH'] = torch_path + os.pathsep + os.environ.get('PATH', '')

import torch          # ← 必须在这里，任何第三方库之前
print("Torch loaded OK:", torch.__version__)

import sys
import threading
import json

from PyQt5.QtCore import QTimer, QObject, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QAction, QMenu

from classes.murasame_class import Murasame
from api import app as api_app
import uvicorn

from tool.config import get_config
from pets.pet_registry import get_live2d_dir, get_live2d_model_json, get_active_pet_id, detect_capabilities

# Live2D 导入（延迟，仅在 Live2D 模式下激活）
_LIVE2D_AVAILABLE = False
try:
    from Live2d.live2d_ui import Live2DWidget
    _LIVE2D_AVAILABLE = True
except ImportError:
    print("[AIpet] Live2D 模块未安装，跳过 Live2D 功能")


CONFIG = get_config("./config.json")
screen_index = CONFIG["screen_index"]
VOICE_TRIGGER_ENABLED = CONFIG.get("voice_trigger")


class VoiceBridge(QObject):
    text_ready = pyqtSignal(str)
    record_start = pyqtSignal()
    record_end = pyqtSignal()


class CameraBridge(QObject):
    """摄像头拍照结果信号 — 后台线程 → 主线程"""
    photo_result = pyqtSignal(str)


def save_screen_type(pet: Murasame) -> None:
    """在程序退出时保存当前截图开关状态到配置文件"""
    try:
        config_path = "./config.json"
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        config["screen_type"] = "true" if pet.is_screenshot_enabled() else "false"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[AIpet] 保存 screen_type 失败: {e}")


if __name__ == "__main__":

    # 设置全局 OpenGL 默认格式（启用 alpha 通道，支持透明背景）
    from PyQt5.QtGui import QSurfaceFormat
    gl_fmt = QSurfaceFormat()
    gl_fmt.setAlphaBufferSize(8)
    gl_fmt.setSamples(0)  # 禁用多重采样以避免与 alpha 冲突
    QSurfaceFormat.setDefaultFormat(gl_fmt)

    # 后台启动本地 API 服务（FastAPI + Uvicorn）
    def _run_api_server():
        config = uvicorn.Config(api_app, host="0.0.0.0", port=28565, log_level="info")
        server = uvicorn.Server(config)
        server.run()

    api_thread = threading.Thread(
        target=_run_api_server,
        name="uvicorn-thread",
        daemon=True,
    )
    api_thread.start()

    app = QApplication(sys.argv)  # 创建应用对象
    pet = Murasame()  # 创建桌宠实例
    app.aboutToQuit.connect(lambda: save_screen_type(pet))
    pet.show()  # 显示窗口

    # ===== Live2D 初始化 =====
    live2d_widget = None
    _LIVE2D_CONFIG_ENABLED = CONFIG.get("live2d_enabled", "true") == "true"
    if _LIVE2D_AVAILABLE and _LIVE2D_CONFIG_ENABLED:
        try:
            # 模型目录按当前角色动态解析（DLL 在引擎 Live2d/，模型在角色包内）
            model_dir = get_live2d_dir()
            if not model_dir:
                # 兼容回退：引擎目录（旧结构）
                model_dir = os.path.join(os.path.dirname(__file__), "Live2d")
            elif not os.path.exists(os.path.join(model_dir, "Live2DCubismCore.dll")):
                # 模型目录没有 DLL → 把引擎 DLL 目录加入 PATH（live2d_ui 已处理）
                pass
            # 动态查找角色模型 json：优先 pet.json 钉死，校验 moc3 引用存在（不写死 Murasame）
            model_json = get_live2d_model_json()
            # 按角色显示/交互配置（窗口比例/缩放/字号/摸头区域/情绪映射，阶段 E）
            from pets.pet_registry import get_live2d_display, get_live2d_params
            disp = get_live2d_display()
            params = get_live2d_params()
            print(f"[Live2D] 模型目录: {model_dir}")
            print(f"[Live2D] 模型文件存在: {bool(model_json) and os.path.exists(model_json)}")
            print(f"[Live2D] 模型文件: {model_json}")
            print(f"[Live2D] DLL 存在: {os.path.exists(os.path.join(model_dir, 'Live2DCubismCore.dll'))}")
            print(f"[Live2D] 显示配置: ratio={disp['window_ratio']} scale={disp['scale']} "
                  f"font={disp['font_scale']} head={disp['head_top']}~{disp['head_bottom']} "
                  f"eye={params['eye_open_max']} mouth={params['mouth_open_max']}")

            # 创建 Live2D 窗口，放在屏幕外初始化，避免遮挡桌宠
            live2d_widget = Live2DWidget(
                model_dir=model_dir, model_json=model_json,
                window_ratio=disp["window_ratio"], model_scale=disp["scale"],
                offset_x=disp["offset_x"], offset_y=disp["offset_y"],
                head_top=disp["head_top"], head_bottom=disp["head_bottom"],
                talk_top=disp["talk_top"], talk_bottom=disp["talk_bottom"],
                edge_margin_x=disp["edge_margin_x"],
                emotion_map=disp["emotions"], motion_map=disp["motions"],
                default_expression=disp["default_expression"],
                eye_open_max=params["eye_open_max"], mouth_open_max=params["mouth_open_max"],
                window_height_ratio=disp["window_height_ratio"],
            )
            pet.set_live2d_widget(live2d_widget)
            # 移到屏幕外再 show，防止初始化窗口遮挡桌宠
            live2d_widget.move(-9999, -9999)
            live2d_widget.resize(1, 1)
            live2d_widget.show()   # ← 触发 initializeGL()
            # 连接 Live2D 点击文本信号
            live2d_widget.trigger_text.connect(lambda text: pet.show_text(text, typing=True))

            # 轮询检查 OpenGL 初始化是否完成
            _check_count = {"n": 0}
            def _check_live2d():
                _check_count["n"] += 1
                status = {
                    "failed": live2d_widget._failed,
                    "ready": live2d_widget._render_ready,
                    "has_model": live2d_widget.model is not None,
                }
                print(f"[Live2D] 检查{_check_count['n']}: {status}")

                if live2d_widget._render_ready:
                    live2d_widget.hide()  # 就绪后隐藏
                    pet.set_live2d_ready(True)
                    # 回写当前显示参数供 PCL 调参面板 GET 初始化
                    try:
                        from api import set_live2d_display_state
                        set_live2d_display_state({
                            "scale": live2d_widget.model_scale,
                            "offset_x": live2d_widget.offset_x,
                            "offset_y": live2d_widget.offset_y,
                            "window_ratio": live2d_widget.window_ratio,
                            "window_height_ratio": live2d_widget.window_height_ratio,
                            "font_scale": pet._live2d_font_scale,
                            "text_offset_x": pet._text_offset_x,
                            "text_offset_y": pet._text_offset_y,
                        })
                    except Exception:
                        pass
                    if pet.should_default_live2d():
                        # 纯 Live2D 角色（pet.json model.default=live2d）：自动进入 Live2D
                        pet._toggle_live2d_mode()
                        print("[Live2D] ✅ 就绪，默认 Live2D 角色，已自动进入 Live2D 模式")
                    else:
                        print("[Live2D] ✅ 就绪，长按 Shift 2 秒切换")
                    return

                if live2d_widget._failed:
                    live2d_widget.hide()  # 失败就隐藏，不遮挡
                    if pet.should_default_live2d():
                        # 纯 Live2D 角色没有 2D 立绘可回退 → 至少显示失败提示，避免完全空白
                        pet.show_text(f"{pet.pet_name}的Live2D加载失败了...", typing=False)
                    print("[Live2D] 失败，跳过该功能")
                    return

                if _check_count["n"] < 20:
                    QTimer.singleShot(500, _check_live2d)
                else:
                    live2d_widget.hide()
                    if pet.should_default_live2d():
                        pet.show_text(f"{pet.pet_name}的Live2D加载超时了...", typing=False)
                    print("[Live2D] 超时，跳过该功能")

            QTimer.singleShot(300, _check_live2d)
        except Exception as e:
            import traceback
            print(f"[Live2D] 初始化异常: {e}")
            traceback.print_exc()

    # ===== 长按 Shift 2 秒 → 进入/退出 Live2D（双向切换） =====
    _shift_hold_timer = QTimer()
    _shift_hold_timer.setSingleShot(True)
    _shift_hold_timer.setInterval(2000)

    def _on_shift_held():
        """Shift 已按住 2 秒 → 切换 Live2D 模式"""
        if live2d_widget:
            if pet.is_live2d_mode():
                pet._exit_live2d_mode()
            else:
                pet._toggle_live2d_mode()

    _shift_hold_timer.timeout.connect(_on_shift_held)

    # 保存原始按键事件（避免递归）
    _orig_key_press = pet.keyPressEvent
    _orig_key_release = pet.keyReleaseEvent
    _key_state = {"shift": False, "ctrl": False, "alt": False}

    # ===== 长按 Alt 2 秒 → 切换长/短文本模式 =====
    _alt_hold_timer = QTimer()
    _alt_hold_timer.setSingleShot(True)
    _alt_hold_timer.setInterval(2000)

    def _on_alt_held():
        """Alt 已按住 2 秒 → 切换长/短文本模式"""
        pet.toggle_long_text_mode()

    _alt_hold_timer.timeout.connect(_on_alt_held)

    # ===== 长按 Ctrl 2 秒 → 摄像头拍照识别 =====
    _ctrl_hold_timer = QTimer()
    _ctrl_hold_timer.setSingleShot(True)
    _ctrl_hold_timer.setInterval(2000)

    _camera_state = {"initialized": False}

    def _on_ctrl_held():
        """Ctrl 已按住 2 秒 → 即时拍照识别（类似 PCL 屏幕识别按钮，不受常开配置限制）"""
        pet.show_text("拍照识别中...", typing=False)

        def _camera_task():
            try:
                from tool.camera import init_camera, take_photo_and_describe, get_camera_frame
                # 只初始化一次摄像头
                if not _camera_state["initialized"]:
                    init_camera(camera_id=CONFIG.get("camera_id", 0))
                    _camera_state["initialized"] = True
                desc = take_photo_and_describe()

                # 人脸识别
                face_result = ""
                if CONFIG.get("face_recognition_enabled") == "true":
                    try:
                        from tool.face_recognition import recognize_faces_in_frame
                        frame = get_camera_frame()
                        if frame is not None:
                            print(f"[Face] 开始人脸识别，帧尺寸: {frame.shape}")
                            faces = recognize_faces_in_frame(frame)
                            print(f"[Face] 检测到 {len(faces)} 个人脸: {faces}")
                            master_found = [f for f in faces if f.get("is_master")]
                            others = [f for f in faces if not f.get("is_master")]
                            face_parts = []
                            if master_found:
                                face_parts.append(f"检测到主人（置信度 {master_found[0].get('confidence', '?')}）")
                                print(f"[Face] 检测到主人，置信度: {master_found[0].get('confidence')}")
                            if others:
                                for f in others:
                                    name = f.get('name', '?')
                                    rel = f.get('relation', '')
                                    label = f"{name}({rel})" if rel else name
                                    face_parts.append(f"{label}（置信度 {f.get('confidence', '?')}）")
                                    print(f"[Face] 检测到他人: {label}，置信度: {f.get('confidence')}")
                            if face_parts:
                                face_result = "\n【人脸识别】" + "; ".join(face_parts)
                            else:
                                print("[Face] 未识别到已知人脸")
                        else:
                            print("[Face] 摄像头帧不可用")
                    except Exception as fe:
                        print(f"[Face] 识别异常: {fe}")
                        import traceback; traceback.print_exc()

                # 通过信号桥接，安全地回到主线程处理结果
                combined = (desc or "拍照失败") + face_result
                cam_bridge.photo_result.emit(combined)
            except Exception as e:
                print(f"[camera] 拍照异常: {e}")
                cam_bridge.photo_result.emit("摄像头识别出了点问题...")
        threading.Thread(target=_camera_task, daemon=True).start()

    # 摄像头结果桥接 — 后台线程 emit → 主线程槽函数
    cam_bridge = CameraBridge()
    def _on_photo_result(combined_text: str):
        if combined_text and combined_text != "拍照失败" and not combined_text.startswith("错误"):
            # 根据是否真的检测到主人，动态调整 system prompt 人称
            has_master = "检测到主人" in combined_text
            subject = "主人" if has_master else "周围的人"
            prompt = (
                f"【重要系统指令】你刚刚通过摄像头看到了{subject}当前的真实状态。"
                "以下是对摄像头画面的描述和可能的人脸识别信息，这是你亲眼所见的事实，你必须围绕这个内容展开对话：\n"
                "=== 摄像头画面描述开始 ===\n"
                f"{combined_text}\n"
                "=== 摄像头画面描述结束 ===\n"
            )
            if has_master:
                prompt += (
                    f"请以{pet.pet_name}的身份，自然地观察并评论你看到的主人。"
                    "可以表达关心、好奇、或撒娇——但要让人感觉你真的看到了主人。回答不超过两句话。"
                )
            else:
                prompt += (
                    f"请以{pet.pet_name}的身份，自然地描述你看到的人。如果识别到具体的人名请直接称呼，"
                    "如果没有识别到任何人可以说'好像有什么人在附近呢'。回答不超过两句话。"
                )
            pet.start_thread(prompt, role="system", t=True)
        else:
            pet.show_text("拍照失败，可能是没检测到摄像头~", typing=True)
    cam_bridge.photo_result.connect(_on_photo_result)

    _ctrl_hold_timer.timeout.connect(_on_ctrl_held)

    # ===== Live2D 调参热键（先按 F1 开启调参模式，再使用其他热键；F5 持久化）=====
    # F1 开关调参模式 | +/- 模型缩放 | 方向键 模型平移 | Shift+方向键 文本框位置
    # F7/F8 窗口宽高比 | F2/F3 窗口高度 | F4 重置位置 | , . 或 F10/F11 字号
    # F9 参考线 | F5 保存 | F6 打印
    # 注意：整体 try/except 兜底——PyQt5 槽函数抛异常会直接杀死进程（"桌宠消失"）
    _tuning_state = {"on": False}  # 调参模式开关（默认关闭，避免打字时方向键误触调参）

    def _handle_tuning_key(event, is_press):
        try:
            return _handle_tuning_key_inner(event, is_press)
        except Exception as _tune_err:
            print(f"[Live2D] 调参热键异常(已忽略): {_tune_err}")
            return False

    def _handle_tuning_key_inner(event, is_press):
        if not is_press or live2d_widget is None or not pet.is_live2d_mode():
            return False
        from PyQt5.QtCore import Qt as QtKey
        key = event.key()
        w = live2d_widget

        # F1：开关调参模式（唯一始终可用的调参键）
        if key == QtKey.Key_F1:
            _tuning_state["on"] = not _tuning_state["on"]
            if _tuning_state["on"]:
                print("[Live2D] 🎛 调参模式已开启。热键: +/- 模型缩放 | 方向键 模型平移(上下=画布上下边距) | "
                      "Shift+方向键 文本框位置 | F7/F8 窗口宽高比 | F2/F3 窗口高度 | F4 重置位置 | "
                      ", . 或 F10/F11 字号 | F9 参考线 | F5 保存 | F6 查看当前值 | Esc 退出输入模式")
                print("[Live2D] 再次按 F1 关闭调参模式")
            else:
                print("[Live2D] 调参模式已关闭")
            return True

        # 调参模式未开启 → 所有热键放行（不影响正常输入/快捷键）
        if not _tuning_state["on"]:
            return False
        # 正在打字（输入模式）→ 全部放行给输入法/文本，绝不调参
        if getattr(pet, "input_mode", False):
            return False

        shift = _key_state.get("shift", False)
        changed = False
        if key in (QtKey.Key_Plus, QtKey.Key_Equal):
            w.model_scale = round(w.model_scale + 0.05, 3); changed = True
        elif key == QtKey.Key_Minus:
            w.model_scale = round(w.model_scale - 0.05, 3); changed = True
        elif key in (QtKey.Key_Up, QtKey.Key_Down, QtKey.Key_Left, QtKey.Key_Right) and shift:
            # Shift+方向键：移动文本框（上下左右）
            step = 20
            if key == QtKey.Key_Up:
                pet._text_offset_y -= step
            elif key == QtKey.Key_Down:
                pet._text_offset_y += step
            elif key == QtKey.Key_Left:
                pet._text_offset_x -= step
            elif key == QtKey.Key_Right:
                pet._text_offset_x += step
            pet.update()
            print(f"[Live2D] 文本框偏移: ({pet._text_offset_x},{pet._text_offset_y})")
            return True
        elif key == QtKey.Key_Up:
            w.offset_y = round(w.offset_y - 10.0, 1); changed = True
        elif key == QtKey.Key_Down:
            w.offset_y = round(w.offset_y + 10.0, 1); changed = True
        elif key == QtKey.Key_Left:
            w.offset_x = round(w.offset_x - 10.0, 1); changed = True
        elif key == QtKey.Key_Right:
            w.offset_x = round(w.offset_x + 10.0, 1); changed = True
        elif key == QtKey.Key_F7:
            w.window_ratio = round(max(0.2, w.window_ratio - 0.05), 3); changed = True
        elif key == QtKey.Key_F8:
            w.window_ratio = round(w.window_ratio + 0.05, 3); changed = True
        elif key == QtKey.Key_F2:
            w.window_height_ratio = round(max(0.15, w.window_height_ratio - 0.05), 3); changed = True
        elif key == QtKey.Key_F3:
            w.window_height_ratio = round(min(0.95, w.window_height_ratio + 0.05), 3); changed = True
        elif key == QtKey.Key_F4:
            # 一键重置模型位置（找回移出画布的模型）
            w.offset_x = 0.0
            w.offset_y = 0.0
            try:
                if w.model:
                    w.model.SetOffset(0.0, 0.0)
            except Exception:
                pass
            print("[Live2D] 模型位置已重置 offset=(0,0)")
            return True
        elif key == QtKey.Key_Comma:
            pet._live2d_font_scale = round(max(0.05, pet._live2d_font_scale - 0.05), 3); changed = True
        elif key == QtKey.Key_Period:
            pet._live2d_font_scale = round(pet._live2d_font_scale + 0.05, 3); changed = True
        elif key == QtKey.Key_F10:
            pet._live2d_font_scale = round(max(0.05, pet._live2d_font_scale - 0.05), 3); changed = True
        elif key == QtKey.Key_F11:
            pet._live2d_font_scale = round(pet._live2d_font_scale + 0.05, 3); changed = True
        elif key == QtKey.Key_F5:
            from pets.pet_registry import save_live2d_display
            save_live2d_display(
                scale=w.model_scale, offset_x=w.offset_x, offset_y=w.offset_y,
                window_ratio=w.window_ratio, window_height_ratio=w.window_height_ratio,
                font_scale=pet._live2d_font_scale,
                text_offset_x=pet._text_offset_x, text_offset_y=pet._text_offset_y,
            )
            print(f"[Live2D] ✅ 已保存到 pet.json: scale={w.model_scale} offset=({w.offset_x},{w.offset_y}) "
                  f"ratio={w.window_ratio} height={w.window_height_ratio} font={pet._live2d_font_scale} "
                  f"text=({pet._text_offset_x},{pet._text_offset_y})")
            return True
        elif key == QtKey.Key_F6:
            print(f"[Live2D] 当前: scale={w.model_scale} offset=({w.offset_x},{w.offset_y}) "
                  f"ratio={w.window_ratio} height={w.window_height_ratio} font={pet._live2d_font_scale} "
                  f"text=({pet._text_offset_x},{pet._text_offset_y})")
            return True
        elif key == QtKey.Key_F9:
            w.toggle_tuning_guides()
            return True
        if changed:
            # 边界钳制：偏移不超过当前窗口尺寸（模型最多移出一半，总能看到）、缩放限制 [0.1, 4.0]
            w.offset_x = max(-float(w.width()), min(float(w.width()), w.offset_x))
            w.offset_y = max(-float(w.height()), min(float(w.height()), w.offset_y))
            w.model_scale = min(4.0, max(0.1, w.model_scale))
            try:
                if w.model:
                    w.model.SetScale(w.model_scale)
                    w.model.SetOffset(w.offset_x, w.offset_y)
            except Exception:
                pass
            if key in (QtKey.Key_F7, QtKey.Key_F8, QtKey.Key_F2, QtKey.Key_F3):
                w.resize_to_screen(CONFIG.get("screen_index", 0))
                pet.move(w.pos())
            pet._ensure_live2d_overlay()
            print(f"[Live2D] scale={w.model_scale} offset=({w.offset_x},{w.offset_y}) "
                  f"ratio={w.window_ratio} height={w.window_height_ratio} font={pet._live2d_font_scale}")
            return True
        return False

    def _on_pet_key_event(event, is_press=True):
        """监听 Shift / Ctrl 长按状态 + Live2D 调参热键"""
        from PyQt5.QtCore import Qt as QtKey
        key = event.key()
        if _handle_tuning_key(event, is_press):
            return
        if key == QtKey.Key_Shift:
            if is_press and not _key_state["shift"]:
                _key_state["shift"] = True
                _shift_hold_timer.start()
            elif not is_press:
                _key_state["shift"] = False
                if _shift_hold_timer.isActive():
                    _shift_hold_timer.stop()
        elif key == QtKey.Key_Control:
            if is_press and not _key_state["ctrl"]:
                _key_state["ctrl"] = True
                _ctrl_hold_timer.start()
            elif not is_press:
                _key_state["ctrl"] = False
                if _ctrl_hold_timer.isActive():
                    _ctrl_hold_timer.stop()
        elif key == QtKey.Key_Alt:
            if is_press and not _key_state["alt"]:
                _key_state["alt"] = True
                _alt_hold_timer.start()
            elif not is_press:
                _key_state["alt"] = False
                if _alt_hold_timer.isActive():
                    _alt_hold_timer.stop()
        if is_press:
            return _orig_key_press(event)
        else:
            return _orig_key_release(event)

    def _on_pet_key_press(event):
        return _on_pet_key_event(event, is_press=True)

    def _on_pet_key_release(event):
        return _on_pet_key_event(event, is_press=False)

    pet.keyPressEvent = _on_pet_key_press
    pet.keyReleaseEvent = _on_pet_key_release

    # ===== 连接 Live2D 信号到 pet 功能 =====
    if live2d_widget:
        live2d_widget.trigger_text.connect(lambda text: pet.show_text(text, typing=True))
        live2d_widget.trigger_touch_head.connect(
            lambda: pet.start_thread("主人摸了摸你的头", role="system")
        )
        live2d_widget.trigger_input_mode.connect(lambda: pet._trigger_input_mode())
        def _sync_move(dx, dy):
            pet.move(pet.x() + dx, pet.y() + dy)
        live2d_widget.trigger_drag_move.connect(_sync_move)
        # 任何模型交互（点击/拖动激活了模型窗口）→ 文字层重新置顶（不抢焦点）
        def _on_live2d_interacted():
            if pet.is_live2d_overlay_visible():
                live2d_widget.lower()
                pet.re_raise_overlay()
        live2d_widget.interacted.connect(_on_live2d_interacted)

        # Live2D Widget 也需要绑定 Shift 监听（pet hide 后失去焦点）
        _live2d_key_orig_press = live2d_widget.keyPressEvent
        _live2d_key_orig_release = live2d_widget.keyReleaseEvent

        def _on_live2d_key_event(event, is_press=True):
            from PyQt5.QtCore import Qt as QtKey
            key = event.key()
            if _handle_tuning_key(event, is_press):
                return
            if key == QtKey.Key_Shift:
                if is_press and not _key_state["shift"]:
                    _key_state["shift"] = True
                    _shift_hold_timer.start()
                elif not is_press:
                    _key_state["shift"] = False
                    if _shift_hold_timer.isActive():
                        _shift_hold_timer.stop()
            elif key == QtKey.Key_Control:
                if is_press and not _key_state["ctrl"]:
                    _key_state["ctrl"] = True
                    _ctrl_hold_timer.start()
                elif not is_press:
                    _key_state["ctrl"] = False
                    if _ctrl_hold_timer.isActive():
                        _ctrl_hold_timer.stop()
            elif key == QtKey.Key_Alt:
                if is_press and not _key_state["alt"]:
                    _key_state["alt"] = True
                    _alt_hold_timer.start()
                elif not is_press:
                    _key_state["alt"] = False
                    if _alt_hold_timer.isActive():
                        _alt_hold_timer.stop()
            if is_press:
                return _live2d_key_orig_press(event)
            else:
                return _live2d_key_orig_release(event)

        def _on_live2d_key_press(event):
            return _on_live2d_key_event(event, is_press=True)

        def _on_live2d_key_release(event):
            return _on_live2d_key_event(event, is_press=False)

        live2d_widget.keyPressEvent = _on_live2d_key_press
        live2d_widget.keyReleaseEvent = _on_live2d_key_release

    screens = QApplication.screens()
    target_screen = screens[screen_index]
    geometry = target_screen.availableGeometry()
    pet.move(geometry.x(), geometry.y())

    # ===== 轮询 API 控制标志（PCL 启动器按钮 → API → 此定时器检测） =====
    _control_poll_timer = QTimer()
    _control_poll_timer.setInterval(500)

    # ===== PCL 按钮语音录制状态 =====
    _pcl_voice_recorder = None
    _pcl_voice_recording = False

    def _apply_live2d_display_request(req):
        """处理 PCL 图形化调参面板的请求：apply(实时应用)/save(持久化)/reset(重置位置)"""
        from api import set_live2d_display_state
        w = live2d_widget
        if w is None:
            return
        apply_data = req.get("apply") or {}
        if apply_data:
            def _f(key, cur):
                try:
                    return float(apply_data.get(key, cur))
                except (TypeError, ValueError):
                    return cur
            w.model_scale = min(4.0, max(0.1, _f("scale", w.model_scale)))
            w.offset_x = _f("offset_x", w.offset_x)
            w.offset_y = _f("offset_y", w.offset_y)
            w.window_ratio = _f("window_ratio", w.window_ratio)
            w.window_height_ratio = min(0.95, max(0.15, _f("window_height_ratio", w.window_height_ratio)))
            pet._live2d_font_scale = _f("font_scale", pet._live2d_font_scale)
            pet._text_offset_x = int(_f("text_offset_x", pet._text_offset_x))
            pet._text_offset_y = int(_f("text_offset_y", pet._text_offset_y))
            try:
                if w.model:
                    w.model.SetScale(w.model_scale)
                    w.model.SetOffset(w.offset_x, w.offset_y)
            except Exception:
                pass
            # 仅 Live2D 模式下实时调整窗口/覆盖层（2D 模式只更新数值，下次进 Live2D 生效）
            if pet.is_live2d_mode():
                try:
                    w.resize_to_screen(CONFIG.get("screen_index", 0))
                    pet.move(w.pos())
                    pet._ensure_live2d_overlay()
                except Exception as _e:
                    print(f"[API] 实时调整窗口失败: {_e}")
            print(f"[API] 已实时应用显示参数: {apply_data}")
        if req.get("reset"):
            w.offset_x = 0.0
            w.offset_y = 0.0
            try:
                if w.model:
                    w.model.SetOffset(0.0, 0.0)
            except Exception:
                pass
            print("[API] 模型位置已重置")
        if req.get("save"):
            from pets.pet_registry import save_live2d_display
            save_live2d_display(
                scale=w.model_scale, offset_x=w.offset_x, offset_y=w.offset_y,
                window_ratio=w.window_ratio, window_height_ratio=w.window_height_ratio,
                font_scale=pet._live2d_font_scale,
                text_offset_x=pet._text_offset_x, text_offset_y=pet._text_offset_y,
            )
        # 回写当前状态供 PCL GET
        set_live2d_display_state({
            "scale": w.model_scale, "offset_x": w.offset_x, "offset_y": w.offset_y,
            "window_ratio": w.window_ratio, "window_height_ratio": w.window_height_ratio,
            "font_scale": pet._live2d_font_scale,
            "text_offset_x": pet._text_offset_x, "text_offset_y": pet._text_offset_y,
        })

    def _poll_control_flags():
        global _pcl_voice_recorder, _pcl_voice_recording
        try:
            from api import check_flag, check_voice_start, check_voice_end, set_feature_status
            from api import consume_live2d_request, set_live2d_display_state
        except ImportError:
            return

        # ===== PCL 图形化调参请求（应用/保存/重置）=====
        _disp_req = consume_live2d_request()
        if _disp_req and live2d_widget is not None:
            try:
                _apply_live2d_display_request(_disp_req)
            except Exception as _derr:
                print(f"[API] 处理显示参数请求失败: {_derr}")

        # PCL 按钮语音识别（长按录音 → 识别 → 对话，等同 CapsLock 逻辑）
        if check_voice_start():
            if VOICE_TRIGGER_ENABLED == "true":
                try:
                    from tool.voice_trigger import AudioRecorder
                    if _pcl_voice_recorder is None:
                        _pcl_voice_recorder = AudioRecorder()
                    _pcl_voice_recorder.start()
                    _pcl_voice_recording = True
                    pet.show_text("正在录音......", typing=False)
                    print("[API Control] PCL 按钮触发录音开始")
                except Exception as e:
                    print(f"[API Control] voice start error: {e}")
            else:
                print("[API Control] 语音识别功能在配置中已关闭")

        if check_voice_end():
            if _pcl_voice_recording and _pcl_voice_recorder is not None:
                _pcl_voice_recording = False
                pet.show_text("录音结束，正在识别......", typing=False)
                print("[API Control] PCL 按钮触发录音结束")

                def _pcl_stt_and_reply():
                    from datetime import datetime
                    import os as _os
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    wav_path = f"./tmp/pcl_voice_{timestamp}.wav"
                    _os.makedirs("./tmp", exist_ok=True)
                    saved = _pcl_voice_recorder.stop_and_save(wav_path)
                    if not saved:
                        return
                    try:
                        from tool.stt import transcribe_full
                        text = transcribe_full(saved)
                        text = (text or "").strip()
                        if text:
                            print(f"[API Control] PCL 语音识别结果: {text}")
                            pet._request_dialog.emit(text, "user", False)
                        else:
                            print("[API Control] PCL 语音识别结果为空")
                    except Exception as e:
                        print(f"[API Control] PCL 语音识别失败: {e}")
                    finally:
                        try:
                            if _os.path.exists(saved):
                                _os.remove(saved)
                        except Exception:
                            pass

                import threading as _th
                _th.Thread(target=_pcl_stt_and_reply, daemon=True).start()
            else:
                print("[API Control] 录音未开始，忽略 voice/end")

        # 语音识别切换（旧逻辑保留，兼容之前的使用方式）
        if check_flag("voice"):
            try:
                from tool.config import get_config as _get_cfg
                cfg = _get_cfg("./config.json")
                if cfg.get("voice_trigger") == "true":
                    print("[API Control] 切换语音识别")
                    pet.show_text("语音识别功能已触发~", typing=True)
                    set_feature_status("voice", "on")
                else:
                    set_feature_status("voice", "off (config)")
            except Exception as e:
                print(f"[API Control] voice error: {e}")
        # 屏幕识别（后台线程，避免阻塞和中断）
        if check_flag("screenshot"):
            def _screenshot_task():
                try:
                    print("[API Control] 触发屏幕识别")
                    from tool.cloud_API_chat import cloud_vl
                    from PyQt5.QtGui import QGuiApplication
                    screen = QGuiApplication.primaryScreen()
                    pixmap = screen.grabWindow(0)
                    import tempfile
                    import os as _os
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png", dir="tmp")
                    tmp_name = tmp.name
                    tmp.close()
                    pixmap.save(tmp_name, "PNG")
                    desc = cloud_vl(tmp_name)
                    _os.remove(tmp_name)
                    prompt = (
                        "【重要系统指令】你刚刚通过屏幕截图看到了主人当前的真实状态。"
                        "以下是对主人屏幕内容的描述，这是你亲眼所见的事实，你必须围绕这个内容展开对话：\n"
                        "=== 屏幕内容描述开始 ===\n"
                        f"{desc}\n"
                        "=== 屏幕内容描述结束 ===\n"
                        f"请以{pet.pet_name}的身份，自然地观察并评论主人正在做什么。你的回复必须紧密围绕上述描述。"
                    )
                    pet._request_dialog.emit(prompt, "system", True)
                    from api import set_feature_status
                    set_feature_status("screenshot", "triggered")
                except Exception as e:
                    print(f"[API Control] screenshot error: {e}")
            threading.Thread(target=_screenshot_task, daemon=True).start()

        # 摄像头即时拍照（PCL 按钮触发，不受常开配置限制，类比屏幕识别按钮）
        if check_flag("camera"):
            def _camera_task():
                try:
                    print("[API Control] 触发摄像头即时拍照")
                    from tool.camera import init_camera, take_photo_and_describe, get_camera_frame
                    if not _camera_state["initialized"]:
                        init_camera(camera_id=CONFIG.get("camera_id", 0))
                        _camera_state["initialized"] = True
                    desc = take_photo_and_describe()

                    # 人脸识别
                    face_result = ""
                    if CONFIG.get("face_recognition_enabled") == "true":
                        try:
                            from tool.face_recognition import recognize_faces_in_frame
                            frame = get_camera_frame()
                            if frame is not None:
                                print(f"[Face] PCL按钮人脸识别，帧尺寸: {frame.shape}")
                                faces = recognize_faces_in_frame(frame)
                                print(f"[Face] PCL按钮检测到 {len(faces)} 个人脸: {faces}")
                                master_found = [f for f in faces if f.get("is_master")]
                                others = [f for f in faces if not f.get("is_master")]
                                face_parts = []
                                if master_found:
                                    face_parts.append(f"检测到主人（置信度 {master_found[0].get('confidence', '?')}）")
                                    print(f"[Face] PCL检测到主人，置信度: {master_found[0].get('confidence')}")
                                if others:
                                    for f in others:
                                        name = f.get('name', '?')
                                        rel = f.get('relation', '')
                                        label = f"{name}({rel})" if rel else name
                                        face_parts.append(f"{label}（置信度 {f.get('confidence', '?')}）")
                                        print(f"[Face] PCL检测到他人: {label}，置信度: {f.get('confidence')}")
                                if face_parts:
                                    face_result = "\n【人脸识别】" + "; ".join(face_parts)
                                else:
                                    print("[Face] PCL按钮未识别到已知人脸")
                            else:
                                print("[Face] PCL按钮摄像头帧不可用")
                        except Exception as fe:
                            print(f"[Face] PCL按钮识别异常: {fe}")

                    from api import set_feature_status
                    combined = (desc or "拍照失败") + face_result
                    if desc and desc != "无法获取摄像头画面" and not desc.startswith("错误"):
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
                                f"请以{pet.pet_name}的身份，自然地观察并评论你看到的主人。"
                                "可以表达关心、好奇、或撒娇——但要让人感觉你真的看到了主人。回答不超过两句话。"
                            )
                        else:
                            prompt += (
                                f"请以{pet.pet_name}的身份，自然地描述你看到的人。如果识别到具体的人名请直接称呼，"
                                "如果没有识别到任何人可以说'好像有什么人在附近呢'。回答不超过两句话。"
                            )
                        pet._request_dialog.emit(prompt, "system", True)
                        set_feature_status("camera", "triggered")
                    else:
                        set_feature_status("camera", "failed")
                except Exception as e:
                    print(f"[API Control] camera error: {e}")
            threading.Thread(target=_camera_task, daemon=True).start()
        # 长文本模式切换（PCL 按钮触发）
        if check_flag("longtext"):
            try:
                print("[API Control] 切换长/短文本模式")
                pet.toggle_long_text_mode()
                from api import set_feature_status as _set_status
                _set_status("longtext", "on" if pet.is_long_text_mode() else "off")
            except Exception as e:
                print(f"[API Control] longtext error: {e}")

        # Live2D 切换
        if check_flag("live2d"):
            try:
                print("[API Control] 切换 Live2D")
                if pet.is_live2d_mode():
                    pet._exit_live2d_mode()
                    set_feature_status("live2d", "off")
                else:
                    pet._toggle_live2d_mode()
                    set_feature_status("live2d", "on")
            except Exception as e:
                print(f"[API Control] live2d error: {e}")

    _control_poll_timer.timeout.connect(_poll_control_flags)
    _control_poll_timer.start()

    tray_icon = QSystemTrayIcon(QIcon("icon.png"), parent=app)
    tray_menu = QMenu()

    # 勿扰模式（勾选 = 开启勿扰，不再主动打扰）
    dnd_action = QAction("Do Not Disturb")
    dnd_action.setCheckable(True)
    dnd_action.setChecked(pet.is_dnd_enabled())
    dnd_action.toggled.connect(pet.set_dnd_enabled)

    # 屏幕截图开关（勾选 = 开启截图）
    screenshot_action = QAction("Screenshot")
    screenshot_action.setCheckable(True)
    screenshot_action.setChecked(pet.is_screenshot_enabled())
    screenshot_action.toggled.connect(pet.set_screenshot_enabled)

    clear_action = QAction("Clear History")
    clear_action.triggered.connect(pet.cleer_history)

    # 退出
    exit_action = QAction("Exit")
    exit_action.triggered.connect(app.quit)

    # 菜单绑定
    tray_menu.addAction(dnd_action)
    tray_menu.addAction(screenshot_action)
    tray_menu.addAction(clear_action)
    tray_menu.addAction(exit_action)
    tray_icon.setContextMenu(tray_menu)
    tray_icon.show()

    # ===== CapsLock 语音触发 =====
    if VOICE_TRIGGER_ENABLED == "true":
        from tool.voice_trigger import CapslockVoiceTrigger
        bridge = VoiceBridge()

        bridge.text_ready.connect(lambda text: pet.start_thread(text, role="user"))
        bridge.record_start.connect(
            lambda: pet.show_text("正在录音......", typing=False)
        )
        bridge.record_end.connect(
            lambda: pet.show_text("录音结束，正在识别......", typing=False)
        )

        def _on_voice_text_ready(text: str) -> None:
            bridge.text_ready.emit(text)

        def _on_record_start() -> None:
            bridge.record_start.emit()

        def _on_record_end() -> None:
            bridge.record_end.emit()

        try:
            voice_trigger = CapslockVoiceTrigger(
                on_text_ready=_on_voice_text_ready,
                hold_seconds=2.0,
                on_record_start=_on_record_start,
                on_record_end=_on_record_end,
            )
            voice_trigger.start()
        except Exception as e:
            print(f"[AIpet] 启用 CapsLock 语音触发失败: {e}")
    else:
        print("[AIpet] 已在配置中关闭 CapsLock 语音触发")

    sys.exit(app.exec_())  # 进入事件循环
