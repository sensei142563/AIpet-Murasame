# -*- coding: utf-8 -*-
"""插件模板：复制这个文件夹，改 plugin.json 和下面的函数就行。

约定：
    rules()            → 返回一段说明，会加进她的提示词（告诉她有这个能力）
    handle(arg)        → 她说【插件:例子】后面的内容会传进来；返回一句结果（她会转述给主人）
    schedule()         → 可选：[(间隔秒, 无参函数)]，桌宠会定期调（最小 30 秒）
    on_load()/on_unload() → 可选

注意：插件跟桌宠同权限运行，别放来源不明的东西进来。
"""
import time


def rules() -> str:
    return "【例子】写一行【插件:例子】随便什么，她会原样念回来。"


def handle(arg: str = "") -> str:
    if not arg:
        return "你没说要我做什么呀。"
    return "你说的「%s」，我记住啦（现在是 %s）。" % (arg, time.strftime("%H:%M"))


def schedule() -> list:
    # 想定期做点什么就返回 [(间隔秒, 函数)]，比如每小时一次
    return []
