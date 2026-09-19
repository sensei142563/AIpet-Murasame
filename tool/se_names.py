# -*- coding: utf-8 -*-
"""把音效文件名（日文）批量翻译成中文，并在两个目录里改名：
    ① 项目内 剧情素材/se/（剧情模式实际用的那份）
    ② 解包目录 05_音乐/数据/音效/（用户要求翻译的那份）
同时写出对照表 剧情素材/se/_名称对照.json（原名 → 中文名），改名可回溯。
"""
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

SRC_DIRS = [
    os.path.join(BASE, "剧情素材", "se"),
    r"D:\下载\AI桌宠\新建文件夹\05_音乐\数据\音效",
]
MAP_PATH = os.path.join(BASE, "剧情素材", "se", "_名称对照.json")

# 兜底词典：模型不可用时也能翻译出个大概（按词元替换，长的优先）
FALLBACK = [
    ("【システム】決定", "系统-确认"), ("【システム】キャンセル", "系统-取消"),
    ("【システム】カーソル", "系统-光标"), ("スマホ操作音", "手机-操作音"),
    ("システム", "系统"), ("キャンセル", "取消"), ("決定", "确认"), ("カーソル", "光标"),
    ("足音", "脚步声"), ("脚步声", "脚步声"), ("跳跃", "跳跃"), ("奔跑", "奔跑"),
    ("玄関", "玄关"), ("居間", "起居室"), ("客房", "客房"), ("客庁", "客厅"),
    ("教場", "教场"), ("会議室", "会议室"), ("甘味処", "甜品店"), ("風呂", "浴室"),
    ("開", "开"), ("閉", "关"), ("扉", "门"), ("ドア", "门"), ("チャイム", "门铃"),
    ("ノック", "敲门"), ("摇", "摇晃"), ("揺", "摇晃"), ("ペンギン", "企鹅"),
    ("心音", "心跳"), ("鼓動", "心跳"), ("風", "风"), ("雨", "雨"), ("波", "浪"),
    ("蝉", "蝉鸣"), ("鳥", "鸟鸣"), ("森", "森林"), ("川", "河"), ("虫", "虫鸣"),
    ("鐘", "钟声"), ("三味線", "三味线"), ("琴", "琴"), ("笛", "笛"),
    ("笑", "笑声"), ("泣", "哭声"), ("叫", "喊叫"), ("悲鳴", "尖叫"),
    ("平手打ち", "耳光"), ("ビンタ", "耳光"), ("抱", "拥抱"), ("キス", "亲吻"),
    ("刀", "刀"), ("薙刀", "长刀"), ("斬", "斩击"), ("刺", "刺击"), ("切", "挥砍"),
    ("払", "扫击"), ("構", "架势"), ("打", "打击"), ("パンチ", "拳击"), ("キック", "踢"),
    ("倒", "倒下"), ("爆発", "爆炸"), ("魔法", "魔法"), ("特效", "特效"),
    ("システム", "系统"), ("電話", "电话"), ("携帯", "手机"), ("メール", "邮件"),
    ("アラーム", "闹钟"), ("カメラ", "相机"), ("シャッター", "快门"),
    ("ループ", "循环"), ("环境", "环境音"), ("環境", "环境音"), ("街", "街道"),
    ("学院", "学院"), ("神社", "神社"), ("部屋", "房间"), ("和室", "和室"),
    ("着替", "换衣"), ("料理", "做饭"), ("食", "吃饭"), ("茶", "茶"),
    ("ページ", "翻页"), ("ペン", "笔"), ("紙", "纸"), ("筆", "毛笔"),
    ("拍手", "鼓掌"), ("ざわ", "嘈杂"), ("雑踏", "人声嘈杂"), ("静", "安静"),
]


def _clean(name: str) -> str:
    s = re.sub(r"\.(ogg|wav|mp3|opus)$", "", name, flags=re.I)
    s = s.strip()
    return s


def _safe(s: str) -> str:
    """Windows 文件名不允许的字符换成全角/短横"""
    s = re.sub(r'[\\/:*?"<>|]', "-", s)
    return s.strip(" .") or "音效"


def fallback_translate(name: str) -> str:
    s = _clean(name)
    out = s
    for jp, cn in FALLBACK:
        out = out.replace(jp, cn)
    out = re.sub(r"[（(]\s*[)）]", "", out)
    return out or s


def batch_prompt(names: list) -> str:
    return (
        "把下面这些游戏音效的日文文件名翻译成**简体中文**，用于素材库命名。要求：\n"
        "1) 简洁、像音效库的名字（例：『【システム】決定1』→『系统-确认1』，"
        "『≪特效17』→『特效17』，『玄関開閉-居間』→『开关门-起居室』）；\n"
        "2) 保留编号（1、2、17…）和【】里的类别含义（翻译成中文）；\n"
        "3) 不要带扩展名，不要解释，只输出一个 JSON 数组，元素顺序与输入完全一致，数量必须相同。\n\n"
        "输入：\n" + "\n".join(f"{i+1}. {n}" for i, n in enumerate(names))
    )


def ask_model(names: list) -> list:
    """让模型批量翻译；失败返回空列表"""
    try:
        from story.generator import _ask_model
    except Exception as e:
        print('  [译名] 无法导入模型调用:', e)
        return []
    try:
        txt = _ask_model("你是游戏素材命名助手，只输出 JSON 数组。",
                         batch_prompt(names), timeout=180) or ""
    except Exception as e:
        print('  [译名] 调用失败:', e)
        return []
    m = re.search(r"\[.*\]", txt, re.S)
    if not m:
        return []
    try:
        arr = json.loads(m.group(0))
    except Exception:
        return []
    arr = [str(x).strip() for x in arr]
    return arr if len(arr) == len(names) else []


def translate_all(names: list) -> dict:
    """返回 {原名: 中文名}"""
    out = {}
    batch = 48
    for i in range(0, len(names), batch):
        chunk = names[i:i + batch]
        got = ask_model(chunk)
        if len(got) != len(chunk):
            print(f'  [译名] 第 {i//batch+1} 批模型没给全 → 用词典兜底')
            got = [fallback_translate(n) for n in chunk]
        for a, b in zip(chunk, got):
            out[a] = _safe(b) or fallback_translate(a)
        print(f'  [译名] {min(i+batch, len(names))}/{len(names)} 完成')
    return out


def apply(mapping: dict, dirs=None, dry=False) -> int:
    """按对照表改名（两个目录都改）；返回改动数"""
    n = 0
    for d in (dirs or SRC_DIRS):
        if not os.path.isdir(d):
            continue
        for f in list(os.listdir(d)):
            if not f.lower().endswith((".ogg", ".wav", ".mp3", ".opus")):
                continue
            key = os.path.splitext(f)[0]
            new = mapping.get(key)
            if not new:
                continue
            ext = os.path.splitext(f)[1]
            target = os.path.join(d, _safe(new) + ext)
            src = os.path.join(d, f)
            if os.path.abspath(src) == os.path.abspath(target):
                continue
            k = 2
            while os.path.exists(target):
                target = os.path.join(d, _safe(new) + f"_{k}" + ext)
                k += 1
            if dry:
                print(f'   [预览] {f} → {os.path.basename(target)}')
            else:
                try:
                    os.rename(src, target)
                except Exception as e:
                    print(f'   ⚠ 改名失败 {f}: {e}')
                    continue
            n += 1
    return n


def collect_names() -> list:
    names = set()
    for d in SRC_DIRS:
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if f.lower().endswith((".ogg", ".wav", ".mp3", ".opus")) and not f.startswith("_"):
                names.add(os.path.splitext(f)[0])
    return sorted(names)


def main():
    dry = "--dry" in sys.argv
    names = collect_names()
    print(f'待翻译音效: {len(names)} 个')
    old_map = {}
    if os.path.exists(MAP_PATH):
        try:
            old_map = json.load(open(MAP_PATH, encoding="utf-8"))
        except Exception:
            old_map = {}
    if old_map and "--redo" not in sys.argv:
        print('已存在对照表，直接用（--redo 可重新翻译）')
        mapping = old_map
    else:
        mapping = translate_all(names)
        json.dump(mapping, open(MAP_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f'对照表已写入 {MAP_PATH}')
    n = apply(mapping, dry=dry)
    print(f'{"预览" if dry else "已改名"} {n} 个文件')
    for k, v in list(mapping.items())[:12]:
        print(f'   {k} → {v}')


if __name__ == "__main__":
    main()
