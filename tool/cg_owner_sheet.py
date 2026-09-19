# -*- coding: utf-8 -*-
"""生成/更新 CG 归属标注表：剧情素材/CG/_CG归属表.csv

用法：python tool/cg_owner_sheet.py
  · 表里每一行 = 一组 CG，第 2 列就是"这张 CG 归谁"——**改这一列**即可
  · 第 2 列可写：丛雨 / 茉子 / 芳乃 / 蕾娜 / 小春 / 芦花 / 共（共通） / 禁用
  · 留空 = 用程序自动判定
  · 重复运行会**保留你已经改过的行**，只补上新出现的 CG
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from story import assets as A  # noqa: E402

HEADER = ["CG组", "归属角色", "原版分类", "帧数", "说明"]
HELP = [
    "# 第 2 列「归属角色」写：丛雨 / 茉子 / 芳乃 / 蕾娜 / 小春 / 芦花 / 共 / 禁用",
    "# 共 = 共通线（不从属某个角色）；禁用 = 剧情里永远不用这张 CG；留空 = 自动判定",
    "# 改完保存即可，程序每次启动会重新读；不用重启，重新生成剧情就生效",
]


def main() -> int:
    path = A.cg_sheet_path()
    groups = sorted((A.any_cg_list() or {}).items())
    if not groups:
        print("⚠ 没找到任何 CG（cg_root = %s）" % A.cg_root())
        return 1

    old = {}
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8-sig", errors="replace", newline="") as fh:
                for row in csv.reader(fh):
                    if row and row[0].strip() and not row[0].strip().startswith("#"):
                        old[row[0].strip()] = row[1].strip() if len(row) > 1 else ""
        except Exception as e:
            print("⚠ 读旧表失败（会新建）：%s" % e)

    rows, kept = [], 0
    for g, frames in groups:
        pet, title = A.cg_pet(g), A.cg_title(g)
        who = old.get(g, "")
        if who:
            kept += 1
        note = "自动判定：%s" % (A.PET_NAMES.get(pet) or pet or "未归属")
        rows.append([g, who, title, len(frames), note])

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        for line in HELP:
            fh.write(line + "\n")
        w = csv.writer(fh)
        w.writerow(HEADER)
        w.writerows(rows)

    print("✅ 已写出 %s" % path)
    print("   共 %d 组 CG，其中保留了你已标注的 %d 组" % (len(rows), kept))
    print("   改「归属角色」那一列后保存即可（可写 丛雨/茉子/芳乃/蕾娜/小春/芦花/共/禁用）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
