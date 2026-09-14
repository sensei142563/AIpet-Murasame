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
DEFAULT_DIR = r"D:\AIpet-Murasame"
VERSION = "1.0"
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
        (log or print)(f"[安装] ⚠ 修正 pyvenv.cfg 失败: {e}")


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
        (log or print)(f"[安装] ⚠ 生成 config.json 失败: {e}")


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
            f"$lnk.TargetPath = '{exe}'; "
            f"$lnk.WorkingDirectory = '{install_dir}'; "
            "$lnk.Description = 'AIpet 丛雨 AI 桌宠 启动器'; "
            f"$lnk.IconLocation = '{exe},0'; $lnk.Save()"
        )
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                            "-Command", ps], capture_output=True, timeout=60,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        ok = r.returncode == 0
        (log or print)(f"[安装] 桌面快捷方式: {'已创建' if ok else '创建失败 ' + r.stderr.decode('utf-8', 'ignore')[:120]}")
        return ok
    except Exception as e:
        (log or print)(f"[安装] ⚠ 创建快捷方式失败: {e}")
        return False


def install(install_dir: str, progress=None, make_shortcut=True,
            size_text: str = "") -> tuple:
    """执行安装。progress(done_bytes, total_bytes, current_file) 可为 None。
    返回 (ok, message, log_lines)"""
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

    os.makedirs(install_dir, exist_ok=True)
    total = payload_size(z) or 1
    done = 0
    made_dirs = set()
    try:
        for info, rel in _iter_members(z):
            rel = rel.replace("/", os.sep)
            dst = os.path.join(install_dir, rel)
            d = os.path.dirname(dst)
            if d not in made_dirs:
                os.makedirs(d, exist_ok=True)
                made_dirs.add(d)
            with z.open(info) as src, open(dst, "wb") as out:
                while True:
                    chunk = src.read(1024 * 1024 * 4)
                    if not chunk:
                        break
                    out.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total, rel)
    except Exception as e:
        return False, f"解压失败: {e}", logs

    log(f"[安装] 文件解压完成，共 {done / 1e9:.2f} GB")
    _write_venv_cfg(install_dir, log)
    _ensure_dirs(install_dir)
    _ensure_config(install_dir, log)
    files = _write_manual(install_dir, size_text)
    for f in files:
        log(f"[安装] 已生成说明书: {os.path.basename(f)}")
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

    tip = tk.Label(root, text="提示：安装约需 5 GB 磁盘空间；安装到已有旧版的目录会自动保留 data/、config.json 等个人数据。",
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

    def on_progress(done, total, cur):
        p = int(done * 100 / max(1, total))
        bar["value"] = p
        pct.config(text=f"{p}%")
        lbl.config(text=f"正在安装：{os.path.basename(cur)}   ({done / 1e9:.2f}/{total / 1e9:.2f} GB)")
        root.update_idletasks()

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
            try:
                ok, msg, _logs = install(d, progress=on_progress,
                                         make_shortcut=var_sc.get())
            except Exception as e:
                ok, msg = False, "安装异常：" + str(e) + "\n" + traceback.format_exc()[:800]
            def finish():
                bar["value"] = 100 if ok else bar["value"]
                pct.config(text="100%" if ok else pct.cget("text"))
                say(msg)
                if ok:
                    lbl.config(text="安装完成 ✓")
                    btn.config(text="完成", state="normal", command=root.destroy)
                    if var_open.get():
                        try:
                            os.startfile(os.path.join(d, "使用教程说明书.html"))
                        except Exception:
                            try:
                                os.startfile(os.path.join(d, "使用教程说明书.txt"))
                            except Exception:
                                pass
                    messagebox.showinfo("安装完成",
                                        f"已安装到：\n{d}\n\n"
                                        "下一步：\n"
                                        "1) 打开启动器 → 设置 → 填写对话模型 API Key\n"
                                        "2) 点「启动 AIpet 桌宠」\n\n"
                                        "详见安装目录里的《使用教程说明书》。")
                else:
                    lbl.config(text="安装失败")
                    btn.config(state="normal")
                    messagebox.showerror("安装失败", msg)
            root.after(10, finish)
        threading.Thread(target=work, daemon=True).start()

    btn.config(command=start)
    btn.place(x=254, y=380)
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
