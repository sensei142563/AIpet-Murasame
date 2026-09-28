# -*- coding: utf-8 -*-
"""「主人这句话是不是要我看看屏幕」+ 带屏幕内容的提示词 + 当场看一眼。

为什么单独拎出来
----------------
以前只有「定时抓屏（screen_interval）」和「截图按钮」会调用视觉模型；主人直接问她
「你看看我屏幕上是什么」「我在干嘛」时**根本不会去抓屏**，她只能拿之前自动识别留下的
记忆凑答案，或者干脆说看不到。所以：先判意图，命中就**当场抓屏识别**，再把描述和
主人的问题一起交给她回答。

依赖：抓屏用 tool.screen_capture（Win32，后台线程安全）；识别优先用现有的云端视觉
（tool.cloud_API_chat.cloud_vl），没配视觉模型就如实返回空，不编内容。
"""
import os
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 需要看屏幕才能答的问法（中文 + 日语）
_LOOK_WORDS = (
    "看看屏幕", "看下屏幕", "看一下屏幕", "看眼屏幕", "看我的屏幕", "屏幕上", "屏幕里",
    "我在干嘛", "我在干什么", "我在干啥", "我在做什么", "我在忙什么", "我在弄什么",
    "我在玩什么", "我在看什么", "我现在在干嘛", "你现在看到", "你看到了什么",
    "看看我在", "看我屏幕", "截个屏", "截屏看看", "帮我看看屏幕", "看一眼屏幕",
    "看看这个", "这个是什么", "我现在在做什么", "你看到了吗", "你看见了吗",
    "画面里", "我屏幕上有什么", "看看我电脑",
    "画面", "見て", "何してる", "画面に", "スクリーン",
)
# 明确不该触发抓屏的说法（省钱：她在问别的事）
_NO_LOOK = (
    "屏幕亮度", "屏幕分辨率", "屏幕保护", "屏幕截图在哪里", "关机", "锁屏怎么设置",
    "不用看", "别看了", "不需要看屏幕",
)


def needs_screen_look(text: str) -> bool:
    """主人这句话是不是要我看看屏幕"""
    t = str(text or "").strip()
    if not t or len(t) > 200:
        return False
    low = t.lower()
    for w in _NO_LOOK:
        if w in t or w in low:
            return False
    for w in _LOOK_WORDS:
        if w in t or w in low:
            return True
    return False


def build_screen_prompt(desc: str, user_text: str = "") -> str:
    """把"屏幕描述 + 主人的问题"拼成给她的提示词"""
    d = str(desc or "").strip()
    if not d:
        return ""
    u = str(user_text or "").strip()
    out = ("【你刚刚看了一眼主人的屏幕（这是你亲眼看到的）】\n" + d[:800] +
           "\n（用你看到的回答主人，自然一点，别提「截图/识别/系统」。）\n")
    if u:
        out += "主人的问题是：" + u[:200]
    return out


def look_now(save_dir: str = None):
    """当场抓屏 + 识别 → (描述, 图片路径)；任一步失败返回 ("", "")"""
    img_path = ""
    try:
        from tool import screen_capture as _sc
        d = save_dir or os.path.join(tempfile.gettempdir(), "aipet_look")
        os.makedirs(d, exist_ok=True)
        img_path = _sc.capture_png(os.path.join(d, "look.png"))
        if not img_path:
            return "", ""
        try:
            from PyQt5.QtGui import QImage
            if _sc.is_blank(QImage(img_path)):
                return "", img_path            # 黑屏/白屏：不拿它编故事
        except Exception:
            pass
    except Exception as e:
        print("[看屏幕] ⚠ 抓屏失败: %s" % e)
        return "", ""
    try:
        from tool.cloud_API_chat import cloud_vl
        desc = str(cloud_vl(img_path) or "").strip()
        return desc, img_path
    except Exception as e:
        print("[看屏幕] ⚠ 识别失败（没配视觉模型？）: %s" % e)
        return "", img_path
