# -*- coding: utf-8 -*-
"""把打了码的 CG 从 CG 目录里挪走（挪到 剧情素材/打码CG备份/，可随时搬回来）

背景：解包出来的 03_事件CG 里有些是**打了码**的版本（文件名带 _打码 / _censored），
它们和角色文件夹里**没打码**的那张是同一张图 → 留着只会重复/用错。

用法：python tool/cg_drop_censored.py [--restore]
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from story import assets as A  # noqa: E402

BAD = ("打码", "censored", "马赛克", "mosaic")


def is_bad(name: str) -> bool:
    low = name.lower()
    return any(b in low for b in BAD)


def main() -> int:
    root = A.cg_root()
    if not root or not os.path.isdir(root):
        print("⚠ 找不到 CG 目录")
        return 1
    backup = os.path.join(os.path.dirname(root), "打码CG备份")
    restore = "--restore" in sys.argv
    src_base, dst_base = (backup, root) if restore else (root, backup)

    moved = []
    for dirpath, _dirs, files in os.walk(src_base):
        for f in sorted(files):
            if not f.lower().endswith((".png", ".jpg", ".jpeg")):
                continue
            if not is_bad(f):
                continue
            src = os.path.join(dirpath, f)
            rel = os.path.relpath(dirpath, src_base)
            dst_dir = os.path.join(dst_base, rel) if rel != "." else dst_base
            os.makedirs(dst_dir, exist_ok=True)
            dst = os.path.join(dst_dir, f)
            try:
                shutil.move(src, dst)
                moved.append(os.path.join(rel, f))
            except Exception as e:
                print(f"  ⚠ 挪不动 {f}: {e}")

    act = "搬回" if restore else "挪走"
    print(f"✅ 已{act} {len(moved)} 个打码文件")
    for m in moved[:10]:
        print("   ", m)
    if len(moved) > 10:
        print(f"    … 还有 {len(moved) - 10} 个")
    print(f"   备份位置：{backup if not restore else root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
