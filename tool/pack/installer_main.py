# -*- coding: utf-8 -*-
"""AIpet 桌宠 安装程序（单文件 exe 的入口）。

载荷形式：本 exe = 安装器本体 + 追加在文件末尾的 payload.zip（ZIP64）。
安装时用 zipfile 直接读取自身（ZIP 允许前缀，Python zipfile 支持自解压式档案）。

用法：
  双击运行          → 图形界面：选安装目录、是否创建桌面快捷方式、进度显示
  AIpet-Installer.exe /S /D=<目录> [/NOSHORTCUT] [/NOOPEN]
                    → 静默安装（供无人值守/自动化测试）

安装过程：
  1) 解压全部文件（保留进度）
  2) 修正运行环境：runtime\\venv\\pyvenv.cfg 的 home 指向随包的 python\\ 目录
  3) 首次安装时用 config.example.json 生成 config.json（安全默认：关闭语音识别）
  4) 创建 data\\ face_shibie\\ tmp\\ 目录
  5) 写入《使用教程说明书》txt + html
  6) 可选创建桌面快捷方式
"""

try:  # 控制台被重定向（管道/日志）时 Windows 会用 GBK 编码 stdout，
    # 打印 emoji 会 UnicodeEncodeError 直接打断进程 → 统一降级成替换字符
    import sys as _sys
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import os
import sys
import shutil
import zipfile
import subprocess
import threading
import traceback

def _silence_std_streams():
    """--windowed 打包后 sys.stdout/stderr 为 None，print 会抛异常 → 换成空写入器"""
    class _Null:
        def write(self, *a):
            return 0
        def flush(self):
            pass
    if sys.stdout is None:
        sys.stdout = _Null()
    if sys.stderr is None:
        sys.stderr = _Null()


APP_NAME = "AIpet 丛雨 AI 桌宠"
INSTALLER_TITLE = f"{APP_NAME} 安装程序"


def _default_dir() -> str:
    """默认安装目录：优先 D:（老用户的习惯），没有 D: 就依次找 E:/F:，
    都没有就落到用户目录里（单盘笔记本很常见，写死 D:\\ 会让默认值直接不可用）。

    ⚠ 原来写死 `D:\\AIpet-Murasame`：只有 C 盘的机器上点「开始安装」就报
      "这个目录不可写"，静默安装 /S 不带 /D 时更是直接抛 FileNotFoundError。
    """
    for drv in ("D:", "E:", "F:"):
        try:
            if os.path.isdir(drv + "\\"):
                return drv + "\\AIpet-Murasame"
        except Exception:
            continue
    return os.path.join(os.path.expanduser("~"), "AIpet-Murasame")


def _app_version() -> str:
    """安装器显示的版本 = 项目版本（取 config.example.json 的 wechat_bot_agent）。

    原来写死 VERSION="1.0"，装出来的包是 1.16.1，用户会以为装错了版本。
    """
    try:
        import json as _json
        base = getattr(sys, "_MEIPASS", None) or os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        p = os.path.join(base, "config.example.json")
        if os.path.isfile(p):
            v = str(_json.load(open(p, encoding="utf-8")).get("wechat_bot_agent", ""))
            if v.startswith("AIpet/"):
                return v.split("/", 1)[1].strip() or "1.0"
    except Exception:
        pass
    return "1.0"


DEFAULT_DIR = _default_dir()
VERSION = _app_version()
PAYLOAD_ZIP_MAGIC = b"PK\x03\x04"


# ── 载荷读取 ────────────────────────────────────────────
def _resource_path(name: str) -> str:
    """PyInstaller 单文件运行时资源解包目录（sys._MEIPASS）里的文件路径"""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, name)


def _self_path() -> str:
    return sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__)


def _open_payload():
    """打开追加在 exe 末尾的 payload.zip（返回 ZipFile 或 None）"""
    p = _self_path()
    try:
        z = zipfile.ZipFile(p)
        if any(n.startswith("app/") for n in z.namelist()):
            return z
    except Exception:
        pass
    # 开发模式兜底：同目录/上级目录的 payload.zip
    for cand in (os.path.join(os.path.dirname(p), "payload.zip"),
                 os.path.join(os.path.dirname(os.path.dirname(p)), "tool", "pack", "build", "payload.zip")):
        if os.path.isfile(cand):
            try:
                return zipfile.ZipFile(cand)
            except Exception:
                pass
    return None


def payload_size(z) -> int:
    try:
        return sum(i.file_size for i in z.infolist())
    except Exception:
        return 0


# ── 安装步骤 ────────────────────────────────────────────
def _iter_members(z):
    for info in z.infolist():
        if info.filename.endswith("/"):
            continue
        if info.filename.startswith("app/"):
            yield info, info.filename[len("app/"):]
        elif info.filename.startswith("extra/"):
            yield info, info.filename[len("extra/"):]
        else:
            yield info, info.filename


def _write_venv_cfg(install_dir: str, log=None) -> None:
    """把 venv 的 pyvenv.cfg 指向随包的便携 Python（保证换目录也能跑）"""
    cfg = os.path.join(install_dir, "runtime", "venv", "pyvenv.cfg")
    py_home = os.path.join(install_dir, "python")
    if not os.path.exists(cfg):
        return
    if not os.path.isdir(py_home):
        return
    try:
        with open(cfg, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
        out, has_home = [], False
        for ln in lines:
            if ln.strip().lower().startswith("home"):
                out.append(f"home = {py_home}")
                has_home = True
            else:
                out.append(ln)
        if not has_home:
            out.insert(0, f"home = {py_home}")
        with open(cfg, "w", encoding="utf-8") as f:
            f.write("\n".join(out) + "\n")
        (log or print)(f"[安装] 已修正运行环境指向: {py_home}")
    except Exception as e:
        (log or print)(f"[安装] 修正 pyvenv.cfg 失败:{e}")


def _ensure_config(install_dir: str, log=None) -> None:
    """首次安装：由 config.example.json 生成 config.json（安全默认值）"""
    dst = os.path.join(install_dir, "config.json")
    src = os.path.join(install_dir, "config.example.json")
    if os.path.exists(dst) or not os.path.exists(src):
        return
    try:
        import json
        with open(src, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        # 分享安装的安全默认值：不占带宽、不误报错、不泄露任何人的信息
        cfg["qq_stt_enabled"] = "false"          # 未附带语音识别模型，默认关闭
        cfg["qq_enabled"] = "false"              # 需要时在启动器里开
        cfg["voice_synthesis_enable"] = "true"   # 语音服务未启动会自动跳过，不影响文字
        cfg.setdefault("qq_owner_id", "")
        cfg.setdefault("qq_master_ids", [])
        with open(dst, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        (log or print)("[安装] 已生成 config.json（请在启动器里填 API Key 与主人 QQ 号）")
    except Exception as e:
        (log or print)(f"[安装] 生成 config.json 失败:{e}")


def _ensure_dirs(install_dir: str) -> None:
    for d in ("data", "face_shibie", "tmp", "场景素材"):
        try:
            os.makedirs(os.path.join(install_dir, d), exist_ok=True)
        except Exception:
            pass


def _write_manual(install_dir: str, size_text: str = "") -> list:
    """写入《使用教程说明书》(txt + html)；模块随安装器 exe 一起打包"""
    mt = None
    try:
        from tool.pack import manual_text as mt   # 打包进 exe 的副本
    except Exception:
        try:
            sys.path.insert(0, install_dir)
            from tool.pack import manual_text as mt
        except Exception:
            mt = None
    if mt is None:
        print("[安装] ⚠ 未找到说明书写入模块")
        return []
    try:
        return mt.write_manual(install_dir, VERSION, size_text or "约 5 GB")
    except Exception as e:
        print(f"[安装] ⚠ 生成说明书失败: {e}")
        return []


def _ps_quote(s: str) -> str:
    """PowerShell 单引号字符串里的单引号要写成两个（''）——不转义就语法错。"""
    return str(s).replace("'", "''")


def _make_shortcut(install_dir: str, log=None) -> bool:
    """在桌面创建快捷方式（走 PowerShell，无需额外依赖）"""
    try:
        exe = os.path.join(install_dir, "AIpet-Murasame.exe")
        if not os.path.exists(exe):
            return False
        ps = (
            "$ws = New-Object -ComObject WScript.Shell; "
            "$lnk = $ws.CreateShortcut([IO.Path]::Combine("
            "[Environment]::GetFolderPath('Desktop'), 'AIpet 丛雨桌宠.lnk')); "
            f"$lnk.TargetPath = '{_ps_quote(exe)}'; "
            f"$lnk.WorkingDirectory = '{_ps_quote(install_dir)}'; "
            "$lnk.Description = 'AIpet 丛雨 AI 桌宠 启动器'; "
            f"$lnk.IconLocation = '{_ps_quote(exe)},0'; $lnk.Save()"
        )
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                            "-Command", ps], capture_output=True, timeout=60,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        ok = r.returncode == 0
        (log or print)(f"[安装] 桌面快捷方式: {'已创建' if ok else '创建失败 ' + r.stderr.decode('utf-8', 'ignore')[:120]}")
        return ok
    except Exception as e:
        (log or print)(f"[安装] 创建快捷方式失败:{e}")
        return False


UNINSTALL_BAT = "卸载 AIpet.bat"


def _write_uninstaller(install_dir: str, log=None) -> None:
    """写入一键卸载脚本 + 注册到「应用和功能」列表。

    原来**完全没有卸载途径**：装完只能自己找目录删、还要自己删桌面快捷方式。
    这里给两样（都不需要管理员权限）：
      · 安装目录里的 `卸载 AIpet.bat`（双击：确认 → 删桌面快捷方式 → 删安装目录）
      · HKCU 的卸载登记项 → Windows「应用和功能」里能看到 AIpet 并能卸载
    """
    try:
        bat = os.path.join(install_dir, UNINSTALL_BAT)
        body = (
            "@echo off\r\n"
            "chcp 65001 >nul\r\n"
            "title AIpet 丛雨桌宠 卸载\r\n"
            "echo.\r\n"
            "echo   即将删除：\r\n"
            f"echo     {install_dir}\r\n"
            "echo     （含聊天记忆 data/、人脸库 face_shibie/、你的配置 config.json）\r\n"
            "echo.\r\n"
            "set /p yes=确认卸载请输入 Y 然后回车：\r\n"
            "if /i not \"%yes%\"==\"Y\" (echo 已取消。& pause & exit /b 0)\r\n"
            "echo 正在删除桌面快捷方式…\r\n"
            "del /f /q \"%USERPROFILE%\\Desktop\\AIpet 丛雨桌宠.lnk\" >nul 2>nul\r\n"
            "echo 正在删除安装目录…\r\n"
            "cd /d \"%TEMP%\"\r\n"
        )
        body += (
            f'rmdir /s /q "{install_dir}" >nul 2>nul\r\n'
            "echo 完成。\r\n"
            "pause\r\n"
        )
        with open(bat, "w", encoding="utf-8") as f:
            f.write(body)
        (log or print)(f"[安装] 已生成卸载脚本: {UNINSTALL_BAT}")
    except Exception as e:
        (log or print)(f"[安装] 生成卸载脚本失败:{e}")
        return
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\AIpet-Murasame"
        k = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
        winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
        winreg.SetValueEx(k, "DisplayVersion", 0, winreg.REG_SZ, VERSION)
        winreg.SetValueEx(k, "InstallLocation", 0, winreg.REG_SZ, install_dir)
        winreg.SetValueEx(k, "UninstallString", 0, winreg.REG_SZ,
                          '"%s"' % os.path.join(install_dir, UNINSTALL_BAT))
        winreg.SetValueEx(k, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(k, "NoRepair", 0, winreg.REG_DWORD, 1)
        icon = os.path.join(install_dir, "icon.ico")
        if os.path.isfile(icon):
            winreg.SetValueEx(k, "DisplayIcon", 0, winreg.REG_SZ, "%s,0" % icon)
        winreg.CloseKey(k)
        (log or print)("[安装] 已注册到「应用和功能」（可从这里卸载）")
    except Exception as e:
        (log or print)(f"[安装] 注册卸载项失败（不影响使用）:{e}")


def _safe_target(install_dir: str, rel: str):
    """把载荷里的相对路径解析成安装目录内的绝对路径；越界就返回 None。

    ⚠ 原来直接 os.path.join(install_dir, rel)：载荷里一条
      `app/../../../x.txt` 就能把文件写到安装目录**外面**（实测确认，见
      _audit_fish9269/test_installer_quality.py 的 zip-slip 用例）。
      正规安装包不该有这种条目（打包器也不会生成），但"能越界"本身就是漏洞：
      载荷一旦损坏/被替换，就能覆盖用户任意文件。
    """
    rel = rel.replace("\\", "/").lstrip("/")
    if not rel or rel.startswith("../") or "/../" in rel or rel == "..":
        return None
    root = os.path.realpath(install_dir)
    dst = os.path.realpath(os.path.join(root, rel.replace("/", os.sep)))
    if dst != root and not dst.startswith(root + os.sep):
        return None
    return dst


def _locked_files(install_dir: str) -> list:
    """旧版是否还在运行：用「改名试探」判断可执行文件有没有被占用。

    Windows 上正在运行的 exe 无法改名（共享冲突），这比 tasklist 可靠：
    不用猜进程名，直接问"这个文件我能不能动它"。
    命中说明旧版启动器或桌宠还在跑 → 覆盖安装必然中途失败（用户看到的是一句
    "解压失败: Permission denied"，然后留下半装状态）。
    """
    locked = []
    for rel in (r"AIpet-Murasame.exe", r"runtime\venv\Scripts\python.exe",
                r"python\python.exe"):
        p = os.path.join(install_dir, rel)
        if not os.path.isfile(p):
            continue
        tmp = p + ".locktest"
        try:
            os.replace(p, tmp)
            os.replace(tmp, p)
        except Exception:
            locked.append(rel)
            try:
                if os.path.exists(tmp):
                    os.replace(tmp, p)
            except Exception:
                pass
    return locked


def _free_space_ok(install_dir: str, need_bytes: int) -> tuple:
    """磁盘空间预检查。返回 (够不够, 剩余字节, 需要字节)。"""
    try:
        import shutil as _sh
        probe = install_dir
        while probe and not os.path.isdir(probe):
            parent = os.path.dirname(probe)
            if parent == probe:
                break
            probe = parent
        free = _sh.disk_usage(probe or os.path.abspath(os.sep)).free
        return free >= need_bytes, free, need_bytes
    except Exception:
        return True, -1, need_bytes


def install(install_dir: str, progress=None, make_shortcut=True,
            size_text: str = "", write_uninstall: bool = True) -> tuple:
    """执行安装。progress(done_bytes, total_bytes, current_file) 可为 None。
    返回 (ok, message, log_lines)

    write_uninstall：是否写卸载脚本并注册到「应用和功能」。默认 True；
    自动化测试传 False（否则会给测试用的临时目录写注册表项，污染用户的卸载列表）。
    """
    logs = []

    def log(m):
        logs.append(m)
        try:
            print(m)
        except Exception:
            pass

    z = _open_payload()
    if z is None:
        return False, "安装包损坏：未找到内置的安装数据（payload）。", logs

    # ── 安装前自检（都在写盘之前，问题要在这里暴露，而不是装到一半）──
    total = payload_size(z) or 1
    try:
        os.makedirs(install_dir, exist_ok=True)
    except Exception as e:
        return False, ("安装目录无法创建：%s\n%s\n（提示：选一个存在的盘符，"
                       "或换到不需要管理员权限的目录）" % (install_dir, e)), logs
    try:
        t = os.path.join(install_dir, ".write_test")
        open(t, "w").close()
        os.remove(t)
    except Exception as e:
        return False, "这个目录不可写：%s\n%s" % (install_dir, e), logs
    locked = _locked_files(install_dir)
    if locked:
        return False, ("旧版程序还在运行，无法覆盖安装：\n  · " + "\n  · ".join(locked) +
                       "\n\n请先关闭「AIpet 桌宠」和启动器（右下角托盘也退出），再重新安装。\n"
                       "（覆盖安装不会删除你的 data/、config.json、人脸库）"), logs
    ok_space, free, need = _free_space_ok(install_dir, int(total * 1.05))
    if not ok_space and free >= 0:
        return False, ("磁盘空间不足：\n  需要约 %.2f GB，%s 只剩 %.2f GB"
                       % (need / 1e9, os.path.splitdrive(os.path.abspath(install_dir))[0] or "该盘",
                          free / 1e9)), logs
    log(f"[安装] 预检查通过（需要约 {total / 1e9:.2f} GB，目标 {install_dir}）")

    done = 0
    made_dirs = set()
    written = []          # 本次真正写入的文件：失败时回滚这些（不动已存在的旧文件）
    skipped = []
    try:
        for info, rel in _iter_members(z):
            dst = _safe_target(install_dir, rel)
            if dst is None:
                skipped.append(rel)
                continue
            d = os.path.dirname(dst)
            if d not in made_dirs:
                os.makedirs(d, exist_ok=True)
                made_dirs.add(d)
            existed = os.path.exists(dst)
            with z.open(info) as src, open(dst, "wb") as out:
                while True:
                    chunk = src.read(1024 * 1024 * 4)
                    if not chunk:
                        break
                    out.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total, rel)
            if not existed:
                written.append(dst)
    except Exception as e:
        # 回滚：只删本次新建的文件（旧文件/用户数据一律不动），避免留下半装状态
        rolled = 0
        for p in reversed(written):
            try:
                if os.path.isfile(p):
                    os.remove(p)
                    rolled += 1
            except Exception:
                pass
        try:
            import shutil as _sh
            for d in sorted(made_dirs, key=len, reverse=True):
                try:
                    if os.path.isdir(d) and not os.listdir(d):
                        _sh.rmdir(d)
                except Exception:
                    pass
        except Exception:
            pass
        log(f"[安装] 失败，已回滚本次新建的 {rolled} 个文件")
        return False, ("解压失败：%s\n\n已回滚本次新建的文件（你原有的数据没动）。\n"
                       "常见原因：旧版还在运行 / 目标目录被别的程序占用 / 磁盘写满。"
                       % e), logs
    if skipped:
        log(f"[安装] 跳过{len(skipped)} 个路径越界的条目（安装包可能已损坏）")

    log(f"[安装] 文件解压完成，共 {done / 1e9:.2f} GB")
    _write_venv_cfg(install_dir, log)
    _ensure_dirs(install_dir)
    _ensure_config(install_dir, log)
    files = _write_manual(install_dir, size_text)
    for f in files:
        log(f"[安装] 已生成说明书: {os.path.basename(f)}")
    if write_uninstall:
        _write_uninstaller(install_dir, log)
    if make_shortcut:
        _make_shortcut(install_dir, log)
    log("[安装] 完成")
    try:
        import datetime
        head = ("安装时间: {t}\n安装目录: {d}\n安装器版本: {v}\n\n".format(
            t=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            d=install_dir, v=VERSION))
        with open(os.path.join(install_dir, "安装日志.txt"), "w", encoding="utf-8") as f:
            f.write(head + "\n".join(logs) + "\n")
    except Exception:
        pass
    return True, "安装完成", logs


# ── 图形界面 ────────────────────────────────────────────
def run_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title(INSTALLER_TITLE)
    root.geometry("640x430")
    root.resizable(False, False)
    # 窗口图标（icon.ico 随安装器 exe 一起打包）
    try:
        for cand in (_resource_path("icon.ico"),
                     os.path.join(os.path.dirname(_self_path()), "icon.ico")):
            if cand and os.path.exists(cand):
                root.iconbitmap(cand)
                break
    except Exception:
        pass

    tk.Label(root, text=f"{APP_NAME}  安装程序", font=("Microsoft YaHei", 15, "bold")).pack(pady=(16, 2))
    tk.Label(root, text=f"版本 {VERSION} · 内含完整运行环境，安装后即可使用",
             font=("Microsoft YaHei", 10), fg="#666").pack()
    tk.Label(root, text="安装目录：", font=("Microsoft YaHei", 10)).place(x=24, y=92)

    var_dir = tk.StringVar(value=DEFAULT_DIR)
    ent = tk.Entry(root, textvariable=var_dir, font=("Microsoft YaHei", 10), width=52)
    ent.place(x=105, y=90)

    def choose_dir():
        d = filedialog.askdirectory(title="选择安装目录", initialdir=os.path.dirname(var_dir.get()) or "D:\\")
        if d:
            var_dir.set(os.path.normpath(d))
    tk.Button(root, text="浏览…", command=choose_dir, font=("Microsoft YaHei", 9)).place(x=530, y=87)

    var_sc = tk.BooleanVar(value=True)
    tk.Checkbutton(root, text="创建桌面快捷方式", variable=var_sc,
                   font=("Microsoft YaHei", 10)).place(x=24, y=128)
    var_open = tk.BooleanVar(value=True)
    tk.Checkbutton(root, text="安装完成后打开使用教程", variable=var_open,
                   font=("Microsoft YaHei", 10)).place(x=210, y=128)

    tip = tk.Label(root, text="提示：安装约需 5 GB 磁盘空间（安装前会检查）；安装到已有旧版的目录会自动保留 "
                              "data/、config.json、人脸库等个人数据。\n"
                              "覆盖安装前请先关闭旧版桌宠与启动器（正在运行时会被占用，安装会中止）。",
                   font=("Microsoft YaHei", 9), fg="#666", wraplength=590, justify="left")
    tip.place(x=24, y=160)

    bar = ttk.Progressbar(root, length=590, mode="determinate")
    bar.place(x=24, y=215)
    lbl = tk.Label(root, text="准备就绪", font=("Microsoft YaHei", 9), fg="#333", anchor="w")
    lbl.place(x=24, y=243)
    pct = tk.Label(root, text="0%", font=("Microsoft YaHei", 9), fg="#333")
    pct.place(x=560, y=243)

    status = tk.Text(root, height=6, width=76, font=("Consolas", 9), bg="#f6f6f8")
    status.place(x=24, y=270)
    status.insert("end", "点击「开始安装」开始。\n")
    status.config(state="disabled")

    def say(m):
        status.config(state="normal")
        status.insert("end", m + "\n")
        status.see("end")
        status.config(state="disabled")
        root.update_idletasks()

    # ⚠ tkinter 不是线程安全的：工作线程**不能**直接改进度条/标签。
    #   原来的 on_progress 就是在子线程里 bar["value"]=…/lbl.config(…)，属于
    #   "平时看着能用、偶发卡死/抛 Tcl 错"的经典写法。改成子线程只往队列里塞，
    #   主线程用 after() 轮询消费。
    import queue
    q = queue.Queue()

    def on_progress(done, total, cur):
        q.put(("progress", done, total, cur))

    def _drain():
        try:
            while True:
                item = q.get_nowait()
                kind = item[0]
                if kind == "progress":
                    _done, _total, cur = item[1], item[2], item[3]
                    p = int(_done * 100 / max(1, _total))
                    bar["value"] = p
                    pct.config(text=f"{p}%")
                    lbl.config(text="正在安装：%s   (%.2f/%.2f GB)"
                               % (os.path.basename(cur), _done / 1e9, _total / 1e9))
                elif kind == "say":
                    say(item[1])
                elif kind == "done":
                    finish(item[1], item[2])
                    return
        except queue.Empty:
            pass
        root.after(100, _drain)

    btn = tk.Button(root, text="开始安装", font=("Microsoft YaHei", 11, "bold"),
                    bg="#c8506e", fg="white", activebackground="#e0607e", width=14)

    def start():
        d = var_dir.get().strip().strip('"')
        if not d:
            messagebox.showwarning("提示", "请先选择安装目录")
            return
        try:
            os.makedirs(d, exist_ok=True)
            t = os.path.join(d, ".write_test")
            open(t, "w").close()
            os.remove(t)
        except Exception as e:
            messagebox.showerror("无法写入", f"这个目录不可写：{d}\n{e}")
            return
        btn.config(state="disabled")
        say(f"开始安装到：{d}")

        def work():
            ok, msg = False, ""
            try:
                ok, msg, _logs = install(d, progress=on_progress,
                                         make_shortcut=var_sc.get())
            except Exception as e:
                ok, msg = False, "安装异常：" + str(e) + "\n" + traceback.format_exc()[:800]
            q.put(("done", ok, msg))
        threading.Thread(target=work, daemon=True).start()

    def finish(ok, msg):
        bar["value"] = 100 if ok else bar["value"]
        pct.config(text="100%" if ok else pct.cget("text"))
        say(msg)
        if ok:
            lbl.config(text="安装完成 ")
            btn.config(text="完成", state="normal", command=root.destroy)
            if var_open.get():
                try:
                    os.startfile(os.path.join(var_dir.get().strip(), "使用教程说明书.html"))
                except Exception:
                    try:
                        os.startfile(os.path.join(var_dir.get().strip(), "使用教程说明书.txt"))
                    except Exception:
                        pass
            messagebox.showinfo("安装完成",
                                f"已安装到：\n{var_dir.get().strip()}\n\n"
                                "下一步：\n"
                                "1) 打开启动器 → 设置 → 填写对话模型 API Key\n"
                                "2) 点「启动 AIpet 桌宠」\n\n"
                                "详见安装目录里的《使用教程说明书》。\n"
                                "（想卸载：Windows「应用和功能」里搜 AIpet，"
                                "或双击安装目录里的「卸载 AIpet.bat」）")
        else:
            lbl.config(text="安装失败")
            btn.config(state="normal")
            messagebox.showerror("安装失败", msg)

    btn.config(command=start)
    btn.place(x=254, y=380)
    root.after(100, _drain)
    root.mainloop()


def run_silent(argv) -> int:
    d = None
    shortcut, open_manual = True, False
    for a in argv:
        al = a.lower()
        if al.startswith("/d="):
            d = a[3:].strip('"')
        elif al.startswith("/dir="):
            d = a[5:].strip('"')
        elif al == "/noshortcut":
            shortcut = False
        elif al == "/noopen":
            open_manual = False
    d = d or DEFAULT_DIR
    print(f"[安装] 静默安装 → {d}")

    def prog(done, total, cur):
        p = int(done * 100 / max(1, total))
        if p % 5 == 0:
            print(f"[安装] {p}% {done / 1e9:.2f}/{total / 1e9:.2f} GB  {os.path.basename(cur)}")

    ok, msg, _ = install(d, progress=prog, make_shortcut=shortcut)
    print(("[安装] " + msg) if ok else ("[安装] 失败: " + msg))
    if ok:
        print(f"[安装] 安装目录: {d}")
        if open_manual:
            try:
                os.startfile(os.path.join(d, "使用教程说明书.html"))
            except Exception:
                pass
    return 0 if ok else 1


if __name__ == "__main__":
    _silence_std_streams()
    argv = sys.argv[1:]
    if any(a.strip().lower() in ("/s", "-s", "--silent", "/silent") for a in argv):
        sys.exit(run_silent(argv))
    run_gui()
