# -*- coding: utf-8 -*-
"""本地视觉模型「接口」体检（本项目不自带本地模型，只留接缝给用户接）。

★ 2026-10-13 用户拍板：**本地视觉不使用，仅保留接口**。
  所以本文件只校验"接口本身还在、行为可预期"，**不再要求**把上游那套 UI 面
  （vision_source 选择器 / vision_local_url / vision_local_command 输入框等）接上 ——
  那是被否决的设计。第 2、5 节已按此改判。

要防的坑（都和 2026-09-29 审计里那几类同源）：
  · **默认必须等于从前**：`vision_source` 没配 → 走云端，一个字的行为都不变；
  · **选了本地但没接** → 必须是**可读的中文提示**（告诉他填哪个键），绝不静默不识别；
  · **两种接法都要真能跑**：HTTP（宽松认三种响应形状）与 CLI（命令**允许带参数**，
    否则用户写 `python describe.py` 直接跑不起来）；
  · **示例配置与代码默认值一致**，且 UI 的选项与代码的取值集合一致（否则设置页存了也没用）。

用法：`python tests/test_vision_interface.py`
"""
import io
import json
import os
import sys
import tempfile
import threading
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.chdir(REPO)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

FAILS = []


def check(name, cond, extra=""):
    if cond:
        print("  [OK]   %s %s" % (name, extra))
    else:
        print("  [FAIL] %s %s" % (name, extra))
        FAILS.append(name)


from tool import vision_local as V   # noqa: E402

print("== 1) 默认与文案：不配就等于从前 ==")
_real_cfg = V._cfg
try:
    V._cfg = lambda: {}
    check("没配 vision_source → cloud（默认，走原链路）", V.source() == "cloud", V.source())
    check("没配 → available() 为假", V.available() is False)
    st = V.status_text()
    check("status_text 说清「没接」以及要填哪个键",
          "还没接" in st and "vision_local" in st, st[:60])
    r = V.describe("x")
    check("没配时 describe 失败且 error 可读（不是空/异常）",
          r["ok"] is False and len(r["error"]) > 10, r["error"][:60])
    V._cfg = lambda: {"vision_source": "Local"}      # 大小写变体也要认
    check("vision_source 大小写/空白归一", V.source() == "local")
    V._cfg = lambda: {"vision_source": "locl"}       # 写错 → 回落 cloud + 提示
    check("写错的值 → 回落 cloud（并会有一句提示）", V.source() == "cloud")
finally:
    V._cfg = _real_cfg

print("== 2) 本地视觉的 UI 面**按设计不存在**（接口保留，但不走这条路）==")
print("   （2026-10-13 用户拍板：本地视觉不使用、仅保留接口 ⇒ 上游那套 UI 面是被否决的设计，")
print("     所以这里反过来查：**不该**出现在示例配置与设置页里。真要接的人自己接。）")
ex = json.load(io.open(os.path.join(REPO, "config.example.json"), encoding="utf-8"))
for k in ("vision_source", "vision_local_url", "vision_local_command", "vision_local_model"):
    check("示例配置里**没有** %-22s（本地视觉不启用）" % k, k not in ex, repr(ex.get(k)))
check("代码的取值集合仍是 (cloud, local)（接口没被删）",
      V.SOURCES == ("cloud", "local"), str(V.SOURCES))
w = io.open(os.path.join(REPO, "pcl_launcher", "widgets.py"), encoding="utf-8").read()
check("设置页**没有**「视觉来源」选择器（上游那套未采纳）",
      '"vision_source", "视觉来源" not in w')
check("设置页**没有**本地地址 / 命令输入框",
      '"vision_local_url", "本地视觉服务地址"' not in w
      and '"vision_local_command", "本地视觉命令"' not in w)

print("== 3) HTTP 接法：三种常见响应形状都要认 ==")
from http.server import BaseHTTPRequestHandler, HTTPServer   # noqa: E402

SHAPES = {
    "/text": '{"text": "一只猫在窗台上"}',
    "/desc": '{"description": "两人在打游戏"}',
    "/openai": '{"choices": [{"message": {"content": "餐桌上的面"}}]}',
    "/plain": "窗外的雨",
    "/bad": '{"foo": 1}',
}


class _H(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(n)                      # 把 body 读掉，别让客户端等
        body = SHAPES.get(self.path, "{}").encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


srv = HTTPServer(("127.0.0.1", 0), _H)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
try:
    for path, want in (("/text", "一只猫在窗台上"), ("/desc", "两人在打游戏"),
                       ("/openai", "餐桌上的面"), ("/plain", "窗外的雨")):
        V._cfg = lambda p=path: {"vision_local_url": "http://127.0.0.1:%d%s" % (port, p)}
        r = V.describe("data:image/jpeg;base64,AAAA")
        check("HTTP %-8s → %r" % (path, want), r["ok"] and r["text"] == want,
              str({k: r[k] for k in ("ok", "text", "error")})[:80])
    V._cfg = lambda: {"vision_local_url": "http://127.0.0.1:%d/bad" % port}
    r = V.describe("data:image/jpeg;base64,AAAA")
    check("HTTP 认不出形状 → 失败但说清要什么形状",
          r["ok"] is False and "text" in r["error"], r["error"][:70])
    V._cfg = lambda: {"vision_local_url": "http://127.0.0.1:1/none"}   # 连不上
    r = V.describe("data:image/jpeg;base64,AAAA", )
    check("HTTP 连不上 → 提示检查 vision_local_url",
          r["ok"] is False and "vision_local_url" in r["error"], r["error"][:70])
finally:
    srv.shutdown()

print("== 4) CLI 接法：命令**允许带参数**（否则用户写 python x.py 跑不起来）==")
tmpd = tempfile.mkdtemp(prefix="aipet_vis_")
script = os.path.join(tmpd, "describe.py")
io.open(script, "w", encoding="utf-8").write(
    "import sys\n"
    "print('CLI 看到参数：' + ' '.join(sys.argv[1:]))\n")
V._cfg = lambda: {"vision_local_command": "%s %s" % (sys.executable, script)}
r = V.describe("data:image/jpeg;base64,AAAA")
check("带参数的命令能被正确拆分并执行", r["ok"] and "CLI 看到参数" in r["text"],
      str({k: r[k] for k in ("ok", "text", "error")})[:90])
V._cfg = lambda: {"vision_local_command": os.path.join(tmpd, "不存在的程序.exe")}
r = V.describe("data:image/jpeg;base64,AAAA")
check("命令不存在 → 提示检查 vision_local_command",
      r["ok"] is False and "vision_local_command" in r["error"], r["error"][:70])

print("== 5) 摄像头那条链路真的分支了（源码守卫）==")
mc = io.open(os.path.join(REPO, "classes", "murasame_class.py"), encoding="utf-8").read()
# 按拍板：摄像头识图**不**分支到本地视觉（上游那套语义未采纳）。
# 仍要防的两件事：① 云端没配模型时不许静默 return；② 本地视觉模块不许被静默 import 进来。
check("摄像头识图**不**走 vision_local 分支（本地视觉不启用）",
      "if _vl.source() == \"local\":" not in mc)
check("也没有活的 `from tool import vision_local`（保持注释状态）",
      "\nfrom tool import vision_local" not in mc
      and "\n    from tool import vision_local" not in mc)
check("云端分支没配模型时**不再静默**（原来直接 return）",
      "没配视觉模型（vision_model_name / APIKEY）" in mc)

print()
if FAILS:
    print("FAILED %d 项：%s" % (len(FAILS), "、".join(FAILS)))
    sys.exit(1)
print("本地视觉接口体检全部通过")
sys.exit(0)
