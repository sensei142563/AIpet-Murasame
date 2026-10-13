# -*- coding: utf-8 -*-
"""更正包体分析文档里"素材去重可省 6~8MB"那条错误建议。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
MAP = os.path.join(ROOT, "dev", "merge-map")

D = os.path.join(ROOT, "dev", "docs", "安卓包体分析-2026-10-13.md")
ADD = """

---

## 五、⚠ **更正**：`assets/Murasame/`（6.54 MB）**不能删**（我上一轮的建议是错的）

上一轮我在"三、另外两条"里写"`assets/Murasame/` 与 `assets/pets/murasame/live2d/` 是同一套的两份拷贝，
确认没有老代码按旧路径读之后可删，约省 6~8 MB"。**核实后发现该判断不成立**，按原文更正如上。

### 证据（这次搜了 C/C++，上一轮只搜了 kt/java/xml/json/txt —— 漏了 native 侧）
```
app/src/main/cpp/LApp/JniBridgeC.cpp:121
    // 下标对应 LAppLive2DManager::_modelDir（assets 根目录里含 <dir>/<dir>.model3.json 的目录，按名排序）。

app/src/main/cpp/LApp/LAppLive2DManager.cpp:92
    const char MODEL3_JSON[] = u8".model3.json";
app/src/main/cpp/LApp/LAppLive2DManager.cpp:294-299
    // model3.jsonのパスを決定する.
    // ディレクトリ名とmodel3.jsonの名前を一致していることが条件
    modelJsonName += ".model3.json";
```

⇒ **native C++ 侧会扫 assets 根目录**，把"含 `<dir>/<dir>.model3.json`"的目录收集成 `_modelDir`（**按名排序**），
再由 JNI 用下标选择模型。`assets/Murasame/` 里正好有 `Murasame.model3.json` + `Murasame.moc3` + `Murasame.4096/`
+ `motion/` —— 它就是**原生渲染器的模型目录**。

### 结论（两份拷贝服务两个消费方，不是重复）
| 拷贝 | 消费方 | 能不能删 |
|---|---|---|
| `assets/Murasame/`（6.54 MB，24 个文件） | **native C++**（`LAppLive2DManager` 扫 assets 根目录） | ❌ **不能删**，删了 Live2D 渲染会坏 |
| `assets/pets/murasame/live2d/`（15.35 MB） | Kotlin 侧（`File(File(baseDir,"pets"), activePet())`） | ❌ 不能删 |
| `assets/noir/NOIR/`（嵌套一份，2.89 MB） | 需同样方式核实（`noir/noir.model3.json` 是否存在） | ⏳ 未核实，**别猜** |

> 教训：**判断 assets 是否死文件时，必须把 native（cpp/h/cpp/hpp）一起搜** ——
> 这一层的路径常常是**拼出来的**（`.model3.json` 是常量拼接），纯文本搜索也未必命中原样字符串，
> 要看**扫描逻辑**而不是只看引用。

### 真正安全的去重方式（如果将来要做）
不是删目录，而是**改 native 侧的扫描根**：让 `LAppLive2DManager` 从 `pets/<id>/live2d/` 找模型，
然后把 `assets/Murasame/` 移走。**这是代码改动 + 必须真机验证**，属于"等你确认后再动"的一类，
不在低风险清单里。
"""
t = io.open(D, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
if "更正" not in t:
    io.open(D, "w", encoding="utf-8", newline="\n").write(t.rstrip() + ADD)
    print("✓ 已追加更正章节")

MSG = """docs(android): ⚠ 更正包体分析 —— assets/Murasame 不能删（native C++ 在用它）

上一轮我在包体分析里建议"assets/Murasame 与 assets/pets/murasame/live2d 是同一套两份拷贝，
确认无旧路径引用后可删，省 6~8 MB"。**这个判断是错的，本提交更正。**

漏查点：上一轮只搜了 `.kt/.java/.xml/.json/.txt`，**没搜 C/C++**。补搜后拿到决定性证据：
    cpp/LApp/JniBridgeC.cpp:121
      // 下标对应 LAppLive2DManager::_modelDir（assets 根目录里含 <dir>/<dir>.model3.json 的目录，按名排序）
    cpp/LApp/LAppLive2DManager.cpp:92,294-299
      const char MODEL3_JSON[] = u8".model3.json";
      // ディレクトリ名とmodel3.jsonの名前を一致していることが条件 / modelJsonName += ".model3.json";
  ⇒ **native C++ 会扫 assets 根目录**，把含 `<dir>/<dir>.model3.json` 的目录收集成 `_modelDir`（按名排序），
    JNI 用下标选模型。`assets/Murasame/` 里正好有 `Murasame.model3.json` + `Murasame.moc3`
    + `Murasame.4096/` + `motion/` ⇒ 它是**原生渲染器的模型目录**，删了 Live2D 渲染会坏。

  ⇒ 两份拷贝服务**两个消费方**，不是重复：
      assets/Murasame/（6.54 MB）           → native C++（扫 assets 根）
      assets/pets/murasame/live2d/（15.35 MB）→ Kotlin（pets/<id>/live2d）

真正的去重方式是**改 native 侧的扫描根**（让 C++ 也从 pets/<id>/live2d 找），
那是**代码改动 + 必须真机验证**，归入"等用户确认后再动"，不在低风险清单里。

教训（写进文档）：**判断 assets 是否死文件，必须把 native（cpp/h/hpp）一起搜**；
而且这一层的路径常是**拼出来的**（`.model3.json` 常量拼接），要看**扫描逻辑**而不是只看字符串引用。

已做且仍有效的低风险项：删除 assets/asr-zh-14M（**实测省 20.34 MB**，见手机仓 d18ba1c）。
"""
p = os.path.join(MAP, "_msg_correct.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", ROOT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", ROOT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:160])
n = subprocess.run(["git", "-C", ROOT, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True, encoding="utf-8").stdout.strip()
st = subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True,
                    text=True, encoding="utf-8").stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
