# -*- coding: utf-8 -*-
"""立绘工坊命令行工具（供 PCL 启动器以子进程方式调用）。

PCL 启动器是纯 UI 壳（不含 cv2 等桌宠依赖），立绘的选项枚举与图片合成
统一通过 runtime venv 的 Python 执行本脚本完成。

用法：
  python portrait_cli.py list                          → 选项 JSON（含 a/b 两套）
  python portrait_cli.py scenes                        → 场景目录与场景图 JSON
  python portrait_cli.py compose SET CLOTH HAIR EXPR [D1,D2] [out_name] [scene]
  python portrait_cli.py save SET CLOTH [D1,D2]        → 保存该套装扮并设为当前立绘类型
"""
import json
import os
import sys

# 输出统一 UTF-8：避免中文（表情名/服装名）在管道里变成乱码
try:
    import io as _io
    sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace",
                                  line_buffering=True)
    sys.stderr = _io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace",
                                  line_buffering=True)
except Exception:
    pass

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)


def cmd_list():
    """当前角色的立绘信息：类型（layers/single/live2d）+ 两套素材的服装/装饰/表情 + 已保存装扮"""
    from qq.qq_portrait import (clothes_for, decors_for, expression_choices,
                                load_choice)
    from tool.portrait_outfit import SETS, active_set
    from pets.pet_registry import (get_active_pet_id, get_pet_config, get_fgimages_dir,
                                   get_fgimages_prefix, get_portrait_mode,
                                   get_portrait_cfg, get_live2d_model_json,
                                   get_live2d_dir)
    pid = get_active_pet_id()
    cfg = get_pet_config(pid) or {}
    model = cfg.get("model") or {}
    has_fg = bool(get_fgimages_dir(pid))
    l2d_json = get_live2d_model_json(pid) or ""
    out = {
        "sets": list(SETS),
        "active": active_set(),
        "clothes": {}, "decors": {}, "expressions": {}, "saved": {},
        # ===== 角色立绘类型（立绘工坊据此自适应）=====
        "pet": {"id": pid, "name": cfg.get("name") or pid,
                "display_name": cfg.get("display_name") or ""},
        "mode": get_portrait_mode(pid),                 # layers / single
        "has_fgimages": has_fg,
        "has_live2d": bool(l2d_json),
        "default_display": str(model.get("default") or "2d").lower(),   # 2d / live2d
        "prefix": get_fgimages_prefix(pid),
        "portrait": get_portrait_cfg(pid),              # single 模式的表情表 / 默认表情
        "live2d": {"model_json": l2d_json, "dir": get_live2d_dir(pid) or ""},
    }
    for s in SETS:
        out["clothes"][s] = [[str(n), int(c), int(h)] for n, c, h in clothes_for(s)]
        out["decors"][s] = [[str(n), int(d)] for n, d in decors_for(s)]
        out["expressions"][s] = [[str(n), int(i)] for n, i in expression_choices(s)]
        out["saved"][s] = load_choice(s)
    # 场景列表一并返回（工坊以前要再起一个子进程，慢）
    try:
        from qq.qq_portrait import list_scenes, scene_dir
        out["scenes"] = list_scenes()
        out["scene_dir"] = scene_dir()
    except Exception as e:
        out["scenes"] = []
        out["scene_dir"] = ""
        print(f"[PortraitCLI] ⚠ 读取场景失败: {e}", file=sys.stderr)
    # 兼容旧字段（a 套）
    out["clothes_legacy"] = out["clothes"]["a"]
    print(json.dumps(out, ensure_ascii=False))


def cmd_set_emotion(argv):
    """set_emotion 表情名 → 写入 pet.json 的 portrait.default_emotion（单图模式用）"""
    from pets.pet_registry import get_active_pet_id, get_pet_dir
    name = argv[0] if argv and argv[0].strip() else "平静"
    p = os.path.join(get_pet_dir(get_active_pet_id()), "pet.json")
    with open(p, encoding="utf-8") as f:
        cfg = json.load(f)
    pt = cfg.setdefault("portrait", {})
    if not pt.get("emotions"):
        print("FAIL: 该角色不是「每个表情一张图」模式")
        return
    if name not in pt["emotions"]:
        print(f"FAIL: 没有这个表情（可选：{list(pt['emotions'])}）")
        return
    pt["default_emotion"] = name
    with open(p, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    print("OK")


def cmd_set_display(argv):
    """set_display 2d|live2d → 写入 pet.json 的 model.default（桌宠用哪套显示）"""
    from pets.pet_registry import get_active_pet_id, get_pet_dir, get_live2d_model_json
    want = (argv[0] if argv else "2d").strip().lower()
    if want not in ("2d", "live2d"):
        print("FAIL: 只能是 2d / live2d")
        return
    if want == "live2d" and not get_live2d_model_json(get_active_pet_id()):
        print("FAIL: 该角色没有可用的 Live2D 模型")
        return
    p = os.path.join(get_pet_dir(get_active_pet_id()), "pet.json")
    with open(p, encoding="utf-8") as f:
        cfg = json.load(f)
    cfg.setdefault("model", {})["default"] = want
    with open(p, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    print("OK")


def cmd_preview_single(argv):
    """preview_single [表情名] [场景] → 单图模式预览（一张整图 + 场景，返回图片路径）"""
    from qq.qq_portrait import build_portrait
    emo = argv[0] if len(argv) > 0 and argv[0].strip() else ""
    scene = argv[1] if len(argv) > 1 and argv[1].strip() else None
    p = build_portrait(emotion=emo, out_name="qq_portrait_studio.png", _scene=scene)
    print(p or "")


def cmd_preview_full(argv):
    """preview_full [SET] [表情] → 全身 + 透明背景的立绘预览（桌宠设置 / 触摸区域调节用）

    与 compose / preview_single 的区别：不裁上半身、不贴场景背景。
    立绘工坊仍然用带背景的半身合成（那条链路没动）。
    """
    import json as _json
    from qq.qq_portrait import compose_custom, build_portrait
    set_name = argv[0] if len(argv) > 0 and argv[0].strip() else None
    emo = argv[1] if len(argv) > 1 and argv[1].strip() else ""
    out_name = "preview_full.png"
    # 先问一下这个角色是「拼合」还是「单图整图」
    import os as _os
    from pets.pet_registry import get_pet_config
    try:
        _pt = (get_pet_config() or {}).get("portrait") or {}
        _single = str(_pt.get("mode") or "").lower() == "single"
    except Exception:
        _single = False
    if _single:
        p = build_portrait(emo, "", out_name=out_name, full_body=True, no_bg=True,
                           set_name=set_name or "a")
    else:
        # 用该套保存的装扮（服装/发型/表情/装饰）——和桌宠身上那套一致
        from qq.qq_portrait import load_choice, _set_of, pet_portrait_cfg
        try:
            ch = load_choice(_set_of(set_name))
            cloth, hair = int(ch["cloth_id"]), int(ch["hair"])
            decors = list(ch.get("decor") or [])
            expr = int(((pet_portrait_cfg().get("emotions") or {}).get(emo)
                        or (pet_portrait_cfg().get("emotions") or {}).get("平静") or 0))
        except Exception:
            cloth, hair, decors, expr = 1952, 1959, [], 0
        if not expr:
            try:
                from qq.qq_portrait import EMOTION_MAP
                expr = int(EMOTION_MAP.get(emo, EMOTION_MAP.get("平静", (1292, None)))[0])
            except Exception:
                expr = 1292
        p = compose_custom(cloth, hair, expr, decors, out_name=out_name,
                           scene=None, set_name=set_name, full_body=True, no_bg=True)
    print(p or "")


def cmd_compose(argv):
    """compose SET CLOTH HAIR EXPR [decors] [out_name] [scene]"""
    from qq.qq_portrait import compose_custom
    set_name = argv[0] if len(argv) > 0 and argv[0].strip() else None
    cloth = int(argv[1]) if len(argv) > 1 and str(argv[1]).strip() else 1952
    hair = int(argv[2]) if len(argv) > 2 and str(argv[2]).strip() else 1959
    expr = int(argv[3]) if len(argv) > 3 and str(argv[3]).strip() else 1292
    decors = []
    if len(argv) > 4 and argv[4].strip():
        decors = [int(x) for x in argv[4].split(",") if x.strip().isdigit()]
    out_name = argv[5] if len(argv) > 5 and argv[5].strip() else "qq_portrait_studio.png"
    scene = argv[6] if len(argv) > 6 and argv[6].strip() else None
    p = compose_custom(cloth, hair, expr, decors, out_name=out_name,
                       scene=scene, set_name=set_name)
    print(p or "")


def cmd_scenes():
    """场景图列表（含目录信息）→ JSON"""
    from qq.qq_portrait import list_scenes, scene_dir
    out = {"dir": scene_dir(), "scenes": list_scenes()}
    print(json.dumps(out, ensure_ascii=False))


def cmd_save(argv):
    """保存装扮：python portrait_cli.py save SET CLOTH [decor1,decor2]"""
    from qq.qq_portrait import save_choice
    set_name = argv[0] if len(argv) > 0 and argv[0].strip() else "a"
    cloth = argv[1] if len(argv) > 1 and argv[1].strip() else "制服"
    decors = []
    if len(argv) > 2 and argv[2].strip():
        decors = [int(x) for x in argv[2].split(",") if x.strip().isdigit()]
    ok = save_choice(cloth, None, decors, set_name=set_name)
    if ok:
        try:
            from tool.portrait_outfit import set_active
            set_active(set_name)
        except Exception:
            pass
    print("OK" if ok else "FAIL")


if __name__ == "__main__":
    try:
        cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
        if cmd == "list":
            cmd_list()
        elif cmd == "scenes":
            cmd_scenes()
        elif cmd == "compose":
            cmd_compose(sys.argv[2:])
        elif cmd == "save":
            cmd_save(sys.argv[2:])
        elif cmd == "set_emotion":
            cmd_set_emotion(sys.argv[2:])
        elif cmd == "set_display":
            cmd_set_display(sys.argv[2:])
        elif cmd == "preview_full":
            cmd_preview_full(sys.argv[2:])
        elif cmd == "preview_single":
            cmd_preview_single(sys.argv[2:])
        else:
            print("")
    except Exception as e:
        import traceback
        print("ERROR: " + repr(e), file=sys.stderr)
        print("", file=sys.stdout)
        traceback.print_exc(file=sys.stderr)
