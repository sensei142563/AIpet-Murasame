# -*- coding: utf-8 -*-
"""打包「单文件安装程序」AIpet-Murasame-安装包.exe

流程：
  1) 收集载荷：
       app/   ← 绿色版 dist/AIpet-Murasame（启动器 exe + 源码 + 资源 + NapCat + F5-TTS 模型）
       app/runtime/venv      ← Python 运行环境（依赖全装好，安装即可用）
       app/python            ← 便携版 Python（venv 的基础解释器，瘦身：去掉 site-packages）
       app/场景素材          ← 立绘背景场景图
  2) 打成 payload.zip（ZIP64 + deflate），成员前缀 app/
  3) PyInstaller 打安装器本体（onedir→不是，onefile）
  4) 把 payload.zip 追加到安装器 exe 末尾 → 单个可分发 exe

用法：
  python tool/pack/build_installer.py            # 完整打包
  python tool/pack/build_installer.py --payload  # 只生成 payload.zip
  python tool/pack/build_installer.py --assemble # 只做第 4 步（复用已有 exe/payload）
"""

try:  # 控制台被重定向（管道/日志）时 Windows 会用 GBK 编码 stdout，
    # 打印 emoji 会 UnicodeEncodeError 直接打断进程 → 统一降级成替换字符
    import sys as _sys
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BUILD = os.path.join(BASE, "tool", "pack", "build")
DIST_APP = os.path.join(BASE, "dist", "AIpet-Murasame")
PAYLOAD_ZIP = os.path.join(BUILD, "payload.zip")
INSTALLER_EXE_SRC = os.path.join(BUILD, "installer", "AIpet-Installer.exe")
OUT_EXE = os.path.join(BASE, "AIpet-Murasame-安装包.exe")
BASE_PY = os.environ.get("AIPET_BASE_PY") or sys.base_prefix   # 构建用基础 Python（可用环境变量覆盖）

# 不进入安装包的目录/文件（个人数据、密钥、开发用）
# ⚠ data / face_shibie 必须在这里：绿色版目录（dist/AIpet-Murasame/）是可运行的，
#   一旦在原地跑过一次，它就会在 exe 旁写 data/wechat_credentials.json（微信登录凭据）、
#   data/history.json（聊天历史）、data/qq_memory/、face_shibie/（主人照片）……
#   而本打包脚本的源就是 dist/ —— 不排除就会把这些**装进分发给别人的安装包**。
#   （build_launcher.py 只复制 git 追踪文件，所以 data/ 不会自己长出来；
#     但"跑过一次绿色版"就会长出来，不能指望这一点。）
SKIP_DIRS = {
    ".git", ".venv", "tmp", "build", "dist", "GPT-SoVITS",
    "data", "face_shibie", "logs",          # ← 个人数据/隐私，见上方注释
    "tool/pack", "tool/pack/build", "tool/pack/__pycache__",
}
SKIP_FILES = {"config.json", "AIpet-Murasame.spec", "AIpetDbgCon.spec",
              "AIPetDbg.spec", "AIpet-Dbg.spec", "nul",
              # 安装包自身/自解压产物绝不能进载荷（会把体积撑爆 → exe > 4GB 无法运行）
              "AIpet-Murasame-安装包.exe", "installer.exe", "installer_console.exe",
              "payload.zip"}
MAX_SINGLE_FILE = 2 * 1024 * 1024 * 1024   # 单个文件 > 2GB 视为异常（已知最大模型 1.35GB）
SKIP_SUFFIX = (".pyo", ".log")


def _log(m):
    print(m, flush=True)


def _should_skip(rel: str, is_dir=False) -> bool:
    rel = rel.replace("\\", "/")
    # 调用方一般在"被遍历目录的根"下传相对路径（如 data/x.json）；但载荷里的最终
    # 路径带 app/ 前缀（app/data/x.json）。两种都认，免得换个遍历根就漏。
    cands = [rel, rel[4:]] if rel.startswith("app/") else [rel]
    for d in SKIP_DIRS:
        for c in cands:
            if c == d or c.startswith(d + "/"):
                return True
    if is_dir:
        return False
    base = os.path.basename(rel)
    if base in SKIP_FILES:
        return True
    if base.lower().endswith(SKIP_SUFFIX):
        return True
    # venv 里的 __pycache__ 保留（加速启动），其它缓存清掉
    return False


def _iter_files(root: str, prefix: str, skip_pycache_keep: bool = False):
    """遍历目录产出 (绝对路径, zip 内相对路径)"""
    for dp, dns, fns in os.walk(root):
        rel_dir = os.path.relpath(dp, root)
        rel_dir = "" if rel_dir == "." else rel_dir.replace("\\", "/")
        dns[:] = [d for d in dns if not _should_skip(f"{rel_dir}/{d}".strip("/"), True)]
        for fn in fns:
            rel = f"{rel_dir}/{fn}".strip("/")
            if _should_skip(rel):
                continue
            yield os.path.join(dp, fn), f"{prefix}/{rel}".replace("//", "/")


def _audit_payload(items: list) -> None:
    """装包前自检：载荷里**绝不能**出现个人数据/凭据（漏一个就是隐私事故）。

    为什么不用"看 SKIP_DIRS 对不对"来保证：那种保证只在有人记得改它时成立。
    这里直接只看结果——收集到的 payload 路径里有没有可疑东西，有就中止构建。

    ⚠ 规则必须**精确**，宁可少报也不能乱中止构建：
      第一版写成 `.*credential.*` 通配，结果第三方库的正常源码
      `runtime/venv/Lib/site-packages/huggingface_hub/utils/_git_credential.py`
      就被判成"凭据"、整个打包被中止（实测踩到）。这种检查器比没有更糟——
      会被人直接注释掉。
      所以：只在**应用根这一层**按文件名判（config.json / *.pid / qr*.png），
      目录规则也只认顶层的 data/ face_shibie/ logs/；site-packages、
      python/Lib、NapCat 里的同名文件一律不管。
    """
    danger_dir = re.compile(r"^(app/)?(data|face_shibie|logs)/", re.I)
    danger_top = re.compile(
        r"^(app/)?(config\.json|wechat_credentials\.json|[^/]*\.pid|qr[^/]*\.png)$", re.I)
    bad = []
    for _src, rel in items:
        r = rel.replace("\\", "/")
        if danger_dir.match(r) or danger_top.match(r):
            bad.append(r)
    if bad:
        _log("")
        _log("载荷里出现了个人数据/凭据，已中止构建（不会生成安装包）：")
        for r in sorted(set(bad))[:30]:
            _log(f"    {r}")
        if len(set(bad)) > 30:
            _log(f"    ... 另有 {len(set(bad)) - 30} 个")
        _log("  → 请删除 dist/AIpet-Murasame 下的这些文件（那是本机运行留下的），")
        _log("    或把对应目录补进本文件的 SKIP_DIRS。")
        raise SystemExit(1)


def collect_payload() -> list:
    """收集 (绝对路径, payload 内路径) 列表"""
    items = []
    # ── 1) 绿色版
    if not os.path.isdir(DIST_APP):
        raise SystemExit(f"未找到绿色版目录：{DIST_APP}\n请先运行 build_launcher.py 生成 dist/")
    n0 = len(items)
    items += list(_iter_files(DIST_APP, "app", skip_pycache_keep=True))
    _log(f"  [app/] 绿色版 {len(items) - n0} 个文件 ← {DIST_APP}")

    # ── 2) 运行环境 venv（放在 app/runtime/venv）
    venv = os.path.join(BASE, "runtime", "venv")
    if not os.path.isdir(venv):
        raise SystemExit(f"未找到运行环境：{venv}")
    n1 = len(items)
    items += list(_iter_files(venv, "app/runtime/venv", skip_pycache_keep=True))
    _log(f"  [app/runtime/venv] 运行环境 {len(items) - n1} 个文件")

    # ── 3) 便携 Python（venv 的基础解释器；去掉 site-packages 等大件）
    if os.path.isdir(BASE_PY):
        py_skip = ("Lib/site-packages", "Lib/test", "Lib/idlelib", "Doc", "include", "libs")
        n2 = len(items)
        for dp, dns, fns in os.walk(BASE_PY):
            rel_dir = os.path.relpath(dp, BASE_PY).replace("\\", "/")
            if rel_dir == ".":
                rel_dir = ""
            if any(rel_dir == s or rel_dir.startswith(s + "/") for s in py_skip):
                dns[:] = []
                continue
            dns[:] = [d for d in dns if not any(
                (f"{rel_dir}/{d}".strip("/") == s or f"{rel_dir}/{d}".strip("/").startswith(s + "/"))
                for s in py_skip) and d != "__pycache__"]
            for fn in fns:
                if fn.endswith((".pyc", ".pyo")):
                    continue
                rel = f"{rel_dir}/{fn}".strip("/")
                items.append((os.path.join(dp, fn), f"app/python/{rel}"))
        _log(f"  [app/python] 便携解释器 {len(items) - n2} 个文件 ← {BASE_PY}")
    else:
        _log(f"未找到系统 Python：{BASE_PY}（安装后需自带解释器才能跑，请检查）")

    # ── 4) 场景素材（若绿色版没带上）
    scene = os.path.join(BASE, "场景素材")
    if os.path.isdir(scene):
        n3 = len(items)
        items += list(_iter_files(scene, "app/场景素材"))
        _log(f"  [app/场景素材] {len(items) - n3} 个文件")

    # ── 5) 去重
    # ⚠ 实测踩到：绿色版目录里**已经**带了 场景素材/（build_launcher 会复制进去），
    #   第 4 步又按 BASE/场景素材 加了一遍 → zip 里出现重复条目
    #   （UserWarning: Duplicate name: 'app/场景素材/巷口.JPG'）。重复条目会让
    #   zip 变大、解压时后写覆盖先写（内容一致时无害，不一致时静默丢文件）。
    seen, uniq, dups = set(), [], 0
    for src, rel in items:
        key = rel.replace("\\", "/")
        if key in seen:
            dups += 1
            continue
        seen.add(key)
        uniq.append((src, rel))
    if dups:
        _log(f"  [去重] 丢掉 {dups} 个重复条目（同一路径被收集了两次）")
    items = uniq
    _audit_payload(items)          # 隐私自检（有问题直接中止，别生成安装包）
    return items


def build_payload(level_big: int = 1, level_small: int = 3,
                  small_limit: int = 1024 * 1024) -> tuple:
    """快速打包载荷：
    - 已压缩过的格式（模型/图片/音视频/压缩包）→ ZIP_STORED 直存（打包/解压都最快）
    - 大文件 → deflate level=1（约 70MB/s）
    - 小文件 → deflate level=3
    """
    os.makedirs(BUILD, exist_ok=True)
    items = collect_payload()
    total = sum(os.path.getsize(p) for p, _ in items if os.path.exists(p))
    _log(f"载荷共 {len(items)} 个文件，原始大小 {total / 1e9:.2f} GB")
    t0 = time.time()
    # 已是压缩格式 → 直存（再压收益 <3%，却要多花几倍时间）
    STORE_EXT = (".safetensors", ".mp4", ".jpg", ".jpeg", ".png", ".webp", ".gif",
                 ".mp3", ".wav", ".flac", ".ogg", ".zip", ".7z", ".rar", ".pt",
                 ".pth", ".bin", ".gguf", ".db")
    done = 0
    n_stored = 0
    t_last = time.time()
    with zipfile.ZipFile(PAYLOAD_ZIP, "w", zipfile.ZIP_DEFLATED,
                         allowZip64=True) as z:
        for i, (src, rel) in enumerate(items, 1):
            try:
                sz = os.path.getsize(src)
            except Exception:
                continue
            store = rel.lower().endswith(STORE_EXT)
            try:
                if store:
                    z.write(src, rel, compress_type=zipfile.ZIP_STORED)
                    n_stored += 1
                else:
                    z.write(src, rel, compress_type=zipfile.ZIP_DEFLATED,
                            compresslevel=(level_small if sz <= small_limit else level_big))
                done += sz
            except Exception as e:
                _log(f"跳过{rel}: {e}")
            if i % 4000 == 0 or time.time() - t_last > 20:
                el = time.time() - t0
                _log(f"  打包中 {i}/{len(items)}  {done / 1e9:.2f}/{total / 1e9:.2f} GB  ({el:.0f}s)")
                t_last = time.time()
    size = os.path.getsize(PAYLOAD_ZIP)
    _log(f"payload.zip 完成：{size / 1e9:.2f} GB（压缩率 {size / max(1, total) * 100:.0f}%），"
         f"用时 {time.time() - t0:.0f}s，直存 {n_stored} 个已压缩文件")
    if size > 3.6e9:
        _log("")
        _log("警告：payload 超过 3.6 GB，组装后的安装包可能 > 4 GB 而无法在 Windows 运行！")
        with zipfile.ZipFile(PAYLOAD_ZIP) as zz:
            for i in sorted(zz.infolist(), key=lambda x: -x.file_size)[:10]:
                _log(f"      {i.file_size / 1e9:6.2f} GB  {i.filename}")
    else:
        _log(f"体积正常（组装后约{(size + 15e6) / 1e9:.2f} GB < 4GB 上限）")
    return PAYLOAD_ZIP, size, total


def build_installer_exe(windowed=True):
    """PyInstaller 打安装器本体（onefile，含 manual_text 与图标）。

    windowed=True （默认，正式交付）→ 无控制台窗口，纯图形安装界面。
    windowed=False（调试用）       → 控制台模式，能看到 stdout/stderr。
    图标：使用工程根目录的 icon.ico（安装包 exe 的图标 + 安装界面窗口图标）
    """
    os.makedirs(BUILD, exist_ok=True)
    py = sys.executable
    entry = os.path.join(BASE, "tool", "pack", "installer_main.py")
    out = os.path.join(BUILD, "installer")
    spec_name = "installer" if windowed else "installer_console"
    flags = ["--windowed"] if windowed else ["--console"]
    icon = os.path.join(BASE, "icon.ico")
    icon_args = []
    if os.path.exists(icon):
        icon_args = ["--icon", icon, "--add-data", f"{icon}{os.pathsep}."]
    cmd = [py, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile"] + flags + [
           "--name", spec_name,
           "--distpath", out, "--workpath", os.path.join(BUILD, "pyi_work"),
           "--specpath", os.path.join(BUILD, "pyi_spec"),
           "--paths", BASE,
           "--hidden-import", "tool.pack.manual_text",
           ] + icon_args + [
           entry]
    _log(f"PyInstaller 打安装器本体（{'无窗口' if windowed else '控制台'}）…")
    if os.path.exists(icon):
        _log(f"  图标: {icon}")
    else:
        _log(f"未找到图标{icon}，将用默认图标")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        _log(r.stdout[-3000:])
        _log(r.stderr[-3000:])
        raise SystemExit("安装器本体打包失败")
    exe = os.path.join(out, f"{spec_name}.exe")
    _log(f"安装器本体: {exe}  {os.path.getsize(exe) / 1e6:.1f} MB")
    return exe


def assemble(exe: str, payload: str, out: str) -> str:
    """把 payload.zip 追加到安装器 exe 末尾（ZIP 允许前缀 → 自解压式单文件）"""
    _log("组装单文件安装包（exe + payload）…")
    with open(out, "wb") as w:
        with open(exe, "rb") as f:
            shutil.copyfileobj(f, w, 1024 * 1024)
        with open(payload, "rb") as f:
            shutil.copyfileobj(f, w, 1024 * 1024)
    size = os.path.getsize(out)
    # 校验：能被 zipfile 正确识别
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
    _log(f"完成：{out}  {size / 1e9:.2f} GB，含 {len(names)} 个文件条目")
    return out


if __name__ == "__main__":
    argv = sys.argv[1:]
    only_payload = "--payload" in argv
    only_assemble = "--assemble" in argv
    os.makedirs(BUILD, exist_ok=True)

    if only_assemble:
        # 注意：必须重新打安装器本体（否则复用旧 exe → 漏掉最新改动）
        # 正式交付：无控制台的图形安装器（图标取工程根目录 icon.ico）
        exe = build_installer_exe()
        assemble(exe, PAYLOAD_ZIP, OUT_EXE)
        raise SystemExit(0)

    if not only_payload:
        exe = build_installer_exe()
    p, zip_size, raw = build_payload()
    if not only_payload:
        assemble(exe, p, OUT_EXE)
        _log("\n完成！可分发的安装程序：" + OUT_EXE)
        _log("静默安装示例：AIpet-Murasame-安装包.exe /S /D=D:\\AIpet-Murasame /NOSHORTCUT")
