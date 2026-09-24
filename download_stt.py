# -*- coding: utf-8 -*-
"""下载「语音识别（faster-whisper）」模型到项目内的 HF 缓存目录。

为什么需要这个脚本：QQ 语音识别默认开着（config 的 qq_stt_enabled=true），但模型
没有任何随包/下载入口 —— 没模型时 faster-whisper 会去 huggingface.co 找，国内经常不通，
于是「语音识别开着却完全没反应」。这里把模型抓到项目内（`models/hf`，与 tool/stt.py
的 HF_HOME 一致），抓完语音识别即可离线使用。

用法：
    python download_stt.py                 # 下载 config.json 里 stt_model 指定的模型
    python download_stt.py --model small   # 换个小模型（几百 MB，CPU 也跑得动）
    python download_stt.py --check         # 只看本地有没有，不下载

默认走国内镜像（HF_ENDPOINT=https://hf-mirror.com）；想用官方源加 --official。
"""
import argparse
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 与 tool/stt.py 保持一致：模型缓存放项目内（别放 C 盘用户目录，容易被清理工具删）
# 目录名取清楚点：models/stt（语音识别），实际权重在 models/stt/hub/ 下
os.environ.setdefault("HF_HOME", os.path.join(BASE, "models", "stt"))
MIRROR = "https://hf-mirror.com"


def _repo_id(model: str) -> str:
    """模型名 → HF 仓库 id（local 路径原样返回）"""
    if os.path.isdir(model):
        return model
    return "Systran/faster-whisper-%s" % model


def main():
    ap = argparse.ArgumentParser(description="下载 faster-whisper 语音识别模型")
    ap.add_argument("--model", default="", help="模型名（tiny/base/small/medium/large-v3）")
    ap.add_argument("--check", action="store_true", help="只检查本地缓存，不下载")
    ap.add_argument("--official", action="store_true", help="用 huggingface.co 官方源")
    args = ap.parse_args()

    from tool.config import get_config
    model = args.model or str(get_config("./config.json").get("stt_model", "large-v3"))
    repo = _repo_id(model)
    # 实际 HF hub 缓存目录（HF_HOME/hub 是新布局；tool/stt.py 两个都认）
    cache = os.path.join(os.environ["HF_HOME"], "hub")

    from tool.stt import cache_state
    ok, where = cache_state(model)
    print("模型      : %s（HF 仓库 %s）" % (model, repo))
    print("缓存目录  : %s" % cache)
    if ok:
        print("本地状态  : ✅ 已经有了 → %s" % where)
        print("语音识别可以直接用（离线加载，不再联网）。")
        return 0
    print("本地状态  : ❌ 还没有（%s）" % where)
    if args.check:
        return 1

    if not args.official:
        os.environ["HF_ENDPOINT"] = MIRROR
        # ⚠ 镜像 + 新版 Xet 下载后端会跳转到需要鉴权的 CAS 服务器，
        #   报 "HTTP status client error (401 Unauthorized)"（实测踩到过）。
        #   关掉 Xet 走普通 CDN 就正常了。
        os.environ["HF_HUB_DISABLE_XET"] = "1"
        print("下载源    : %s（国内镜像，已关闭 Xet；加 --official 可换官方源）" % MIRROR)
    print("开始下载（large 系列约 3 GB，慢的话换 --model small）...")
    try:
        from huggingface_hub import snapshot_download
        path = snapshot_download(repo_id=repo, cache_dir=cache)
    except Exception as e:
        print("❌ 下载失败: %s" % e)
        print("   可以：① 换镜像/网络重试；② 用更小的模型 python download_stt.py --model small；")
        print("        ③ 不需要语音识别就在设置里关掉「语音识别」。")
        return 2
    print("✅ 下载完成：%s" % path)
    ok2, where2 = cache_state(model)
    print("复查      : %s → %s" % ("已就绪" if ok2 else "仍不完整", where2))
    return 0 if ok2 else 3


if __name__ == "__main__":
    sys.exit(main())
