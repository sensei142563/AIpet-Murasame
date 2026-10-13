# -*- coding: utf-8 -*-
"""提交换装测试改写 + 图像摘要证据。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
VENV = os.path.join(ROOT, "runtime", "venv", "Scripts", "python.exe")
MAP = os.path.join(ROOT, "dev", "merge-map")

print("=== 全量 ===")
r = subprocess.run([VENV, os.path.join("tests", "run_all.py")], cwd=ROOT, capture_output=True,
                   text=True, encoding="utf-8", errors="replace", timeout=1800)
out = (r.stdout or "") + (r.stderr or "")
for l in out.split("\n"):
    if re.match(r"\s*test_\w+\.py\s+-?\d", l) or "总计" in l:
        print("   " + l.strip()[:135])

# 把结论追加进排查文档
D = os.path.join(ROOT, "dev", "docs", "换装不生效-排查结论-2026-10-13.md")
ADD = """

---

## 五、✅ 找到真 bug 了（2026-10-13 追加，用**图像摘要**定性）

把测试改成走**真实入口** `pet._switch_cloth(名字)`（保存 → `load_outfit` → `swap_body` →
`update_portrait`，正是右键菜单点衣服走的那条路），并把渲染判据从"不透明占比"换成
**图像内容摘要**（前者太粗：实测睡衣/私服/刀服占比都恰好 31.22，会误判）：

```
解析层 cloth_id：{'制服': 1952, '睡衣': 1956, '私服': 1978, '刀服': 1950}      ← 四套全不同 ✓
渲染层 不透明占比：{'制服': 32.61, '睡衣': 31.22, '私服': 31.22, '刀服': 31.22}  ← 后三套相同
渲染层 图像摘要：  {'制服': '53c2f4fc91', '睡衣': '7ee86d5cfa',
                    '私服': '7ee86d5cfa', '刀服': '7ee86d5cfa'}                ← 后三套**像素完全相同** ✗
```

⇒ **制服 → 睡衣 确实变了；睡衣 → 私服 → 刀服 画出来的东西一模一样。**
   也就是说：**换第一次有效，之后换装不再生效** —— 这是**真的产品 bug**（用户从睡袍换便服、
   换刀装会没反应），不是我上一版结论里说的"只是测试入口用错"。上一版结论修正如下：

- **测试入口确实用错了**（写顶层 `b`、把固定 `first_portrait` 当 layers）—— 已修为真实入口；
- 修好入口之后**又暴露了真 bug**：连续换装只有第一次生效。

嫌疑点（下一轮从这里查）：`classes/murasame_class.py::_switch_cloth()`
```python
layers = getattr(self, "_last_portrait_layers", None) or self._first_portrait_for(cur_set)
layers = swap_body(layers, cur_set, _of.get("cloth_id") or 0)   # ← 怀疑这里没换掉身体层
```
第二次起 `_last_portrait_layers` 里已经是**上一件衣服的层号**，若 `swap_body` 只在
"原始身体层号"上做替换（或按已知集合匹配），就会认不出当前这件 → 原样返回 → 画面不变。

**待办**：查 `tool/portrait_outfit.py::swap_body()` 的匹配逻辑，让它能把"当前任意一件衣服的层号"
换成目标层号；补一条"连续换 3 次"的断言防回归。
"""
t = io.open(D, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
if "找到真 bug 了" not in t:
    io.open(D, "w", encoding="utf-8", newline="\n").write(t.rstrip() + ADD)
    print("✓ 结论已追加进排查文档")

MSG = """test(outfit): 换装测试改走真实入口 + 图像摘要判据 —— 并**定出真 bug**：连续换装只有第一次生效

一、测试改写（原写法的两个错）
  · 原来写 `data/portrait_choice.json` 的**顶层 b**，而 murasame 有 `portrait.sets`
    ⇒ 代码读的是 `pets.<id>.<set>`，顶层写法根本不生效；
  · 原来把**固定不变的 `_pet2.first_portrait`** 当 layers 传给 `update_portrait`
    ⇒ 图层参数从没变过，画出来当然一样。
  改为调用**应用自己的换装函数** `pet._switch_cloth(名字)`（保存 → load_outfit → swap_body →
  update_portrait，正是右键菜单点衣服走的那条路），并在结束时还原主人原本的装扮选择。

二、渲染判据换成**图像内容摘要**（原来用"不透明占比"太粗）
  实测睡衣/私服/刀服的占比**恰好都是 31.22** ⇒ 用占比判"换装生效"会误判。
  改为对合成图逐像素取 md5 摘要：画出来只要有一处不同，摘要就不同。

三、✅ 由此定出**真的产品 bug**
```
解析层 cloth_id：{'制服': 1952, '睡衣': 1956, '私服': 1978, '刀服': 1950}   ← 四套全不同 ✓
渲染层 图像摘要：  {'制服': '53c2f4fc91', '睡衣': '7ee86d5cfa',
                    '私服': '7ee86d5cfa', '刀服': '7ee86d5cfa'}             ← 后三套像素完全相同 ✗
```
  ⇒ **制服→睡衣 生效；睡衣→私服→刀服 完全无变化**：**换第一次有效，之后换装不再生效**。
  这是上一版结论（"只是测试入口用错"）的**修正**：入口确实用错了（已修），
  但修好入口后**又暴露了这个真 bug**。
  嫌疑点：`_switch_cloth()` 里 `swap_body(layers, cur_set, cloth_id)` —— 第二次起
  `_last_portrait_layers` 里已是上一件衣服的层号，若 `swap_body` 只认"原始身体层号"就会认不出、
  原样返回 ⇒ 画面不变。**下一轮查 `tool/portrait_outfit.py::swap_body()`**，
  并补"连续换 3 次"的防回归断言。

文档：dev/docs/换装不生效-排查结论-2026-10-13.md 追加第五节（含嫌疑代码与下一步）。
"""
p = os.path.join(MAP, "_msg_outfit2.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:160])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
