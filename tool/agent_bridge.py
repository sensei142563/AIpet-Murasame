# -*- coding: utf-8 -*-
"""把"操作电脑"这类任务交给本机的 agent CLI 去做（桌宠只当调度方）。

为什么不自己写
--------------
远端那条线是手写的：`tool/pc_control.py`（1000 行键鼠）、`tool/uia.py`、`tool/msaa.py`、
`tool/music.py`（2096 行网易云 UI 自动化）… 而这些能力本机**已经有打磨好的 agent**：

    · DSH    `node <npm>/node_modules/@deepseek-ai/dsh/lib/bin.js --profile headless "<任务>"`
             —— 一句话交给它做完，stdout 给答案、stderr 给诊断；工具面最全
             （桌面输入 / 截图 / 浏览器 / 技能），还支持 `--json` 事件流与 `--session-id` 续跑。
    · Codex  `node E:\\Codex\\node_modules\\@openai\\codex\\bin\\codex.js exec "<任务>"`
             —— 需要 CODEX_HOME 与 .codex\\.env 里的密钥（本模块会照它的启动器一样设置）。

设计取舍（都是踩过坑之后的）
--------------------------
· **直接调 node 入口**，不走 .cmd / PowerShell 包装：包装要经过 cmd.exe 解析，
  任务文本里的引号/& | > 会被当命令注入；用 subprocess 的列表参数 + node 则完全安全。
· **输出写临时文件**而不是管道：agent 往往再开子进程，**管道被子进程继承就永远不关**，
  父进程读管道会假死（本项目在探针里真踩过）。写文件 + 轮询进程状态 = 不会挂。
· **超时后杀进程树**（taskkill /F /T）：`subprocess.run(timeout=)` 只杀直接子进程，
  孙进程会活下来继续占资源。
· **默认关闭 + 每次必须主人确认**：`agent_bridge_enabled` 默认 false；即便打开，
  不给 `on_confirm` 回调就一律拒绝执行（fail-safe，绝不自作主张动主人的电脑）。
· 另有一层**廉价黑名单**（关机/格式化/删系统目录/改注册表…），只是防手滑，不是沙箱 ——
  agent 自己的审批与权限模型才是真正的边界。

配置（config.json，缺省见下）
---------------------------
    agent_bridge_enabled   "false"      # 总开关（要主人自己打开）
    agent_backend          "auto"       # auto | dsh | codex
    agent_timeout_sec      600          # 单次任务上限
    agent_dsh_entry        ""           # 可选：直接指定 dsh 的 bin.js / 目录
    agent_codex_entry      ""           # 可选：直接指定 codex 的 bin/codex.js
    agent_codex_home       "E:\\Codex\\.codex"   # 可选：CODEX_HOME（含 .env 密钥）
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_REL = os.path.join("data", "agent_bridge.log")

# 廉价黑名单：明显灾难性的请求直接拒（不是沙箱，只是防手滑）
_DENY = re.compile(
    r"(format\s+[a-z]:|diskpart|shutdown\s+/[sr]|rm\s+-rf\s+/|del\s+/[sq]\s+[a-z]:\\|"
    r"reg\s+(add|delete)\s+HKLM|bcdedit|vssadmin\s+delete|cipher\s+/w)", re.I)


def _say(msg: str) -> None:
    try:
        print(msg)
    except Exception:
        pass


def _cfg() -> dict:
    try:
        from tool.config import get_config
        return get_config(os.path.join(ROOT, "config.json")) or {}
    except Exception:
        return {}


def _as_bool(v, default=False) -> bool:
    try:
        from tool.config import as_bool
        return as_bool(v, default)
    except Exception:
        return str(v).strip().lower() in ("1", "true", "yes", "on", "开")


def enabled() -> bool:
    """总开关（默认关：这种事必须主人自己点头）"""
    return _as_bool(_cfg().get("agent_bridge_enabled", "false"), False)


def backend_pref() -> str:
    return str(_cfg().get("agent_backend") or "auto").strip().lower()


def timeout_sec() -> int:
    try:
        return max(30, min(3600, int(_cfg().get("agent_timeout_sec") or 600)))
    except Exception:
        return 600


def _node_exe() -> str:
    """找不到 node 就没法调这两个 CLI（它们都是 node 程序）"""
    n = shutil.which("node") or shutil.which("node.exe")
    if n:
        return n
    for cand in (os.path.join(os.environ.get("APPDATA", ""), "npm", "node.exe"),
                 r"C:\Program Files\nodejs\node.exe"):
        if cand and os.path.isfile(cand):
            return cand
    return ""


def _resolve_dsh():
    """→ ([node, bin.js], env_extra) 或 None"""
    entry = str(_cfg().get("agent_dsh_entry") or "").strip()
    cands = []
    if entry:
        cands.append(entry if entry.lower().endswith(".js")
                     else os.path.join(entry, "lib", "bin.js"))
    shim = shutil.which("dsh") or shutil.which("dsh.cmd")
    if shim:
        base = os.path.dirname(shim)
        cands.append(os.path.join(base, "node_modules", "@deepseek-ai", "dsh", "lib", "bin.js"))
    npm = os.path.join(os.environ.get("APPDATA", ""), "npm")
    cands.append(os.path.join(npm, "node_modules", "@deepseek-ai", "dsh", "lib", "bin.js"))
    node = _node_exe()
    for c in cands:
        if c and os.path.isfile(c) and node:
            return ([node, c], {})
    return None


def _resolve_codex():
    """→ ([node, codex.js], env_extra) 或 None；env 复刻它的启动器（CODEX_HOME + .env）"""
    entry = str(_cfg().get("agent_codex_entry") or "").strip()
    home = str(_cfg().get("agent_codex_home") or r"E:\Codex\.codex").strip()
    cands = []
    if entry:
        cands.append(entry if entry.lower().endswith(".js")
                     else os.path.join(entry, "bin", "codex.js"))
    if os.path.isdir(os.path.dirname(home)):
        cands.append(os.path.join(os.path.dirname(home), "node_modules", "@openai", "codex",
                                  "bin", "codex.js"))
    node = _node_exe()
    for c in cands:
        if c and os.path.isfile(c) and node:
            env_extra = {"CODEX_HOME": home}
            try:
                envf = os.path.join(home, ".env")
                if os.path.isfile(envf):
                    with open(envf, encoding="utf-8", errors="replace") as f:
                        for line in f:
                            s = line.strip()
                            if not s or s.startswith("#") or "=" not in s:
                                continue
                            k, v = s.split("=", 1)
                            env_extra[k.strip()] = v.strip().strip('"')
            except Exception:
                pass
            return ([node, c], env_extra)
    return None


def available() -> dict:
    """探测两个后端能不能用（只查文件，不真的跑任务）"""
    dsh = _resolve_dsh()
    codex = _resolve_codex()
    out = {"dsh": bool(dsh), "codex": bool(codex), "node": _node_exe(),
           "chosen": None, "reason": ""}
    pref = backend_pref()
    if pref == "dsh":
        out["chosen"] = "dsh" if dsh else None
    elif pref == "codex":
        out["chosen"] = "codex" if codex else None
    else:                                    # auto：优先 DSH，回落 Codex
        out["chosen"] = "dsh" if dsh else ("codex" if codex else None)
    if not out["node"]:
        out["reason"] = "找不到 node（DSH/Codex 都是 node 程序）"
    elif not out["chosen"]:
        out["reason"] = "两个后端都没找到（DSH 的 bin.js / Codex 的 bin/codex.js）"
    return out


def looks_dangerous(task: str) -> bool:
    return bool(_DENY.search(str(task or "")))


def _log(rec: dict):
    try:
        p = os.path.join(ROOT, LOG_REL)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _argv_for(backend: str, task: str):
    if backend == "dsh":
        r = _resolve_dsh()
        return (r[0] + ["--profile", "headless", task], r[1]) if r else (None, {})
    if backend == "codex":
        r = _resolve_codex()
        return (r[0] + ["exec", task], r[1]) if r else (None, {})
    return (None, {})


def run_task(task: str, *, timeout=None, on_confirm=None, cwd=None, is_auto=False) -> dict:
    """让 agent 去做一件事。

    on_confirm(task) -> bool 是**必须**的：主人点头才跑（不给回调 = 一律拒绝，fail-safe）。
    is_auto=True 表示这是**她自己想做的**（主人没开口）—— 会先过 tool.autonomy 的政策：
    只读类允许，改动类要等主人开口，系统/删除/关机类永远不做。
    返回 {ok, backend, output, error, seconds, refused}；任何异常都不抛给调用方。
    """
    t0 = time.time()
    res = {"ok": False, "backend": "", "output": "", "error": "", "seconds": 0.0,
           "refused": ""}
    task = str(task or "").strip()
    if not task:
        res["refused"] = "空任务"
        return res
    if len(task) > 4000:
        res["refused"] = "任务太长（>4000 字）"
        return res
    if not enabled():
        res["refused"] = "agent 桥接没打开（config.json: agent_bridge_enabled）"
        _log({"ts": t0, "task": task[:200], "refused": res["refused"]})
        return res
    if on_confirm is None:
        res["refused"] = "没有确认回调 —— 不替主人做决定（fail-safe）"
        _log({"ts": t0, "task": task[:200], "refused": res["refused"]})
        return res
    if looks_dangerous(task):
        res["refused"] = "任务看起来是破坏性的，已拒绝（防手滑黑名单）"
        _log({"ts": t0, "task": task[:200], "refused": res["refused"]})
        return res
    # 自主行动分档（tool/autonomy）：never 直接拒；quiet 时她自己不主动动手
    try:
        from tool import autonomy as _au
        _ok, _why = _au.allowed(task, is_auto=bool(is_auto))
        if not _ok:
            res["refused"] = _why
            res["tier"] = _au.classify(task)
            _log({"ts": t0, "task": task[:200], "refused": res["refused"],
                  "tier": res["tier"]})
            return res
        res["tier"] = _au.classify(task)
    except Exception:
        pass
    try:
        if not on_confirm(task):
            res["refused"] = "主人取消了"
            _log({"ts": t0, "task": task[:200], "refused": res["refused"]})
            return res
    except Exception as e:
        res["refused"] = "确认环节出错: %s" % type(e).__name__
        return res

    av = available()
    order = [av["chosen"]] if av["chosen"] else []
    for b in ("dsh", "codex"):                     # 回落顺序
        if b not in order and (av.get(b) or backend_pref() == b):
            order.append(b)
    to = int(timeout or timeout_sec())
    tried = []
    for backend in [b for b in order if b]:
        argv, env_extra = _argv_for(backend, task)
        if not argv:
            tried.append("%s: 没找到入口" % backend)
            continue
        out_p = tempfile.NamedTemporaryFile(prefix="aipet_agent_", suffix=".out", delete=False)
        err_p = tempfile.NamedTemporaryFile(prefix="aipet_agent_", suffix=".err", delete=False)
        out_p.close()
        err_p.close()
        proc = None
        try:
            env = dict(os.environ)
            env.update(env_extra)
            env.setdefault("PYTHONIOENCODING", "utf-8")
            creation = 0x08000000 if os.name == "nt" else 0     # CREATE_NO_WINDOW
            with open(out_p.name, "wb") as fo, open(err_p.name, "wb") as fe:
                proc = subprocess.Popen(argv, stdout=fo, stderr=fe, cwd=cwd or ROOT,
                                        env=env, creationflags=creation)
                # ⚠ 不用 communicate(timeout)：agent 会再开子进程，管道被继承就永远不关。
                #   输出已经写文件，这里只等进程结束即可（轮询 + 超时杀树）。
                deadline = time.time() + to
                while proc.poll() is None and time.time() < deadline:
                    time.sleep(0.2)
                if proc.poll() is None:
                    tried.append("%s: 超时(%ds)" % (backend, to))
                    _kill_tree(proc)
                    res["error"] = "超时 %ds 已中止" % to
                    res["backend"] = backend
                    continue
            out = _read_text(out_p.name)
            err = _read_text(err_p.name)
            res.update({"output": out.strip(), "backend": backend,
                        "seconds": round(time.time() - t0, 1)})
            if proc.returncode == 0 and out.strip():
                res["ok"] = True
                break
            res["error"] = (err.strip() or ("退出码 %s" % proc.returncode))[:800]
            tried.append("%s: %s" % (backend, res["error"][:120]))
        except Exception as e:
            tried.append("%s: %s" % (backend, type(e).__name__))
            res["error"] = "%s: %s" % (type(e).__name__, e)
            if proc is not None and proc.poll() is None:
                _kill_tree(proc)
        finally:
            for p in (out_p.name, err_p.name):
                try:
                    os.remove(p)
                except Exception:
                    pass
    res["seconds"] = res.get("seconds") or round(time.time() - t0, 1)
    if tried and not res["ok"]:
        res["error"] = res["error"] or "；".join(tried)
    _log({"ts": t0, "task": task[:200], "backend": res["backend"], "ok": res["ok"],
          "seconds": res["seconds"], "error": res["error"][:200],
          "out_len": len(res["output"])})
    return res


def _read_text(path: str) -> str:
    try:
        with open(path, "rb") as f:
            return f.read().decode("utf-8", "replace")
    except Exception:
        return ""


def _kill_tree(proc):
    """杀进程树：subprocess 的 kill 只杀直接子进程，孙进程会留着继续占资源"""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True, creationflags=0x08000000)
        else:
            proc.kill()
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


if __name__ == "__main__":
    av = available()
    _say("开关: %s（config.json → agent_bridge_enabled）" % enabled())
    _say("node: %s" % (av["node"] or "（没找到）"))
    _say("DSH: %s" % ("可用" if av["dsh"] else "不可用"))
    _say("Codex: %s" % ("可用" if av["codex"] else "不可用"))
    _say("会选: %s %s" % (av["chosen"], ("（%s）" % av["reason"]) if av["reason"] else ""))
    if len(sys.argv) > 1:
        _say("\n试跑（会先问一次）: %s" % sys.argv[1])
        r = run_task(sys.argv[1], on_confirm=lambda t: input("确认执行？(y/N) ").lower() == "y")
        _say(json.dumps(r, ensure_ascii=False, indent=2)[:1500])
