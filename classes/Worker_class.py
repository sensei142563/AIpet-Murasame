import json
import tempfile
import time
import os
from concurrent.futures import ThreadPoolExecutor

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QGuiApplication

from tool.cloud_API_chat import cloud_portrait, cloud_translate, cloud_talk, cloud_emotion
from tool.config import get_config
from tool.chat import qwen3_lora, ollama_qwen3_sentence, ollama_qwen3_portrait, gpt_sovits_tts, ollama_qwen3_emotion, ollama_qwen3_translate, strip_self_dialogue

portrait_type = get_config("./config.json")['portrait']


def current_portrait_type():
    """运行时读取立绘体系（桌宠右键换装会把 config 切到 a 套；
    若仍用启动时的快照常量，AI 会继续按 b 套选层导致与 a 套渲染不匹配）"""
    try:
        return str(get_config("./config.json").get("portrait") or portrait_type or "a")
    except Exception:
        return portrait_type


def clean_sentence(text):
    """防御性清理：去掉动作描写【】、括注（）/()、Emoji（人设 prompt 已禁止，此处兜底）"""
    import re
    if not text:
        return ""
    text = str(text)
    text = re.sub(r"【[^】]*】", "", text)
    text = re.sub(r"（[^）]*）", "", text)
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F]", "", text)
    return text.strip()


def split_sentences(text):
    """兜底切句：AI 未按 JSON 列表返回时，客户端按句末标点切分（保留标点）"""
    import re
    if not text:
        return [""]
    text = str(text)
    parts = re.split(r"(?<=[。！？!?…])\s*", text)
    parts = [p.strip() for p in parts if p and p.strip()]
    if not parts:
        return [text.strip()]
    return parts


def _is_pure_punct(text):
    """句子是否为纯标点/省略号（没有可朗读内容）"""
    return not (text or "").strip("…。.!！?？、，~～\"'“”‘’「」『』 \t\n")


def _persona_default_emotion() -> str:
    """人设默认情绪（短文本语音兜底用）：角色包 pet.json voices.default_emotion，
    默认「高兴」——活泼角色不要默认用冷淡的「平静」。"""
    try:
        from pets.pet_registry import get_pet_config
        v = (get_pet_config().get("voices", {}) or {})
        return str(v.get("default_emotion") or "高兴")
    except Exception:
        return "高兴"


def _align_lists(reply_list, translate_list, emotion_list, portrait_list):
    """把翻译/情绪/立绘列表对齐到「中文回复句数」（TTS 与逐句显示一一对应）。

    翻译拆句往往比回复细（如 1 句被译成 3 句）、情绪标签数也可能不一致，
    直接 zip 会截断 → 后面的句子没语音。这里：
    - 翻译：多于回复句 → 按比例合并；少于 → 补空串
    - 情绪：多于 → 截断；少于 → 补最后一个标签（无则「平静」）
    - 立绘：多于 → 截断；少于 → 补空列表
    """
    n = len(reply_list)

    t = list(translate_list)
    if len(t) < n:
        t += [""] * (n - len(t))
    elif len(t) > n:
        merged = []
        for i in range(n):
            lo = int(i * len(t) / n)
            hi = int((i + 1) * len(t) / n)
            if hi <= lo:
                hi = lo + 1
            merged.append("".join(t[lo:hi]))
        t = merged

    e = list(emotion_list)
    if len(e) < n:
        # 情绪列表缺失时的补位：沿用最后一个标签；一个都没有 → 按人设默认情绪
        # （活泼角色=高兴），不要一律用「平静」——那会让语音听起来冷淡
        _pad = e[-1] if e else _persona_default_emotion()
        e += [_pad] * (n - len(e))
    else:
        e = e[:n]

    p = list(portrait_list)[:n]
    if len(p) < n:
        p += [[]] * (n - len(p))
    return t, e, p


class qwen3_lora_Worker(QThread):
    finished = pyqtSignal(list, list, list, list, list, list)  # (AI回复, 立绘, history, 立绘历史, 语音, 情绪列表)

    def __init__(self, history, portrait_history, user_input, role="user", t = False,
                 portrait_type=None):
        super().__init__()
        # 当前画面上显示的那一套立绘（a/b）——AI 必须按同一套选层，
        # 否则渲染时要跨套换算，表情/装饰会被丢掉（用户反馈"立绘没有表情"）
        self.portrait_type = portrait_type
        self.history = history
        self.portrait_history = portrait_history
        self.user_input = user_input
        self.role = role
        self.t = t
        self.force_stop = False

    def stop_all(self):
    
        self.force_stop = True

    def stop_screen(self):
      
        if self.t:
            self.force_stop = True
    def run(self):
        """QThread 入口：外面兜一层底。

        任何一步抛异常（模型返回异常、立绘清单被写坏、网络超时……）以前会让线程直接死掉，
        finished 信号永远不发 → 桌宠一直停在「她还在说话/思考」，点她也不理（用户反馈）。
        现在异常也发一个空回复，让她正常收尾、把对话锁放掉。
        """
        try:
            self._run_impl()
        except Exception as _e:
            import traceback
            print(f"[对话] ⚠ 本轮回复失败（已自动恢复，不会卡住）：{_e}")
            traceback.print_exc()
            try:
                self.finished.emit([], [], self.history, self.portrait_history, [], [])
            except Exception:
                pass
    def _run_impl(self):
        def to_list(text):
            try:
                text = json.loads(text)  # 把字符串解析成 Python 列表
            except Exception as e:
                text = [text]  # 如果解析失败，就退化成单句
            return text
        if self.force_stop:
            print("[qwen3-lora] 已中断生成。")
            return
        reply, history = qwen3_lora(self.history, self.user_input, self.role)  # 对话
        # ★ 防「自问自答」：模型有时会把历史当剧本继续写，返回里带上「user主人：…」和下一轮
        _fixed = strip_self_dialogue(reply)
        if _fixed != reply:
            print('[对话] ⚠ 已截断模型自行续写的多轮台词（防自问自答）')
            reply = _fixed
        if self.force_stop:print("[ollama-qwn3] 已中断生成。");return
        # ── 她要求操作键鼠：把【键鼠】指令抽出来（动作归动作、文字归文字）──
        #    必须在翻译/情绪/立绘/TTS 之前剥离，否则她会把指令念出来。
        try:
            from tool import pc_control as _pc
            _acts = _pc.parse(reply)
            if _acts:
                # 识别触发/系统观察那一轮 = 她自己在看屏幕，属于"自主行动"
                _auto_turn = bool(getattr(self, "t", False)) or str(getattr(self, "role", "")) == "system"
                print(f"[桌宠] 她请求操作电脑：{len(_acts)} 个动作（自主={_auto_turn}）")
                if _pc.enabled():
                    import threading as _thpc
                    _thpc.Thread(target=_pc.execute, args=(_acts,),
                                 kwargs={"auto": _auto_turn}, daemon=True).start()
                else:
                    print("[桌宠] 操控电脑未开启（右键菜单可打开）→ 只解析不执行")
                reply = _pc.strip(reply) or "……好，我试试。"
        except Exception as _epc:
            print(f"[桌宠] 处理电脑操作失败: {_epc}")

        reply = ollama_qwen3_sentence(reply)  # 句子分割
        if self.force_stop: print("[ollama-qwn3] 已中断生成。");return
        history[-1]["content"] = reply
        portrait_list, portrait_history = ollama_qwen3_portrait(reply, self.portrait_history, (getattr(self, "portrait_type", None) or current_portrait_type()))  # 立绘
        if self.force_stop: print("[ollama-qwn3] 已中断生成。");return
        emotion_list = ollama_qwen3_emotion(history)  # 情感
        if self.force_stop: print("[ollama-qwn3] 已中断生成。");return
        translate = ollama_qwen3_translate(reply)  # 翻译

        translate = to_list(translate)
        reply = to_list(reply)
        emotion_list = to_list(emotion_list)
        portrait_list = to_list(portrait_list)

        # 防御性清理：动作描写/括注/Emoji
        reply_raw = list(reply)          # 清洗前的原始句（句内【标签】从这里提取）
        translate = [clean_sentence(t) for t in translate]
        reply = [clean_sentence(t) for t in reply]

        # 对齐：以中文回复句数为准（翻译/情绪/立绘可能与回复句数不一致）
        translate, emotion_list, portrait_list = _align_lists(
            reply, translate, emotion_list, portrait_list)

        # 并发执行所有TTS任务（索引定位结果，杜绝空句导致的错位）
        # 语音合成开关（启动器 设置→桌宠 可关）：关闭时跳过全部 TTS（合成较慢、会拖慢回复）
        _voice_on = True
        try:
            _voice_on = bool(get_config("./config.json").get("voice_synthesis_enable", True))
        except Exception:
            _voice_on = True
        voices = [None] * len(translate)
        if not _voice_on:
            print("[tts] 语音合成已关闭（可在启动器 设置→桌宠 中开启），跳过 TTS")
        else:
            with ThreadPoolExecutor(max_workers=3) as executor:
                # 提交所有TTS任务
                futures = []
                for i, text in enumerate(translate):
                    if self.force_stop: print("[tts] 已中断生成。");return
                    if not text or _is_pure_punct(text):
                        continue
                    futures.append((i, executor.submit(gpt_sovits_tts, text, emotion_list[i])))

                # 按索引回填结果，保持与回复句一一对应
                for i, future in futures:
                    if self.force_stop: print("[tts] 已中断生成。");return
                    voices[i] = future.result()

        # 句内【情绪】标签（如【白】）→ 只覆盖「显示用情绪」（表情/动作），
        # TTS 已按原始情绪合成，语音不受影响。
        import re as _re
        for i, t in enumerate(reply_raw):
            m = _re.findall(r'\[(.+?)\]', str(t))
            if m and i < len(emotion_list):
                emotion_list[i] = m[-1]

        self.finished.emit(reply, portrait_list, history, portrait_history, voices, emotion_list)  # 发回主线程

class cloud_API_Worker(QThread):
    finished = pyqtSignal(list, list, list, list, list, list)

    def __init__(self, history, portrait_history, user_input, role="user", t = False,
                 portrait_type=None):
        super().__init__()
        # 当前画面上显示的那一套立绘（a/b）——AI 必须按同一套选层，
        # 否则渲染时要跨套换算，表情/装饰会被丢掉（用户反馈"立绘没有表情"）
        self.portrait_type = portrait_type
        self.history = history
        self.portrait_history = portrait_history
        self.user_input = user_input
        self.role = role
        self.force_stop = False
        self.t = t

    def stop_all(self):
        """外部调用，用于请求线程中断"""
        self.force_stop = True
    def stop_screen(self):
        """外部调用，用于请求线程中断"""
        if self.t:
            self.force_stop = True
    '''
    这种定义方法来实现中途中断的操作我之前一直没有想到，这个做法很好
    '''
    def run(self):
        """QThread 入口：外面兜一层底。

        任何一步抛异常（模型返回异常、立绘清单被写坏、网络超时……）以前会让线程直接死掉，
        finished 信号永远不发 → 桌宠一直停在「她还在说话/思考」，点她也不理（用户反馈）。
        现在异常也发一个空回复，让她正常收尾、把对话锁放掉。
        """
        try:
            self._run_impl()
        except Exception as _e:
            import traceback
            print(f"[对话] ⚠ 本轮回复失败（已自动恢复，不会卡住）：{_e}")
            traceback.print_exc()
            try:
                self.finished.emit([], [], self.history, self.portrait_history, [], [])
            except Exception:
                pass
    def _run_impl(self):
        def to_list(text):
            try:
                text = json.loads(text)  # 把字符串解析成 Python 列表
            except Exception as e:
                text = [text]  # 如果解析失败，就退化成单句
            return text

        # 1. 先获取对话回复（这个必须串行，因为依赖前面的历史）
        if self.force_stop:print("[deepseek] 已中断生成。");return
        reply, history = cloud_talk(self.history, self.user_input, self.role)
        # ★ 防「自问自答」：云端模型也会把历史当剧本接着写，带回「主人：…」和下一轮台词
        _fixed = strip_self_dialogue(reply)
        if _fixed != reply:
            print('[对话] ⚠ 已截断模型自行续写的多轮台词（防自问自答）')
            reply = _fixed
        # 兜底切句：AI 未按 JSON 列表返回时，客户端按句末标点切分（修复整段话不切句）
        try:
            parsed = json.loads(reply)
            reply_list_raw = parsed if isinstance(parsed, list) else split_sentences(str(parsed))
        except Exception:
            reply_list_raw = split_sentences(reply)
        reply_json = json.dumps(reply_list_raw, ensure_ascii=False)
        # 2. 使用线程池并发执行所有 DeepSeek 任务和 TTS 任务
        if self.force_stop:print("[deepseek] 已中断生成。");return
        # ── 她要求操作键鼠：把【键鼠】指令抽出来（动作归动作、文字归文字）──
        #    必须在翻译/情绪/立绘/TTS 之前剥离，否则她会把指令念出来。
        try:
            from tool import pc_control as _pc
            _acts = _pc.parse(reply_json)
            if _acts:
                _auto_turn = bool(getattr(self, "t", False)) or str(getattr(self, "role", "")) == "system"
                print(f"[桌宠] 她请求操作电脑：{len(_acts)} 个动作（自主={_auto_turn}）")
                if _pc.enabled():
                    import threading as _thpc
                    _thpc.Thread(target=_pc.execute, args=(_acts,),
                                 kwargs={"auto": _auto_turn}, daemon=True).start()
                else:
                    print("[桌宠] 操控电脑未开启（右键菜单可打开）→ 只解析不执行")
                reply_json = _pc.strip(reply_json) or "……好，我试试。"
        except Exception as _epc:
            print(f"[桌宠] 处理电脑操作失败: {_epc}")

        with ThreadPoolExecutor(max_workers=5) as executor:  # 增加线程数
            # 提交所有任务（下游拿到切好的句子列表，保证对齐）
            future_portrait = executor.submit(cloud_portrait, reply_json, self.portrait_history, (getattr(self, "portrait_type", None) or current_portrait_type()))
            future_translate = executor.submit(cloud_translate, reply_json)
            future_emotion = executor.submit(cloud_emotion, history)

            # 获取所有结果
            portrait_result, portrait_history = future_portrait.result()
            emotion_result = future_emotion.result()
            translate_result = future_translate.result()

        # 3. 处理结果

        translate_list = to_list(translate_result)
        emotion_list = to_list(emotion_result)
        portrait_list = to_list(portrait_result)
        # 防御性清理：动作描写/括注/Emoji
        translate_list = [clean_sentence(t) for t in translate_list]
        reply_list = [clean_sentence(t) for t in reply_list_raw]

        # 4. 对齐列表后并发执行所有TTS任务
        translate_list, emotion_list, portrait_list = _align_lists(
            reply_list, translate_list, emotion_list, portrait_list)

        voices = [None] * len(translate_list)
        # ⚠ 修复：设置里那个开关存的是**字符串** "false"（滑条写的就是 "true"/"false"），
        #   而 bool("false") == True → 关了语音也照样合成，还会因为 TTS 服务慢而卡住整轮回复。
        #   这里按字符串语义解析（false/0/off/no 都算关），并且每次都重新读配置（改完立即生效）。
        _voice_on = True
        try:
            _v = get_config("./config.json").get("voice_synthesis_enable", True)
            if isinstance(_v, str):
                _voice_on = _v.strip().lower() in ("true", "1", "on", "yes", "开", "开启")
            else:
                _voice_on = bool(_v)
        except Exception:
            _voice_on = True
        if not _voice_on:
            print("[tts] 语音合成已关闭（设置里可开启）→ 本轮不合成语音，直接出文字")
        else:
            with ThreadPoolExecutor(max_workers=3) as tts_executor:
                # 提交所有TTS任务
                futures = []
                for i, text in enumerate(translate_list):
                    if self.force_stop:print("[tts] 已中断生成。");return
                    if not text or _is_pure_punct(text):
                        continue
                    futures.append((i, tts_executor.submit(gpt_sovits_tts, text, emotion_list[i])))

                # 按索引回填结果，保持与回复句一一对应
                for i, future in futures:
                    if self.force_stop:print("[tts] 已中断生成。");return
                    voices[i] = future.result()

        # 句内【情绪】标签（如【白】）→ 只覆盖「显示用情绪」（表情/动作），
        # TTS 已按原始情绪合成，语音不受影响。
        import re as _re
        for i, t in enumerate(reply_list_raw):
            m = _re.findall(r'\[(.+?)\]', str(t))
            if m and i < len(emotion_list):
                emotion_list[i] = m[-1]

        self.finished.emit(reply_list, portrait_list, history, portrait_history, voices, emotion_list)


screen_index = get_config("./config.json")["screen_index"]


def shot_is_blank(pixmap) -> bool:
    """截到的画面是不是黑的/一片纯色（等于没截到东西）。

    锁屏、显示器休眠、独占全屏（游戏/播放器）时 QScreen.grabWindow(0) 会返回一张全黑图；
    偶尔也会返回一张纯色图。这种图送给视觉模型只能得到「看不到内容」，
    她就跟着说「我看不到你的屏幕」（用户反馈过）。
    判定（缩到 48x48 再采样，开销可忽略）：
      * 又黑又没有内容：平均亮度 < 12 或 97% 以上是纯黑像素
      * 整幅几乎没有变化：标准差 < 3（真实屏幕哪怕全白也有文字/边框的抗锯齿，实测标准差 60+）
    """
    import statistics
    try:
        from PyQt5.QtCore import Qt
        if pixmap is None or pixmap.isNull():
            return True
        small = pixmap.scaled(48, 48, Qt.IgnoreAspectRatio, Qt.FastTransformation).toImage()
        vals = []
        for y in range(small.height()):
            for x in range(small.width()):
                c = small.pixelColor(x, y)
                vals.append((c.red() + c.green() + c.blue()) / 3.0)
        if not vals:
            return True
        mean = sum(vals) / len(vals)
        dark_ratio = sum(1 for v in vals if v < 10) / len(vals)
        try:
            sd = statistics.pstdev(vals)
        except Exception:
            sd = 99.0
        return mean < 12 or dark_ratio > 0.97 or sd < 3.0
    except Exception:
        return False


class ScreenWorker(QThread):
    # 发出临时文件路径（主线程负责删除）
    screenshot_captured = pyqtSignal(str)

    def __init__(self, interval_sec=3.0, parent=None):
        super().__init__(parent)
        self.interval = interval_sec
        os.makedirs("tmp", exist_ok=True)

    def run(self):
        screens = QGuiApplication.screens()
        screen = screens[screen_index]
        if screen is None:
            return
        while not self.isInterruptionRequested():
            # 抓屏（全屏）
            pixmap = screen.grabWindow(0)
            if shot_is_blank(pixmap):
                # 偶尔会抓到全黑（锁屏 / 显示器休眠 / 独占全屏）→ 等一下重抓一次；
                # 还是黑就安静跳过这轮：不调用视觉模型，也不让她说"看不到"
                time.sleep(1.5)
                if self.isInterruptionRequested():
                    break
                pixmap = screen.grabWindow(0)
                if shot_is_blank(pixmap):
                    print("[vision] ⚠ 两次抓屏都是黑的（锁屏 / 显示器休眠 / 独占全屏）→ 跳过本轮屏幕识别")
                    for _ in range(int(self.interval * 10)):
                        if self.isInterruptionRequested():
                            break
                        time.sleep(0.1)
                    continue
            # 存到临时文件
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png", dir="tmp")
            tmp_name = tmp.name
            tmp.close()
            pixmap.save(tmp_name, "PNG")
            # 发信号，让主线程去处理（网络调用等）
            self.screenshot_captured.emit(tmp_name)
            # sleep 可被 requestInterruption() 打断（间隔相对宽松）
            for _ in range(int(self.interval * 10)):
                if self.isInterruptionRequested():
                    break
                time.sleep(0.1)


camera_id_config = get_config("./config.json").get("camera_id", 0)


class CameraWorker(QThread):
    """定时摄像头识别的后台线程（类比 ScreenWorker）"""
    camera_captured = pyqtSignal(str)  # 发出 cv2 帧编码的 base64 URL

    def __init__(self, interval_sec=300.0, camera_id=0, parent=None):
        super().__init__(parent)
        self.interval = interval_sec
        self.camera_id = camera_id
        self._cap = None

    def _init_camera(self):
        import cv2
        from tool.camera import CameraCapture
        try:
            self._cap = CameraCapture(self.camera_id)
            return True
        except Exception as e:
            print(f"[CameraWorker] 摄像头初始化失败: {e}")
            return False

    def run(self):
        if not self._init_camera():
            return
        while not self.isInterruptionRequested():
            frame = self._cap.get_frame()
            if frame is not None:
                import base64
                import cv2
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 75]
                _, buffer = cv2.imencode('.jpg', frame, encode_param)
                img_b64 = base64.b64encode(buffer).decode('utf-8')
                img_url = f"data:image/jpeg;base64,{img_b64}"
                self.camera_captured.emit(img_url)
            # 按间隔 sleep
            for _ in range(int(self.interval * 10)):
                if self.isInterruptionRequested():
                    break
                time.sleep(0.1)

    def close_camera(self):
        if self._cap:
            try:
                self._cap.close()
            except Exception:
                pass
            self._cap = None
