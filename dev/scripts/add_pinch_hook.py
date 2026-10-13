# -*- coding: utf-8 -*-
"""在 vrm/index.html 里补 window.__pinch（捏脸的反应）。
  · 与 __poke 区分开：__poke 是"被戳"（切表情 + 轻轻一跳），
    __pinch 是"被捏"—— 她会**扭头躲一下 + 缩一下** + 给一个偏"抗拒"的表情。
  · 优先用 VRM humanoid 的 head 骨骼转头（更像"捏脸"）；取不到就退化为整体旋转。
  · 与 __poke 同风格：入口先查 window.__vrm、全程 try/catch、返回 boolean。
最后做一次 JS 语法检查（有 node 就用 node --check，没有就至少核对括号配平）。
"""
import io
import os
import re
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
F = r"E:\university\order\python\pet\chatter\app\src\main\assets\vrm\index.html"

t = io.open(F, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")

PINCH = '''
// 被"捏"一下（捏脸）：**与 __poke 区分开** —— 被戳是"愣一下+跳"，被捏是"扭头躲+缩一下"。
// 脸是头部的动作，所以优先转 **humanoid 的 head 骨骼**（取不到就退化为整体旋转）。
window.__pinch = function () {
  if (!window.__vrm) return false;
  try {
    const em = window.__vrm.expressionManager;
    if (em) {
      const names = Object.keys(em.expressionMap || {});
      // 偏"抗拒/吃痛"的表情优先，退回到开心，再退到第一个
      const want = names.find(n => /surprised|angry|pain|sad/i.test(n))
                || names.find(n => /happy|joy/i.test(n)) || names[0];
      if (want) { em.setValue(want, 1.0); setTimeout(() => { try { em.setValue(want, 0); } catch (e) {} }, 1200); }
    }
    const h = window.__vrm.humanoid;
    let head = null;
    try { head = h && h.getNormalizedBoneNode ? h.getNormalizedBoneNode('head') : null; } catch (e) { head = null; }
    const target = head || window.__vrm.scene;
    const r0 = target.rotation.y;
    const s = window.__vrm.scene;
    const y0 = s.position.y;
    const t0 = performance.now();
    (function flinch() {
      const k = (performance.now() - t0) / 450;
      if (k >= 1) { target.rotation.y = r0; s.position.y = y0; return; }
      const e = Math.sin(k * Math.PI);          // 起→最大→回原位（正弦包络）
      target.rotation.y = r0 + e * 0.45;        // 扭头躲开
      s.position.y = y0 - e * 0.03;             // 身体缩一下
      requestAnimationFrame(flinch);
    })();
  } catch (e) {}
  return true;
};
'''

if "window.__pinch" in t:
    print("· 已有 __pinch")
else:
    anchor = "window.__setFov = function (deg) {"
    if anchor in t:
        t = t.replace(anchor, PINCH.strip() + "\n" + anchor, 1)
        io.open(F, "w", encoding="utf-8", newline="\n").write(t)
        print("✓ 已在 __setFov 之前插入 window.__pinch")
    else:
        print("✗ 锚点未命中")

# ---------- 语法检查 ----------
print()
print("=== JS 语法检查 ===")
node = shutil.which("node") or shutil.which("node.exe")
# 把 <script> 里的内容抽出来单独喂给 node --check（只查我们改的那段足够）
m = re.search(r"window\.__pinch = function[\s\S]*?\n\};", t)
if not m:
    print("   ✗ 没抽到 __pinch 片段")
else:
    frag = m.group(0)
    tmp = os.path.join(os.environ.get("TEMP", "."), "pinch_check.js")
    io.open(tmp, "w", encoding="utf-8", newline="\n").write(frag + "\n")
    print("   片段 %d 字符 → %s" % (len(frag), tmp))
    if node:
        r = subprocess.run([node, "--check", tmp], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120)
        print("   node --check:", "OK ✓" if r.returncode == 0 else (r.stderr or "")[:200])
    else:
        # 没有 node：至少核对括号/引号配平
        pairs = {"(": ")", "{": "}", "[": "]"}
        st = []
        ok = True
        for ch in frag:
            if ch in pairs:
                st.append(ch)
            elif ch in pairs.values():
                if not st or pairs[st.pop()] != ch:
                    ok = False
                    break
        print("   括号配平:", "OK ✓" if ok and not st else "不配平 ✗")

print()
print("=== 页面里现有的钩子（复核）===")
for i, l in enumerate(io.open(F, encoding="utf-8", errors="replace").read().split("\n"), 1):
    if re.search(r"window\.__(poke|pinch|setPitch|setFov|arPitch|placeOnGround|vrmFeetPx)\s*=", l):
        print("   %4d| %s" % (i, l.strip()[:110]))
