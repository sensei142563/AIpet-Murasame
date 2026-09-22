# -*- coding: utf-8 -*-
"""任务循环：让"一件事"连着做完，而不是每走一步都要等一整轮对话。

为什么需要（实测 data/pc_control.log）：主人让她打开哔哩哔哩，她是这么走的——
21:35:38 点击任务栏 → 21:36:07 移动鼠标 → 21:36:34 按 win → 21:37:10 按键 win →
21:37:40 被重复抑制挡下 → 21:38:20 又移动 → 21:38:54 又按 win → 21:39:19 卡死。
每一步之间隔 25~45 秒：因为每走一步都要经过「看一次屏幕(8~20秒) + 完整对话管线
(翻译/情绪/立绘/TTS 约 10 秒) + 完成汇报(又一轮)」。十步下来五分钟，"半天都没操控好"。

这个模块做的事：接到"要动手"的任务后，在后台连续循环——
    让模型给出下一步指令 → 执行 → 把结果喂回去 → 继续，直到她说"完成"或步数/时间用尽。
每一步只做一次很小的模型调用（不翻译、不合成语音、不画立绘），一步约 2~4 秒。
任务结束时把她那句总结交给正常的对话链路说出口（所以她不是哑巴）。

主人喊停：stop() 立刻中止循环（pc_control 那边也会立刻停手不再执行下一个动作）。
"""
import json
import os
import threading
import time

MAX_STEPS = 8                  # 一个任务最多走几步（每步 1 次小调用）
MAX_SECONDS = 100              # 一个任务最多花这么久
LOOK_BUDGET = 2                # 一个任务里最多看几次屏幕（每次 5~9 秒，很贵）

_lock = threading.Lock()
_state = {
    "running": False,
    "task": "",
    "step": 0,
    "stop": False,
    "started": 0.0,
    "looks": 0,
    "log": [],
}
# 界面回调（桌宠注册）：status(文本) 显示在对话框；finish(文本, 成功?) 任务结束
_ui = {"status": None, "finish": None}


def set_ui(status=None, finish=None):
    _ui["status"] = status
    _ui["finish"] = finish


def _say_status(text: str):
    try:
        if _ui["status"]:
            _ui["status"](str(text))
    except Exception:
        pass


def _say_finish(text: str, ok: bool = True):
    try:
        if _ui["finish"]:
            _ui["finish"](str(text), bool(ok))
    except Exception:
        pass


def running() -> bool:
    return bool(_state["running"])


def current_task() -> str:
    return str(_state["task"] or "")


def stop(reason: str = "主人喊停") -> bool:
    """中止当前任务（立刻生效：循环下一步就退出，pc_control 也停止执行）"""
    try:
        with _lock:
            if not _state["running"]:
                return False
            _state["stop"] = True
        print(f"[任务] ⛔ 停止：{reason}")
        try:
            from tool import pc_control as _pc
            _pc.set_abort(reason)          # 正在执行的动作立刻停手
        except Exception:
            pass
        return True
    except Exception:
        return False


def _stopped() -> bool:
    return bool(_state["stop"])


# ─────────────────────── 模型调用（很小、很便宜） ───────────────────────

def _ask(system: str, user: str, max_tokens: int = 300) -> str:
    try:
        from tool.config import get_config
        model_type = str(get_config("./config.json").get("model_type", "deepseek")).strip().lower()
    except Exception:
        model_type = "deepseek"
    try:
        if model_type == "local":
            from tool.chat import ollama_post
            r = ollama_post("qwen3:14b", {"model": "qwen3:14b", "prompt": system + "\n\n" + user,
                                          "stream": False, "options": {"num_predict": max_tokens}})
            try:
                return str((r or {}).get("message", {}).get("content") or r.get("response") or "").strip()
            except Exception:
                return ""
        from tool.cloud_API_chat import post
        from longtext.model_config import get_short_model_config
        cfg = get_short_model_config()
        if not cfg:
            return ""
        payload = {"messages": [{"role": "system", "content": system},
                                {"role": "user", "content": user}],
                   "model": cfg["model"], "max_tokens": max_tokens, "stream": False}
        payload.update(cfg.get("reasoning") or {})
        return str(post("任务", payload, api_key=cfg["api_key"]) or "").strip()
    except Exception as e:
        print(f"[任务] ⚠ 调用失败: {type(e).__name__}: {e}")
        return ""


def _pet_name() -> str:
    try:
        from pets.pet_registry import get_pet_config
        return str((get_pet_config() or {}).get("name") or "桌宠")
    except Exception:
        return "桌宠"


def _planner_system(pet: str) -> str:
    try:
        from tool import pc_control as _pc
        brief = _pc.screen_brief()
        rules = _pc.PROMPT_RULES
    except Exception:
        brief, rules = "", ""
    return (
        f"你是{pet}，正在**亲自操作主人的电脑**。你只能靠输出指令来操作，没有别的办法。\n"
        "【一次写一步到三步】每轮你输出接下来要做的一到三行指令，不要解释、不要客套、不要多说话。\n"
        "指令格式：\n"
        "【键鼠】点击 800 250 / 【键鼠】双击 800 250 / 【键鼠】右键 800 250 / 【键鼠】移动 800 250\n"
        "【键鼠】输入 你好 / 【键鼠】按键 enter / 【键鼠】热键 ctrl+s / 【键鼠】滚轮 下 3 / 【键鼠】等待 0.6\n"
        "需要看清画面时才写一行「【看屏幕】」（很慢，一次任务最多用两次，别每步都看）。\n"
        "★ 每一步之间留出反应时间：点了会弹出东西就跟着写「【键鼠】等待 0.8」。\n"
        "★ 任务做完了 → 输出：完成：<一句给主人说的话>（用你的口吻，可以带点小情绪）\n"
        "★ 确实做不了（找不到、没有权限、界面不认）→ 输出：失败：<一句给主人说的话>\n"
        f"{brief}\n{rules}"
    )


# ─────────────────────── 主循环 ───────────────────────

def start_task(history: list, task: str, is_auto: bool = False, done_note: str = "") -> bool:
    """接到"要动手"的任务 → 开一个后台线程连着做（受命才做，自主的那些保持一次一轮）。

    done_note：这一轮已经做过的那批动作（循环把它当成"上一步"，不会重复做）。
    """
    try:
        if is_auto:
            return False                    # 她自己动手的场景维持原样：一次一批、有间隔
        if running():
            print("[任务] ⏭ 已有任务在跑，先不重复开")
            return False
        task = str(task or "").strip()
        if not task:
            return False
        with _lock:
            _state.update({"running": True, "task": task, "step": 0, "stop": False,
                           "started": time.time(), "looks": 0, "log": []})
        t = threading.Thread(target=_loop, args=(history, task, str(done_note or "")), daemon=True)
        t.start()
        print(f"[任务] ▶ 开始连着做：{task[:40]}")
        return True
    except Exception as e:
        print(f"[任务] ⚠ 启动失败: {e}")
        return False


def _exec_step(actions: list) -> str:
    """执行一步动作，返回"实际做成了什么"的文字"""
    from tool import pc_control as _pc
    notes = []
    try:
        done = _pc.execute(actions, notify=lambda r: notes.append(r))
    except Exception as e:
        return f"执行出错（{type(e).__name__}）"
    desc = _pc.describe(done) if done else "（一个都没做成）"
    if notes:
        desc += "；" + "；".join(str(n) for n in notes[:2])
    return desc


def _look_once() -> str:
    """任务里看一眼屏幕（收费很贵的操作，有预算限制）"""
    try:
        if _state["looks"] >= LOOK_BUDGET:
            return "（这一轮不能再看了——看屏幕次数已经用完，按现有信息继续或说做不了）"
        import tempfile
        from PyQt5.QtGui import QGuiApplication
        from tool.chat import describe_image
        _state["looks"] += 1
        _say_status("正在观看屏幕……")
        screen = QGuiApplication.primaryScreen()
        pm = screen.grabWindow(0)
        os.makedirs("tmp", exist_ok=True)
        p = os.path.join("tmp", "task_shot.png")
        pm.save(p, "PNG")
        # 任务里用更小的图（约 5 秒，比正常快档还快），描述也短一点
        desc = describe_image(p, max_side=640, max_new=120)
        return str(desc or "（看不清）")
    except Exception as e:
        return f"（看屏幕失败：{type(e).__name__}）"


def _loop(history: list, task: str, done_note: str = ""):
    from tool import pc_control as _pc
    pet = _pet_name()
    system = _planner_system(pet)
    last = done_note or "（还没有动作）"
    obs = ""
    ok, final = False, ""
    try:
        for step in range(1, MAX_STEPS + 1):
            if _stopped():
                ok, final = False, "好，停了。"
                break
            if time.time() - float(_state["started"]) > MAX_SECONDS:
                ok, final = False, "唔……这个我一时做不完。"
                break
            _state["step"] = step
            _say_status(f"正在操作电脑……第 {step} 步")
            user = (f"任务：{task}\n"
                    f"上一步做了什么：{last}\n"
                    + (f"你上次看到的画面：{obs[:1200]}\n" if obs else "")
                    + "现在输出下一步指令（一到三行）；做完了就输出「完成：…」，做不了就输出「失败：…」。")
            reply = _ask(system, user, max_tokens=400)
            if not reply:
                final = "唔……我这边联系不上模型了。"
                break
            print(f"[任务] 第 {step} 步：{reply[:120].replace(chr(10), ' | ')}")
            _state["log"].append(reply[:200])

            # 她要求看屏幕 → 看一眼再继续
            if "【看屏幕】" in reply:
                obs = _look_once()
                print(f"[任务] 看了一眼屏幕：{str(obs)[:80]}")
                _say_status("正在操作电脑……")
                clean = reply.replace("【看屏幕】", "").strip()
                if not clean:
                    last = "（你刚看了一眼屏幕）"
                    continue
                reply = clean

            # 完成 / 失败
            for key in ("完成：", "完成:", "失败：", "失败:"):
                if key in reply:
                    _is_ok = key.startswith("完成")
                    final = reply.split(key, 1)[1].strip().strip("「」\"'") or \
                        ("做完了。" if _is_ok else "这个我做不到。")
                    ok = _is_ok
                    break
            if final:
                break

            # 执行这一步
            acts = _pc.parse(reply)
            acts = [a for a in acts if a.get("type") != "move"] or acts
            if not acts:
                last = "（你这一步没写出可执行的指令，请写「【键鼠】…」或「完成：…」）"
                continue
            if _stopped():
                ok, final = False, "好，停了。"
                break
            print(f"[任务] 执行：{_pc.describe(acts)}")
            last = _exec_step(acts)
            print(f"[任务] 结果：{last[:120]}")
        else:
            final = "唔……搞了半天还没弄好，你来吧。"
    except Exception as e:
        print(f"[任务] ⚠ 循环出错: {type(e).__name__}: {e}")
        final = "唔……出了点问题，我没做成。"
    finally:
        stopped = _stopped()
        with _lock:
            _state["running"] = False
        try:
            _pc.clear_abort()
        except Exception:
            pass
        if stopped:
            _say_finish("好，停了。", False)
        else:
            _say_finish(final or "唔……做完了。", ok)
        print(f"[任务] ■ 结束（{'成功' if ok else '未完成'}）：{final[:60]}")


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("任务模块自检")
    print("  MAX_STEPS =", MAX_STEPS, "| MAX_SECONDS =", MAX_SECONDS, "| LOOK_BUDGET =", LOOK_BUDGET)
    print("  running() =", running())
    print("  规划提示词长度:", len(_planner_system("夏目")))
    print()
    print("  提示词开头:")
    for line in _planner_system("夏目").splitlines()[:6]:
        print("   ", line[:90])
