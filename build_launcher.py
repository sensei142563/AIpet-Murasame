"""PyInstaller 打包脚本 — 构建 AIpet 启动器 EXE（绿色版 onedir 模式）

用法：python build_launcher.py
输出：dist/AIpet-Murasame/  ← 完整绿色版（可直接分发）

架构说明（重要）：
- PCL exe 仅是「UI 壳」，负责显示窗口、启动子进程
- 桌宠本体（run.py / main.py / Live2d / fgimages 等）以「源码+资源」形式
  原样放在 exe 旁边 → 子进程从 exe 目录直接运行源码
- 好处：
  1) 人脸/记忆/配置写在 exe 旁的 data/ face_shibie/ config.json，可持久化
     （修复旧版 --onefile 写入临时目录丢失的问题）
  2) Live2D DLL 在工作目录可稳定加载（修复旧版 DLL 加载失败）
  3) 用户拿到绿色版后只需跑 install.bat 建 venv 即可，与源码工作流一致
"""
import subprocess
import sys
import os
import json
import re
import shutil

# 强制 stdout 使用 UTF-8（避免在管道/GBK 控制台下打印 emoji(✅) 时报 UnicodeEncodeError）
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 确保在项目根目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 铁律：打包启动器必须用"装了 PyQt5"的解释器（桌宠自带 runtime\venv\Scripts\python.exe）。
# 用错解释器时 PyInstaller 不报错、照样出 exe，但产物里整个 PyQt5 都会缺掉 →
# 用户双击 exe 弹 "Failed to execute script 'run_launcher' ... DLL load failed while
# importing QtWidgets"。宁可在这里直接停住。
try:
    import PyQt5  # noqa: F401
    _ = PyQt5.__file__
except Exception as _e:
    print("=" * 60)
    print("[中断] 当前解释器没有 PyQt5，打出来的启动器会打不开！")
    print(f"       解释器: {sys.executable}")
    print(f"       原因  : {_e}")
    print(r"       请改用: runtime\venv\Scripts\python.exe build_launcher.py")
    print("=" * 60)
    raise SystemExit(2)

# 自动选择虚拟环境的 Python（优先 .venv）
python_exe = sys.executable
venv_python = os.path.join(os.path.dirname(__file__), ".venv", "Scripts", "python.exe")
if os.path.exists(venv_python):
    python_exe = venv_python
    print(f"[INFO] 使用虚拟环境 Python: {python_exe}")
else:
    print(f"[INFO] 使用当前 Python: {python_exe}")

# ============ 1. 打包 PCL 壳（只含 UI 依赖，不塞源码/资源）============
# 关键：必须 --exclude-module 排除桌宠本体的大依赖（torch/transformers/whisper 等）。
# 它们由子进程（PCL 启动的 run.py）用 venv 运行，无需进壳；
# 否则 PyInstaller 扫描 .venv 里的 torch 字节码会触发
# "IndexError: tuple index out of range" 崩溃（PyInstaller 6.10 + torch 兼容 bug）。
# 关键：删除陈旧的 .spec 文件！
# PyInstaller 若发现同名 .spec 存在，会直接复用其中的 Analysis 配置（含旧的
# 全部资源打包 + torch hidden-import），导致命令行新参数（--exclude-module等）不生效。
# 方案：每次打包前删除旧的 spec，强制 PyInstaller 按当前命令行参数重新生成。
_stale_spec = os.path.join(os.getcwd(), "AIpet-Murasame.spec")
if os.path.exists(_stale_spec):
    os.remove(_stale_spec)
    print(f"[清理] 已删除旧 spec: {_stale_spec}")

_stale_build = os.path.join(os.getcwd(), "build")
if os.path.exists(_stale_build):
    shutil.rmtree(_stale_build, ignore_errors=True)
    print(f"[清理] 已删除旧 build 目录")

# 清理旧绿色版里已下架的角色包（arona/hiyori），防止重新打包时残留；
# 只删这两个角色目录，不动绿色版内的用户数据（data/ face_shibie/ 等）。
_old_dist_pets = os.path.join("dist", "AIpet-Murasame", "pets")
for _stale_pet in ("arona", "hiyori"):
    _p = os.path.join(_old_dist_pets, _stale_pet)
    if os.path.isdir(_p):
        shutil.rmtree(_p, ignore_errors=True)
        print(f"[清理] 已删除旧绿色版中的角色包 pets/{_stale_pet}/（不随包分发）")

cmd = [
    python_exe, "-m", "PyInstaller",
    "--onedir",
    "--windowed",
    "--name", "AIpet-Murasame",
    "--distpath", "dist",
    "--workpath", "build",
    # PCL UI 图标资源（colors.py 用 __file__ 相对定位 resources）
    "--add-data", f"pcl_launcher/resources{os.pathsep}pcl_launcher/resources",
    # Live2D 着色器（PCL 预览需要，hard-link 到包内 live2d 模块）
    "--add-data", f".venv/Lib/site-packages/live2d/v3/FrameworkShaders{os.pathsep}live2d/v3/FrameworkShaders",
    # 隐式导入（壳真正需要的第三方）
    # 注意：不要加 websocket —— 壳内已删除 import websocket 自检，
    #       websocket 由子进程 run_qq.py 的解释器环境提供，壳不需要。
    "--hidden-import", "OpenGL.GL",
    "--hidden-import", "pygame",
    "--hidden-import", "PyQt5.QtMultimedia",
    "--hidden-import", "live2d.v3",
    # 剧情里的 Live2D 立绘要用桌面端这套运行时（live2d_ui 里 import wave 等标准库）
    "--hidden-import", "wave",
    "--hidden-import", "audioop",
    "--hidden-import", "Live2d.live2d_ui",
    # ===== 页面模块：壳里用「字符串动态导入」懒加载（__import__("pcl_launcher.widgets")）=====
    # PyInstaller 静态分析看不到这种导入 → 必须显式 hidden-import，
    # 否则桌宠/记忆/提示词/设置（widgets.py）与插件（plugins_panel.py）页面会「加载失败」。
    "--hidden-import", "pcl_launcher.widgets",
    "--hidden-import", "pcl_launcher.plugins_panel",
    "--hidden-import", "pcl_launcher.themes_panel",
    "--hidden-import", "pcl_launcher.pet_wizard",
    "--hidden-import", "pcl_launcher.portrait_studio",
    "--hidden-import", "pcl_launcher.silicon_dialog",
    "--hidden-import", "pcl_launcher.silicon_ui",
    "--hidden-import", "pcl_launcher.live2d_preview",
    "--hidden-import", "pcl_launcher.safety",
    "--hidden-import", "story",
    "--hidden-import", "story.store",
    "--hidden-import", "story.plot",
    "--hidden-import", "story.generator",
    "--hidden-import", "story.characters",
    "--hidden-import", "story.assets",
    "--hidden-import", "story.server",
    "--hidden-import", "story.launch",
    "--hidden-import", "story.i18n",
    "--hidden-import", "story.config",
    "--hidden-import", "story.modelcfg",
    "--hidden-import", "pcl_launcher.touch_editor",
    "--hidden-import", "tool.touch_areas",
    # ===== 排除：桌宠本体的重依赖（走子进程 venv，绝不进壳）=====
    "--exclude-module", "torch",
    "--exclude-module", "torchvision",
    "--exclude-module", "torchaudio",
    "--exclude-module", "transformers",
    "--exclude-module", "bitsandbytes",
    "--exclude-module", "peft",
    "--exclude-module", "faster_whisper",
    "--exclude-module", "ctranslate2",
    "--exclude-module", "f5_tts",
    "--exclude-module", "insightface",
    "--exclude-module", "scipy",
    "--exclude-module", "skimage",
    "--exclude-module", "sklearn",
    "--exclude-module", "onnx",
    "--exclude-module", "modelscope",
    "--exclude-module", "rich",
    "--exclude-module", "sounddevice",
    "--exclude-module", "pynput",
    "--exclude-module", "soundfile",
    "--exclude-module", "aiohttp",
    "--exclude-module", "fastapi",
    "--exclude-module", "uvicorn",
    "--exclude-module", "pydantic",
    "--exclude-module", "requests",
    "--exclude-module", "onnxruntime",
    "--icon", "icon.ico",
    "--clean",
    "--noconfirm",
    "run_launcher.py",
]

print("=" * 60)
print("  第 1 步：打包 PCL 启动器壳（onedir）")
print("=" * 60)
print()
print("命令:", " ".join(cmd))
print()

# 中文/非 ASCII 路径修正：PyQt5 在 Python 侧把 Qt 路径按 latin-1 解码成乱码
# （D:/ÏÂÔØ/...），PyInstaller 收集 Qt 插件时会判"目录不存在"→ 打包失败或产物缺 PyQt5
# （exe 双击打不开）。用 PYTHONPATH 注入 tool/pyinstaller_qtfix 还原路径，不动 site-packages。
_env = None
try:
    if any(ord(_c) > 127 for _c in os.getcwd()):
        _fix_dir = os.path.join(os.getcwd(), "tool", "pyinstaller_qtfix")
        if os.path.isfile(os.path.join(_fix_dir, "sitecustomize.py")):
            _env = dict(os.environ)
            _env["PYTHONPATH"] = _fix_dir + os.pathsep + _env.get("PYTHONPATH", "")
            _env["AIPET_QT_PATHFIX"] = "1"
            print("[修正] 项目路径含非 ASCII 字符 → 启用 PyQt5 路径还原补丁（否则收集不到 Qt 插件）")
except Exception as _e:
    print(f"[修正] 路径补丁启用失败（继续尝试打包）: {_e}")

try:
    subprocess.run(cmd, check=True, env=_env)
except subprocess.CalledProcessError:
    print()
    print("=" * 60)
    print("[失败] PyInstaller 打包启动器壳失败，常见原因：")
    print("  · 项目路径含中文，且上面的 [修正] 没生效（产物会缺 PyQt5 → exe 打不开）")
    print(r"  · 用了没装 PyQt5 的解释器（应使用 runtime\venv\Scripts\python.exe）")
    print("=" * 60)
    raise SystemExit(1)

out_dir = os.path.join("dist", "AIpet-Murasame")

# ============ 1.5 补齐 PyInstaller 收集不全的第三方包（cv2 等）============
# 背景：构建机上若 cv2 导入异常（"recursion is detected during loading of cv2"），
# PyInstaller 只抄到 cv2/__init__.py 而漏掉 cv2.pyd 与子包 →
# 绿色版/安装版双击启动器立刻 ImportError: recursion detected（装完用不了）。
# 这里从健康的运行环境把整个 cv2 包原样同步进 _internal，保证开箱可用。
def _sync_pkg(name: str, dest_parent: str):
    srcs = [
        os.path.join("runtime", "venv", "Lib", "site-packages", name),
        os.path.join(".venv", "Lib", "site-packages", name),
    ]
    src = next((s for s in srcs if os.path.isdir(s)), None)
    if not src:
        print(f"[补齐] ⚠ 未找到 {name} 源目录，跳过")
        return
    dst = os.path.join(dest_parent, name)
    n = 0
    for dp, dns, fns in os.walk(src):
        dns[:] = [d for d in dns if d != "__pycache__"]
        rel = os.path.relpath(dp, src)
        target_dir = dst if rel == "." else os.path.join(dst, rel)
        os.makedirs(target_dir, exist_ok=True)
        for fn in fns:
            if fn.endswith((".pyc", ".pyo")):
                continue
            try:
                shutil.copy2(os.path.join(dp, fn), os.path.join(target_dir, fn))
                n += 1
            except Exception:
                pass
    print(f"[补齐] {name}: 同步 {n} 个文件 ← {src}")


_internal = os.path.join(out_dir, "_internal")
if os.path.isdir(_internal):
    if not os.path.exists(os.path.join(_internal, "cv2", "cv2.pyd")):
        print("[补齐] 检测到 _internal/cv2 缺少 cv2.pyd（PyInstaller 收集失败）→ 从运行环境同步")
        _sync_pkg("cv2", _internal)
    else:
        print("[补齐] _internal/cv2 完整 ✓")

    # ===== PyQt5：启动器界面的命根子 =====
    # 缺了它 exe 双击只会弹 "DLL load failed while importing QtWidgets"（用户看不到界面）。
    # 构建解释器里没装 PyQt5 时 PyInstaller 静默漏收 → 这里从运行环境补齐，补不上就停。
    if not os.path.isdir(os.path.join(_internal, "PyQt5")):
        print("[补齐] 检测到 _internal 缺少 PyQt5（PyInstaller 收集失败）→ 从运行环境同步")
        _sync_pkg("PyQt5", _internal)
    if not os.path.isdir(os.path.join(_internal, "PyQt5")):
        print("=" * 60)
        print("[中断] _internal/PyQt5 补不齐 → 装出来的启动器会打不开，停止打包。")
        print(r"       请用 runtime\venv\Scripts\python.exe build_launcher.py 重打。")
        print("=" * 60)
        raise SystemExit(3)
    print("[补齐] _internal/PyQt5 完整 ✓")

    # ===== 启动器界面自己用到的第三方运行库 =====
    # 这些不在打包 venv 里（PyInstaller 收集不到），但界面代码会 import →
    # 缺了就会在界面上弹「No module named 'xxx'」（例如：记忆页微信凭据请求 requests、
    # 解密凭据 Crypto、图片处理 cv2）。统一从 runtime/venv 同步进 _internal。
    for _pkg in ("requests", "urllib3", "certifi", "charset_normalizer", "idna", "Crypto",
                 # 剧情模式的手柄用 pygame（打包 venv 里没有它 → 必须从运行环境同步）
                 "pygame"):
        if os.path.isdir(os.path.join(_internal, _pkg)):
            continue
        _sync_pkg(_pkg, _internal)

# ============ 2. 复制完整项目源码/资源到 exe 旁 ============
print()
print("=" * 60)
print("  第 2 步：复制完整项目到绿色版目录（git 追踪文件）")
print("=" * 60)

# 用 git ls-files 列出所有受版本控制的文件（自动排除 .venv/build/dist/配置隐私等）
try:
    tracked = subprocess.run(
        ["git", "ls-files", "-z"],
        capture_output=True, text=True, encoding="utf-8", check=True
    ).stdout
    files = [f for f in tracked.split("\0") if f]
    print(f"  [git] 发现 {len(files)} 个追踪文件")
except Exception as e:
    print(f"  [警告] git ls-files 失败: {e}，回退为手工清单")
    files = None

# 用户不需要的过时/调试文件（不进入绿色版）
_SKIP_FILES = {
    "run_backup.py",   # 旧版 run.py 备份
    "diagnose_launcher.py",  # 启动诊断脚本（开发者用）
    "AIpet-Murasame.spec",   # 打包时的 spec 产物
}

# 不随绿色版分发的本地自用角色包（第三方模型，授权原因）
_SKIP_PET_DIRS = ("pets/arona/", "pets/hiyori/")

if files is None:
    # 手工兜底清单（git 不可用时）
    top_items = [
        "api.py", "build_launcher.py", "config.example.json", "download.py",
        "icon.ico", "icon.png", "install.bat", "LICENSE", "main.py",
        "prompt.txt", "README.md", "requirements.txt", "重启长语音服务.bat",
        "run.py", "run_launcher.py", "run_qq.py",
        "思源黑体Bold.otf", "启动QQ.bat", "启动桌宠.bat", "启动微信.bat",
        "time_sync_guard.py", "time_sync_guard_runner.bat",
        "安装时间同步守护【管理员】.bat", "修复系统时间同步【管理员】.bat",
        "biaoqingbao", "classes", "fgimages", "Live2d", "longtext",
        "pcl_launcher", "pets", "qq", "reference_voices", "tool", "场景素材",
        "story", "剧情素材",
        "pcl_launcher", "pets", "qq", "reference_voices", "tool", "场景素材",
        "更新日志",   # 启动器「更新日志」读它（由 tool/gen_changelog.py 从 README 生成）
    ]
    files = []
    for item in top_items:
        if os.path.isdir(item):
            for root, dirs, fnames in os.walk(item):
                dirs[:] = [d for d in dirs if d not in ("__pycache__",)]
                for fn in fnames:
                    files.append(os.path.join(root, fn).replace("\\", "/"))
        elif os.path.exists(item):
            files.append(item)

# ===== 追加：git「未追踪」但需要随包分发的新文件 =====
# 教训：pcl_launcher/portrait_studio.py、tool/portrait_outfit.py 等新写的模块
# 未被 git 追踪 → 只按 git ls-files 复制会漏掉 → 安装后启动器/桌宠直接 ModuleNotFoundError。
_UNTRACKED_SKIP_PREFIX = (
    "dist/", "build/", "_internal", ".venv/", "tmp/", "models/", "runtime/",
    "GPT-SoVITS/", "tool/pack/", "data/", "face_shibie/", "__pycache__/",
    "reference_voices/", "NapCat.Shell.Windows.OneKey/", "F5-TTS_Models/", "场景素材/",
)
# 注意：绝不能包含 .pyd / .pyc —— cv2.pyd 等扩展模块漏掉会让安装副本直接起不来
_UNTRACKED_SKIP_SUFFIX = (".log", ".pyo", ".7z", ".tar", ".spec", ".ps1",
                          ".exe", ".zip", ".bin", ".pth")
try:
    _out = subprocess.run(["git", "ls-files", "--others", "--exclude-standard", "-z"],
                          capture_output=True, text=True, encoding="utf-8", check=True).stdout
    _extra = []
    for _f in _out.split("\0"):
        if not _f:
            continue
        _n = _f.replace("\\", "/")
        if any(_n.startswith(_pfx) for _pfx in _UNTRACKED_SKIP_PREFIX):
            continue
        if _n.lower().endswith(_UNTRACKED_SKIP_SUFFIX):
            continue
        if os.path.basename(_n) in _SKIP_FILES or os.path.basename(_n) == "nul":
            continue
        if os.path.basename(_n).startswith(("AIpet-Murasame-安装包", "AIpet-Installer", "payload.zip")):
            continue
        _extra.append(_f)
    if _extra:
        print(f"  [git] 追加未追踪的新文件 {len(_extra)} 个（新模块/资源）")
        files += _extra
except Exception as _e:
    print(f"  [警告] 未追踪文件列表获取失败: {_e}")

copied = 0
for rel in files:
    if rel.startswith(".git"):
        continue
    # 跳过不随包分发的本地自用角色包
    if any(rel.startswith(p) for p in _SKIP_PET_DIRS):
        continue
    # 跳过打码 CG 备份（用户本地留着以备恢复，占 97MB，没必要塞进安装包）
    if rel.startswith("剧情素材/打码CG备份") or rel.startswith("剧情素材\\打码CG备份"):
        continue
    # 跳过过时/调试文件
    if os.path.basename(rel) in _SKIP_FILES:
        continue
    src = os.path.join(os.getcwd(), rel)
    dst = os.path.join(out_dir, rel)
    if not os.path.exists(src):
        continue
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        shutil.copy2(src, dst)
        copied += 1
    except Exception as e:
        print(f"  [跳过] {rel}: {e}")
print(f"  [git] 已复制 {copied} 个文件（已排除 {len(_SKIP_FILES)} 个过时/调试文件）")

# 显式补拷「场景素材」目录（立绘背景场景图；新加目录可能还没纳入 git 追踪）
try:
    _scene_src = os.path.join(os.getcwd(), "场景素材")
    if os.path.isdir(_scene_src):
        _n = 0
        for _r, _dirs, _fs in os.walk(_scene_src):
            _dirs[:] = [d for d in _dirs if d != "__pycache__"]
            for _f in _fs:
                _rel = os.path.relpath(os.path.join(_r, _f), os.getcwd())
                _dst = os.path.join(out_dir, _rel)
                os.makedirs(os.path.dirname(_dst), exist_ok=True)
                shutil.copy2(os.path.join(_r, _f), _dst)
                _n += 1
        print(f"  [复制] 场景素材/ {_n} 个文件 ✅")
except Exception as _e:
    print(f"  [警告] 复制场景素材失败: {_e}")

# ============ 3. 复制被 git 忽略的「模型目录」（语音必需）============
# 说明：F5-TTS_Models 与 GPT-SoVITS 都在 .gitignore 里，git ls-files 不会复制。
# 但它们对语音功能是必需的——F5-TTS 长文本语音需要 F5TTS_v1_Base + vocos 声码器；
# GPT-SoVITS 短文本日语语音需要整个整合包。这里强制手动复制。

def _dir_size_gb(path: str) -> float:
    """估算目录体积（GB），大目录会扫描较久，仅用于提示"""
    try:
        total = 0.0
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in ("__pycache__",)]
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except Exception:
                    pass
        return total / (1024 ** 3)
    except Exception:
        return 0.0


def _copy_tree(src, dst, desc, skip_if_over_gb: float = 0.0):
    """复制整个目录树，返回是否成功；skip_if_over_gb>0 时超体积自动跳过"""
    if not os.path.exists(src):
        print(f"  [跳过] {desc}：源目录不存在 {src}")
        return False
    if os.path.exists(dst):
        print(f"  [跳过] {desc}：已存在")
        return True

    if skip_if_over_gb > 0:
        size_gb = _dir_size_gb(src)
        if size_gb > skip_if_over_gb:
            print(f"  [跳过] {desc}：体积 {size_gb:.1f}GB 超过阈值 {skip_if_over_gb:.0f}GB，未复制")
            print(f"         如需强制复制，请手动设置 AIPET_COPY_GPT_SOVITS=1 后重试")
            return False
        print(f"  [复制] {desc}（{size_gb:.1f}GB）...")
    else:
        print(f"  [复制] {desc} ...")

    try:
        shutil.copytree(src, dst,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.log", "cache", "temp"))
        print(f"  [复制] {desc} ✅")
        return True
    except Exception as e:
        print(f"  [警告] {desc} 复制失败: {e}")
        return False


# 3a. F5-TTS 长文本语音模型（必需，约 1GB 级）
_copy_tree(
    os.path.join(os.getcwd(), "F5-TTS_Models", "F5TTS_v1_Base"),
    os.path.join(out_dir, "F5-TTS_Models", "F5TTS_v1_Base"),
    "F5-TTS_Models/F5TTS_v1_Base"
)
_copy_tree(
    os.path.join(os.getcwd(), "F5-TTS_Models", "vocos-mel-24khz"),
    os.path.join(out_dir, "F5-TTS_Models", "vocos-mel-24khz"),
    "F5-TTS_Models/vocos-mel-24khz"
)

# 3b. GPT-SoVITS 短文本日语语音整合包
# 注意：① 该整合包通常 20~40 GB（含 runtime venv + 预训练权重），强制复制会使绿色版
#      体积爆炸且下载不现实 → 默认「不复制」；
#      ② 缺失时 run.py 会优雅提示、tool/chat.py 会探测跳过，对话文字不受影响；
#      ③ 如需强制复制（例如本地离线分发），设置环境变量 AIPET_COPY_GPT_SOVITS=1。
gtp_src = os.path.join(os.getcwd(), "GPT-SoVITS")
gtp_dst = os.path.join(out_dir, "GPT-SoVITS")
if os.environ.get("AIPET_COPY_GPT_SOVITS", "").strip().lower() in ("1", "true", "yes"):
    if os.path.exists(gtp_src):
        # 防呆：即使强制复制，超过 8GB 也自动跳过（20~40GB 的整合包不该进绿色版）
        _copy_tree(gtp_src, gtp_dst, "GPT-SoVITS", skip_if_over_gb=8.0)
    else:
        print("  [跳过] GPT-SoVITS：未找到整合包")
else:
    print("  [跳过] GPT-SoVITS：默认不复制（整合包 20~40GB 过大，绿色版不含；短文本语音走优雅降级）")
    print("         如需强制复制：设置环境变量 AIPET_COPY_GPT_SOVITS=1 后重新打包")

# ============ 4. 复制 reference_voices（git 忽略 *.wav/*.mp3，必须手动带）============
# 关键：.gitignore 含 *.wav 和 *.mp3 → git ls-files 不会复制任何音频。
# reference_voices 同时服务两个语音引擎：
#   - long_chinese/953244.wav → F5-TTS 长文本音色克隆参考（缺失则整个长文本语音失败）
#   - 情感目录/*.wav|*.mp3    → GPT-SoVITS 短文本情感参考（缺失则跳过语音）
# 因此必须整目录手动复制（含音频）。
# 注意：上一轮打包已生成「只有 asr.txt」的空壳 reference_voices，导致 _copy_tree
# 因目已存在跳过该次复制 → 这里强制先删旧空壳再整目录复制。
_ref_voices_dst = os.path.join(out_dir, "reference_voices")
if os.path.exists(_ref_voices_dst):
    shutil.rmtree(_ref_voices_dst, ignore_errors=True)
    print("  [清理] 已删除旧 reference_voices（空壳，仅含 asr.txt）")
_copy_tree(
    os.path.join(os.getcwd(), "reference_voices"),
    _ref_voices_dst,
    "reference_voices (含 wav/mp3 参考音频)"
)

# ============ 4b. 复制角色包内的语音参考音频（git 忽略 *.wav/*.mp3，必须手动带）============
# 各角色 pets/<id>/voices/ 里的 ref.wav/mp3 决定该角色的音色，但 git 不追踪音频，
# git ls-files 只会复制到 asr.txt → 这里手动补复制「随包分发角色」的音频
# （跳过 _SKIP_PET_DIRS 与 _ 开头的模板/私有角色包）。
_pets_src = os.path.join(os.getcwd(), "pets")
if os.path.isdir(_pets_src):
    _copied_voice = 0
    for _pet_dir in sorted(os.listdir(_pets_src)):
        _pet_path = os.path.join(_pets_src, _pet_dir)
        if not os.path.isdir(_pet_path) or _pet_dir.startswith("_"):
            continue
        if any(("pets/" + _pet_dir + "/").startswith(p) for p in _SKIP_PET_DIRS):
            continue
        _vsrc = os.path.join(_pet_path, "voices")
        if not os.path.isdir(_vsrc):
            continue
        for _root, _dirs, _fnames in os.walk(_vsrc):
            for _fn in _fnames:
                if not _fn.lower().endswith((".wav", ".mp3")):
                    continue
                _s = os.path.join(_root, _fn)
                _d = os.path.join(out_dir, "pets", _pet_dir, "voices",
                                  os.path.relpath(_root, _vsrc), _fn)
                os.makedirs(os.path.dirname(_d), exist_ok=True)
                shutil.copy2(_s, _d)
                _copied_voice += 1
    print(f"  [复制] 角色包语音参考音频 {_copied_voice} 个 ✅")
else:
    print("  [跳过] pets/ 目录不存在")

# ============ 5. 创建必要的数据目录（git 忽略，首次运行自动生成）============
for d in ["data", "face_shibie"]:
    os.makedirs(os.path.join(out_dir, d), exist_ok=True)
print("  [目录] data/ face_shibie/ 已创建")

# ============ 6. 复制 NapCat 一键包（QQ 功能需要，体积大可选）============
# 隐私关键：NapCat 目录里的 config/（含 QQ 号+token 的账号配置）、logs/、cache/、
# guild1.db 等是作者本机的登录数据，绝不能进分发包 → 复制时全部排除，
# 用户拿到的是「全新」NapCat，首次扫码登录后自行配置（与官方一键包一致）。
napcat_src = os.path.join(os.getcwd(), "NapCat.Shell.Windows.OneKey")
napcat_dst = os.path.join(out_dir, "NapCat.Shell.Windows.OneKey")   # ← 加版本核对时漏过这行


def _napcat_version_check(src: str):
    """打包前核对 NapCat 版本是否还是锁定值（NapCat 自带更新器，容易被动升级）。

    逻辑统一在 tool/napcat_version.py 里（启动 QQ 时 run_qq 用的是同一份，
    免得"打包会提醒、直接启动不说"）。
    只警告不中止：万一用户确实要用别的版本，也不该卡住打包；
    但必须**大声**说出来，否则"悄悄换版本分发出去"没人会发现。
    """
    try:
        from tool.napcat_version import check as _check
        findings = _check(os.getcwd(), src)
    except Exception as e:
        print(f"  [版本] ⚠ 版本核对失败: {e}")
        return
    for f in findings:
        if f.get("level") == "warn":
            print("  [版本] " + "!" * 56)
            print(f"  [版本] ⚠⚠ {f.get('msg', '')}")
            print("  [版本] " + "!" * 56)
        else:
            print(f"  [版本] {f.get('msg', '')}")


if os.path.exists(napcat_src) and not os.path.exists(napcat_dst):
    _napcat_version_check(napcat_src)      # 复制前先核对锁定版本（详见该函数说明）
    print("  [复制] NapCat.Shell.Windows.OneKey/ ...")
    shutil.copytree(
        napcat_src, napcat_dst,
        ignore=shutil.ignore_patterns(
            "config", "logs", "cache", "temp",
            "*.log", "*.db", "qrcode.png", "__pycache__",
        )
    )
    print("  [复制] NapCat.Shell.Windows.OneKey/ ✅（已排除本机登录数据 config/logs/cache/db）")
else:
    print("  [跳过] NapCat.Shell.Windows.OneKey/（不存在或已复制）")

print()
print("=" * 60)
print("  绿色版打包完成！")
print(f"  位置: {out_dir}")
print()
# ============ 6. 部署到项目根目录（用户日常就是双击根目录的 exe）============
# 之前这步是手工做的，容易忘 → 打包后自动把新 exe 与 _internal 同步到根目录。
try:
    import filecmp
    _src_exe = os.path.join(out_dir, "AIpet-Murasame.exe")
    if os.path.exists(_src_exe):
        _dst_exe = os.path.join(os.getcwd(), "AIpet-Murasame.exe")
        try:
            shutil.copy2(_src_exe, _dst_exe)
        except PermissionError:
            # 启动器正在运行 → exe 被占用。Windows 允许重命名运行中的 exe，
            # 于是「旧 exe 改名为 .old → 拷新 exe」即可，不用让用户先关程序。
            try:
                _old = _dst_exe + ".old"
                if os.path.exists(_old):
                    os.remove(_old)
                os.replace(_dst_exe, _old)
                shutil.copy2(_src_exe, _dst_exe)
                print("  [部署] 检测到启动器正在运行：旧 exe 已改名 .old，新 exe 已就位 ✅"
                      "（重启启动器后生效）")
            except Exception as _e2:
                print(f"  [部署] ⚠ exe 被占用，未能更新（关掉启动器后重新打包即可）: {_e2}")
        # _internal 增量同步（exe 与它必须同版本）
        _src_int = os.path.join(out_dir, "_internal")
        _dst_int = os.path.join(os.getcwd(), "_internal")
        if os.path.isdir(_src_int):
            n = 0
            for dp, dns, fns in os.walk(_src_int):
                rel = os.path.relpath(dp, _src_int)
                td = _dst_int if rel == "." else os.path.join(_dst_int, rel)
                os.makedirs(td, exist_ok=True)
                for fn in fns:
                    sp = os.path.join(dp, fn)
                    dp2 = os.path.join(td, fn)
                    try:
                        if os.path.exists(dp2) and filecmp.cmp(sp, dp2, shallow=True):
                            continue
                        shutil.copy2(sp, dp2)
                        n += 1
                    except Exception:
                        pass
            print(f"  [部署] 根目录 exe 已更新；_internal 同步 {n} 个文件 ✅")
        else:
            print("  [部署] 根目录 exe 已更新 ✅（未找到 _internal，跳过）")
except Exception as _e:
    print(f"  [部署] ⚠ 同步到根目录失败: {_e}")

print("  目录结构：")
print(f"    {out_dir}/")
print(f"    ├── AIpet-Murasame.exe        ← PCL 启动器（双击）")
print(f"    ├── run.py / main.py ...       ← 桌宠本体（源码）")
print(f"    ├── Live2d/ fgimages/ tool/    ← 资源")
print(f"    ├── install.bat                ← 首次安装（建 venv + 装依赖）")
print(f"    ├── 启动桌宠.bat / 启动QQ.bat")
print(f"    └── data/ face_shibie/         ← 用户数据（可持久化）")
print()
print("  用户使用：复制整个目录 → 双击 install.bat → 启动桌宠.bat")
print("  或：已装 Python 时直接双击 AIpet-Murasame.exe")
print("=" * 60)