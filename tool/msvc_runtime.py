# -*- coding: utf-8 -*-
"""PyQt5 自带的**旧 MSVC 运行时**会让 torch 起不来（Windows）—— 这里安全地让它让位给系统的新版。

## 症状（用户 2026-09-24 实测）

桌宠启动到 `[AIpet] 检测到 CUDA 环境: …` 那行就"卡退"，**没有任何 traceback**；
Windows 事件日志里是 `python.exe` 在 `PyQt5\\Qt5\\bin\\MSVCP140.dll` 里
`0xc0000005`（访问违规），偏移每次都一样。

## 根因

`PyQt5-Qt5 5.15.2` 在 `PyQt5\\Qt5\\bin` 里带了一套 **14.26（VS2017）** 的运行时：
`concrt140 / msvcp140 / msvcp140_1 / msvcp140_2 / vcruntime140 / vcruntime140_1`。
而 torch ≥2.x 的 `c10.dll` 是按**更新的** MSVC 运行时构建的。

`run.py` 的顺序恰好把 Qt 放在前面：
第 208 行 `import PyQt5.QtCore`（依赖自检）→ 旧运行时被加载进进程；
第 474 行 `import torch` → `c10.dll` 初始化失败
（`OSError: [WinError 1114] 动态链接库(DLL)初始化例程失败`，在桌宠的窗口上下文里直接 0xC0000005）。

所以**只有"Qt + torch 同进程"的桌宠必崩**，启动器（只有 Qt）、单独跑测试都不会；
反过来"先 torch 再 Qt"也没事。实测在系统 Python 与项目 `.venv` 里都必崩。

## 修法

把这几个**旧**文件改名让位，Windows 就会用系统里的新运行时（`System32\\msvcp140.dll`）。
`System32` 里那份是 14.51（VS2022），向后兼容，Qt 5.15.2 用它没问题
（实测：改名后 Qt 建窗口渲染 + torch + cv2 同进程全通）。

⚠ 安全护栏：
  · 只在"系统里确实存在**更新**版本的对应文件"时才改那一个文件（否则 Qt 可能缺依赖）；
  · 改名 = `<名字>.aipet-disabled`，幂等、可回滚（改回来即可）；
  · 纯文件改名，不动注册表、不下载任何东西。
"""
import os

# PyQt5\Qt5\bin 里那套旧运行时的文件名（Qt 自己的 DLL 不碰）
RUNTIME_NAMES = ("msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll",
                 "vcruntime140.dll", "vcruntime140_1.dll", "concrt140.dll")

DISABLED_SUFFIX = ".aipet-disabled"


def _vs_version(path: str):
    """读 PE 的 VS_FIXEDFILEINFO → (a,b,c,d)；读不到给 ()"""
    try:
        import ctypes
        from ctypes import wintypes
        v = ctypes.windll.version
        size = v.GetFileVersionInfoSizeW(str(path), None)
        if not size:
            return ()
        buf = ctypes.create_string_buffer(size)
        if not v.GetFileVersionInfoW(str(path), 0, size, buf):
            return ()
        ptr = ctypes.c_void_p()
        ln = wintypes.UINT()
        if not v.VerQueryValueW(buf, "\\", ctypes.byref(ptr), ctypes.byref(ln)):
            return ()

        class FIXED(ctypes.Structure):
            _fields_ = [("dwSignature", wintypes.DWORD), ("dwStrucVersion", wintypes.DWORD),
                        ("dwFileVersionMS", wintypes.DWORD), ("dwFileVersionLS", wintypes.DWORD),
                        ("dwProductVersionMS", wintypes.DWORD), ("dwProductVersionLS", wintypes.DWORD),
                        ("dwFileFlagsMask", wintypes.DWORD), ("dwFileFlags", wintypes.DWORD),
                        ("dwFileOS", wintypes.DWORD), ("dwFileType", wintypes.DWORD),
                        ("dwFileSubtype", wintypes.DWORD), ("dwFileDateMS", wintypes.DWORD),
                        ("dwFileDateLS", wintypes.DWORD)]
        fi = ctypes.cast(ptr, ctypes.POINTER(FIXED)).contents
        ms, ls = fi.dwFileVersionMS, fi.dwFileVersionLS
        return (ms >> 16, ms & 0xFFFF, ls >> 16, ls & 0xFFFF)
    except Exception:
        return ()


def pyqt_bin_dir(python_exe: str = None) -> str:
    """给定解释器（默认当前进程）对应的 PyQt5\\Qt5\\bin 目录；找不到给空串"""
    try:
        import importlib.util
        if python_exe:
            # 用子进程问一下（解释器可能不是当前这个）
            import subprocess
            code = "import PyQt5,os;print(os.path.join(os.path.dirname(PyQt5.__file__),'Qt5','bin'))"
            r = subprocess.run([python_exe, "-c", code], capture_output=True, text=True,
                               timeout=25, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            p = (r.stdout or "").strip()
            return p if p and os.path.isdir(p) else ""
        spec = importlib.util.find_spec("PyQt5")     # find_spec 不加载 DLL，安全
        if not spec or not spec.origin:
            return ""
        p = os.path.join(os.path.dirname(spec.origin), "Qt5", "bin")
        return p if os.path.isdir(p) else ""
    except Exception:
        return ""


def plan(bin_dir: str, system_dir: str = None, version_of=None):
    """**纯逻辑**（好测）：算出该把哪些文件让位。

    返回 {"to_disable": [(名字, 旧版本, 系统版本)], "keep": [(名字, 原因)]}
    """
    version_of = version_of or _vs_version
    system_dir = system_dir or os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                                            "System32")
    to_disable, keep = [], []
    for name in RUNTIME_NAMES:
        mine = os.path.join(bin_dir, name)
        if not os.path.isfile(mine):
            continue
        theirs = os.path.join(system_dir, name)
        if not os.path.isfile(theirs):
            keep.append((name, "系统里没有同名的更新版本，保留（免得 Qt 缺依赖）"))
            continue
        v_mine, v_theirs = version_of(mine), version_of(theirs)
        if not v_mine or not v_theirs:
            keep.append((name, "读不到版本信息，保守保留"))
            continue
        if v_theirs > v_mine:
            to_disable.append((name, v_mine, v_theirs))
        else:
            keep.append((name, "系统版本并不更新（%s vs %s）" % (fmt(v_theirs), fmt(v_mine))))
    return {"to_disable": to_disable, "keep": keep}


def fmt(v) -> str:
    return ".".join(str(x) for x in v) if v else "?"


def fix_if_needed(bin_dir: str = None, system_dir: str = None, apply: bool = True,
                  log=None, version_of=None, python_exe: str = None) -> dict:
    """检查并（默认）执行让位。**幂等**：已经让过位就什么都不做。

    返回 {"bin_dir","changed":[...],"kept":[...],"skipped":原因}
    """
    say = log or (lambda m: None)
    out = {"bin_dir": "", "changed": [], "kept": [], "skipped": ""}
    if os.name != "nt":
        out["skipped"] = "非 Windows"
        return out
    bin_dir = bin_dir or pyqt_bin_dir(python_exe)
    if not bin_dir:
        out["skipped"] = "找不到 PyQt5\\Qt5\\bin"
        return out
    out["bin_dir"] = bin_dir
    p = plan(bin_dir, system_dir, version_of)
    out["kept"] = p["keep"]
    for name, v_mine, v_theirs in p["to_disable"]:
        src = os.path.join(bin_dir, name)
        dst = src + DISABLED_SUFFIX
        if apply:
            try:
                if os.path.exists(dst):
                    os.remove(dst)          # 清掉上次的残留，保持只有一个备份
                os.rename(src, dst)
            except Exception as e:
                out["kept"].append((name, "改名失败：%s" % e))
                continue
        out["changed"].append((name, fmt(v_mine), fmt(v_theirs)))
    if out["changed"]:
        say("检测到 PyQt5 自带的旧 MSVC 运行时会让 torch 起不来 → 已让它让位给系统新版")
        for name, v_mine, v_theirs in out["changed"]:
            say("   · %s：自带 %s → 改用系统 %s" % (name, v_mine, v_theirs))
        say("   （改名备份为 *.aipet-disabled，想还原改回来即可）")
    elif not p["to_disable"]:
        say("MSVC 运行时无冲突（PyQt5 自带的这些文件不比系统的新）")
    if out["skipped"]:
        say("跳过：%s" % out["skipped"])
    return out


def conflict_present(bin_dir: str = None, system_dir: str = None,
                     version_of=None, python_exe: str = None) -> bool:
    """只判断"有没有冲突"（不改任何文件）"""
    bin_dir = bin_dir or pyqt_bin_dir(python_exe)
    if not bin_dir:
        return False
    return bool(plan(bin_dir, system_dir, version_of)["to_disable"])


if __name__ == "__main__":       # 手动跑：python -m tool.msvc_runtime [--dry-run]
    import sys
    dry = "--dry-run" in sys.argv
    r = fix_if_needed(apply=not dry, log=lambda m: print("[msvc] " + m))
    print("[msvc] 结果：", "改 %d 个" % len(r["changed"]) if r["changed"] else "无需改动",
          ("（dry-run）" if dry else ""), r["skipped"] or "")
