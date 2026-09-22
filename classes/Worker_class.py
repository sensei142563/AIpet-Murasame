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


def _tidy_sentences(items):
    """整理待显示的句子列表：清理动作描写/括注 + 去掉清理后变空的句子。

    三件事都很要紧：
    * 【看屏幕】标记必须原样保留 —— 她只输出这个标记时，以前会被 clean_sentence 的
      「去掉【动作描写】」规则顺手删掉，主线程就认不出标记、走到"空回复"分支弹出
      「信号好像不太好」。日志实锤：自请看屏幕成功 0 次，「本轮回复为空」14 次。
    * 【文件】标记同样要保留（她要看电脑里的文件），并把她写的具体请求暂存起来，
      主线程取走后真的去翻。
    * 清理后变空的句子直接去掉 —— 否则对话框里会空出一行（用户反馈"文字有问题"），
      也会白白多跑一次翻译/情绪/立绘。
    """
    from tool.screen_intent import SCREEN_LOOK_MARK
    out = []
    for t in (items or []):
        s = str(t or "")
        if SCREEN_LOOK_MARK in s:
            out.append(SCREEN_LOOK_MARK)
            continue
        try:
            from tool import file_access as _fa
            if _fa.FILE_MARK in s:
                _fa.set_pending(s)          # 请求暂存，"列出 桌面"这种内容不进台词
                out.append(_fa.FILE_MARK)
                continue
        except Exception:
            pass
        c = clean_sentence(s)
        if c.strip():
            out.append(c)
    return out


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


def _emit_status(owner, text: str):
    """给对话框报一行状态（"正在操作电脑……"）——Worker 线程里发信号，主线程显示"""
    try:
        owner.status.emit(str(text))
    except Exception:
        pass


# 她只发了指令、没留台词时，按动作补一句（不然她"变哑巴"，主人什么都听不到）
_PC_FALLBACK = {
    "click": "好，我点一下。", "double": "好，我双击一下。", "right": "我右键点一下。",
    "type": "我来打字。", "key": "我按一下键。", "hotkey": "我按个组合键。",
    "scroll": "我滚一下。", "move": "我把鼠标挪过去看看。", "wait": "等一下下。",
}


def _pc_fallback_line(acts: list) -> str:
    """从动作里挑一句像她会说的话（只发指令的回合用）"""
    try:
        for a in (acts or []):
            t = str(a.get("type") or "")
            if t in ("click", "double", "right", "type", "key", "hotkey", "scroll"):
                return _PC_FALLBACK[t]
        for a in (acts or []):
            t = str(a.get("type") or "")
            if t in _PC_FALLBACK:
                return _PC_FALLBACK[t]
    except Exception:
        pass
    return "……好，我试试。"


def _handle_pc_control(reply: str, owner, is_auto: bool) -> str:
    """她要求操作键鼠：把【键鼠】指令抽出来执行，返回剥离指令后的文字。

    必须在 切句/翻译/情绪/立绘/TTS 之前调用 —— 否则指令会被念出来，
    而且显示用的句子列表里还会残留「【键鼠】点击 800 250」这种句子。
    is_auto=True 表示这是她自己主动动手（屏幕观察/空闲搭话那一轮）：
    受命动手（主人开口）不受自主间隔限制，主人让她做就必须做。
    """
    try:
        from tool import pc_control as _pc
        _acts = _pc.parse(reply)
        # 解析不出动作也要把半截指令从文字里去掉：那种"【键鼠】晃动鼠标"念出来更糟
        _clean = _pc.strip(reply)
        if not _acts:
            return _clean
        # ── 兜底：主人只是让你"陪着玩/陪你聊"时，不要真的去操作电脑 ──
        #    （用户反馈：他说"陪我打火影"，桌宠却去点开始菜单想打开火影）
        if not is_auto:
            try:
                if _pc.looks_like_chat_only(getattr(owner, "user_input", "")):
                    print("[桌宠] 💬 主人只是要人陪 → 这轮不动手（已忽略指令）")
                    return _clean or "好啊，你打我看——我在这儿。"
            except Exception:
                pass
        print(f"[桌宠] 她请求操作电脑：{len(_acts)} 个动作（{'自主' if is_auto else '受命'}）")
        print(f"[桌宠] 🖥 她要做的：{_pc.describe(_acts)}")
        _emit_status(owner, "正在操作电脑……")
        if _pc.enabled():
            import threading as _thpc
            _thpc.Thread(target=_pc.execute, args=(_acts,),
                         kwargs={"auto": is_auto,
                                 "notify": getattr(owner, "_pc_note", None)},
                         daemon=True).start()
            # 受命动手 → 开「连着做完」的任务循环：每步只花一次小调用，
# 不再一步等一整轮对话（实测一步 25~45 秒、一次任务要五分钟，用户反馈"效率太低"）。
            if not is_auto:
                try:
                    from tool import pc_task as _pt
                    _pt.start_task(getattr(owner, "history", None) or [],
                                   str(getattr(owner, "user_input", "") or ""),
                                   is_auto=False, done_note=_pc.describe(_acts))
                except Exception as _et:
                    print(f"[桌宠] ⚠ 任务循环启动失败: {_et}")
        else:
            print("[桌宠] 操控电脑未开启（右键菜单可打开）→ 只解析不执行")
        # ★ 只发指令、没留台词 → 补一句，别让她"变哑巴"
        return _clean or _pc_fallback_line(_acts)
    except Exception as _epc:
        print(f"[桌宠] 处理电脑操作失败: {_epc}")
        return reply


class qwen3_lora_Worker(QThread):
    finished = pyqtSignal(list, list, list, list, list, list)  # (AI回复, 立绘, history, 立绘历史, 语音, 情绪列表)
    status = pyqtSignal(str)      # 临时状态（"正在操作电脑……"）→ 对话框显示

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

    def _pc_note(self, reason: str):
        """动作被拦下来（没开发、自主间隔没到、坐标越界…）时把实情记进对话。

        不记的话她嘴上已经说了"帮你点掉"，实际什么都没做，下一轮还照旧吹牛。
        """
        try:
            self.history.append({
                "role": "system",
                "content": "（系统提示：你刚才想操作电脑，但那个动作没有真的执行——%s。"
                           "别重复同一个动作，也别声称自己做过了；如实地跟主人说没做成，"
                           "或者让他自己来。）" % reason,
            })
        except Exception:
            pass

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
        # ── 她要求操作键鼠：动作归动作、文字归文字（必须在切句/TTS 之前剥离）──
        #    识别触发/系统观察那一轮（t=True / role=system）= 她自己在看屏幕，算自主行动。
        reply = _handle_pc_control(
            reply, self,
            bool(getattr(self, "t", False)) or str(getattr(self, "role", "")) == "system")

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

        # 防御性清理：动作描写/括注/Emoji（保留【看屏幕】标记、去掉清理后变空的句子）
        reply_raw = list(reply)          # 清洗前的原始句（句内【标签】从这里提取）
        translate = [clean_sentence(t) for t in translate]
        reply = _tidy_sentences(reply)
        if any("【文件】" in str(x) for x in reply):
            _emit_status(self, "正在查看电脑文件……")

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
    status = pyqtSignal(str)      # 临时状态（"正在操作电脑……"）→ 对话框显示

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

    def _pc_note(self, reason: str):
        """动作被拦下来（没开发、自主间隔没到、坐标越界…）时把实情记进对话。

        不记的话她嘴上已经说了"帮你点掉"，实际什么都没做，下一轮还照旧吹牛。
        """
        try:
            self.history.append({
                "role": "system",
                "content": "（系统提示：你刚才想操作电脑，但那个动作没有真的执行——%s。"
                           "别重复同一个动作，也别声称自己做过了；如实地跟主人说没做成，"
                           "或者让他自己来。）" % reason,
            })
        except Exception:
            pass

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
        # ── 她要求操作键鼠：动作归动作、文字归文字（必须在切句/翻译/TTS 之前剥离）──
        #    以前放在切句之后：显示用的 reply_list_raw 还留着「【键鼠】移动 960 540」，
        #    strip 出来的空句子也会白白占一次翻译。
        reply = _handle_pc_control(
            reply, self,
            bool(getattr(self, "t", False)) or str(getattr(self, "role", "")) == "system")
        # 兜底切句：AI 未按 JSON 列表返回时，客户端按句末标点切分（修复整段话不切句）
        try:
            parsed = json.loads(reply)
            reply_list_raw = parsed if isinstance(parsed, list) else split_sentences(str(parsed))
        except Exception:
            reply_list_raw = split_sentences(reply)
        # 清理 + 去空句 + 保留【看屏幕】标记（下游翻译/情绪/立绘都按这份列表走）
        reply_list_raw = _tidy_sentences(reply_list_raw)
        if any("【文件】" in str(x) for x in reply_list_raw):
            _emit_status(self, "正在查看电脑文件……")
        reply_json = json.dumps(reply_list_raw, ensure_ascii=False)
        # 历史里只留她**实际说出口**的话：cloud_talk 早先把带指令的原文写进历史了，
        # 她会照着自己的历史学成「只回一行【键鼠】不说话」，而且显示/朗读也会对不上。
        try:
            if (self.history and isinstance(self.history[-1], dict)
                    and self.history[-1].get("role") == "assistant"):
                self.history[-1]["content"] = reply_json
        except Exception:
            pass
        # 2. 使用线程池并发执行所有 DeepSeek 任务和 TTS 任务
        if self.force_stop:print("[deepseek] 已中断生成。");return

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
        reply_list = list(reply_list_raw)   # 已在 _tidy_sentences 里清理过（【看屏幕】标记要留着）

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
