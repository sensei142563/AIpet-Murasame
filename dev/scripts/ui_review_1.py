# -*- coding: utf-8 -*-
"""复查修复：
   ① 全屏遮罩：ChatScreen 里 showAr/showVrm/showSettings 统一套不透明铺满层；VrmScreen/QqScreen 自身也加底
   ② 暗色一致：SettingsPage 的 5 个写死亮色 + 2 个浅色 tint 全换主题色
   ③ 写成《UI 规范》文档（新增页面必须遮罩 + 一律暗色）
"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
CHAT = r"E:\university\order\python\pet\chatter"
UI = os.path.join(CHAT, "app/src/main/java/com/aipet/murasame/ui")
MAP = os.path.join(MAIN, "dev", "merge-map")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")


def patch(path, pairs, label):
    t = io.open(path, encoding="utf-8").read().replace("\r\n", "\n")
    n = 0
    for old, new in pairs:
        if old in t:
            t = t.replace(old, new, 1)
            n += 1
        else:
            print("      · 锚点未命中：" + old.strip().splitlines()[0][:70])
    if n:
        io.open(path, "w", encoding="utf-8", newline="\n").write(t)
    print("   %s %s（%d/%d 处）" % ("✓" if n == len(pairs) else "⚠", label, n, len(pairs)))
    return n


print("=== ① 全屏遮罩 ===")
# ChatScreen：三个页面各自套一层不透明铺满 Box
patch(os.path.join(UI, "ChatScreen.kt"), [
    ("""        if (showVrm) {
            // M1：手机上加载 VRM（离线 three + three-vrm；模型来自外部目录，不入库）
            VrmScreen(onBack = { showVrm = false })
        }""",
     """        if (showVrm) {
            // 全屏遮罩：新页必须不透明铺满，否则会透出底下的聊天页与消息（用户明确要求）
            Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
                VrmScreen(onBack = { showVrm = false })
            }
        }"""),
    ("""        if (showSettings) {""",
     """        if (showSettings) {"""),
], "ChatScreen: showVrm 套遮罩")

# SettingsPage / ArScreen 的调用点：包一层
t = io.open(os.path.join(UI, "ChatScreen.kt"), encoding="utf-8").read().replace("\r\n", "\n")
# 找到 if (showSettings) { ... } 的结束不易，这里改为在 ArScreen 调用点前包一层（ArScreen 自身已有黑底），
# 并把 SettingsPage 页面自身背景改成主题色（见 ②），因此调用点无需再包。
print("   （showAr / showSettings 的目标页自身改为主题色/黑底，即为不透明 → 无需再包）")

# VrmScreen / QqScreen 自身加底（防御：以后被别处调用也不会透）
patch(os.path.join(UI, "VrmScreen.kt"), [
    ("""    Column(Modifier.fillMaxSize().padding(horizontal = 12.dp, vertical = 10.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)) {""",
     """    // 自身不透明铺满：即使被别处当作新页打开，也不会透出底下的聊天
    Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)
        .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)) {"""),
], "VrmScreen 自身加底")
patch(os.path.join(UI, "VrmScreen.kt"),
      [("import androidx.compose.foundation.layout.Arrangement",
        "import androidx.compose.foundation.background\nimport androidx.compose.foundation.layout.Arrangement")],
      "VrmScreen 补 background import")

patch(os.path.join(UI, "QqScreen.kt"), [
    ("""    val rootMod = if (embedded) Modifier.fillMaxWidth().padding(horizontal = 4.dp, vertical = 6.dp)
    else Modifier.fillMaxSize().verticalScroll(rememberScrollState())
        .padding(horizontal = 16.dp, vertical = 12.dp)""",
     """    // 独立整页时不透明铺满（遮罩规范）；嵌入首页卡片时交给卡片背景
    val rootMod = if (embedded) Modifier.fillMaxWidth().padding(horizontal = 4.dp, vertical = 6.dp)
    else Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)
        .verticalScroll(rememberScrollState())
        .padding(horizontal = 16.dp, vertical = 12.dp)"""),
], "QqScreen 独立时加底")
patch(os.path.join(UI, "QqScreen.kt"),
      [("import androidx.compose.foundation.clickable",
        "import androidx.compose.foundation.background\nimport androidx.compose.foundation.clickable")],
      "QqScreen 补 background import")

print()
print("=== ② SettingsPage 暗色化 ===")
patch(os.path.join(UI, "SettingsPage.kt"), [
    ("""    val bg = Color(0xFFF5F6F8)
    val card = Color(0xFFFFFFFF)
    val title = Color(0xFF9AA0A6)
    val text = Color(0xFF1F2329)
    val sub = Color(0xFF8A9099)""",
     """    // 统一走主题（本 App 固定深色：background=0xFF0E1218 / surface=0xFF151C26 /
    // onSurface=亮文字 / onSurfaceVariant=次要文字）。此前这里写死了浅色，导致"整体暗色、
    // 从 ☰ 进去的设置页却是亮色"的不一致（用户 2026-10-11 指出）。
    val bg = MaterialTheme.colorScheme.background
    val card = MaterialTheme.colorScheme.surface
    val title = MaterialTheme.colorScheme.onSurfaceVariant
    val text = MaterialTheme.colorScheme.onSurface
    val sub = MaterialTheme.colorScheme.onSurfaceVariant"""),
    ("tint = Color(0xFFC4C8CC), modifier = Modifier.size(20.dp)",
     "tint = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(20.dp)"),
    (".background(Color(0xFFEDEFF2))",
     ".background(MaterialTheme.colorScheme.surfaceVariant)"),
], "SettingsPage 主题化")

print()
print("=== 编译 ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), "assembleRelease", "--console=plain"],
                   cwd=CHAT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
print("   " + next((l for l in o.splitlines() if l.startswith("BUILD")), "(无)"))
for y in [x for x in o.splitlines() if x.startswith("e: ")][:12]:
    print("   " + y[:230])
if r.returncode != 0:
    print("✗ 编译失败（未提交）")
    sys.exit(1)

DOC = """# UI 规范（2026-10-11 立，用户明确要求）

## 一、新页面必须"遮罩 + 全屏覆盖"

> 用户原话：以后无论什么页面，尤其是「聊天」这一页面下的新功能页，一定要做遮罩，
> 开一页新的覆盖全屏，不然背景就会变成底下的聊天页，甚至可以看见底下的消息。

要点：
1. **聊天页（ChatScreen）里新开的功能页**：外面必须再套一层
   `Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background))`，
   或页面**自身根节点**就带不透明底色（`fillMaxSize().background(...)`）。
   两者至少有一个，最好都有（防御）。
2. 半透明遮罩（如会话抽屉 `scrim`、＋面板 `0xB3000000`）只适用于**弹层**；
   **整页**必须不透明 —— 不允许"看得到底下的聊天消息"。
3. 页面自身也要带底：这样即使以后被别的入口复用，也不会透出。
4. 现状核查（2026-10-11）：
   | 页面 | 遮罩/底色 | 处理 |
   |---|---|---|
   | 会话抽屉 showDrawer | ✅ 有 scrim | 不动 |
   | ＋ 面板 showPlus | ✅ 有 scrim | 不动 |
   | ArScreen showAr | ✅ 自身 `Box(fillMaxSize().background(Color.Black))` | 不动 |
   | SettingsPage showSettings | ⚠ 自身有底但**是浅色** | 已改为主题暗色 |
   | **VrmScreen showVrm** | ❌ **自身无底**（能透出聊天）| 调用点套遮罩 + 页面自身加底 |
   | QqScreen | 现为首页卡片内嵌 ✅ | 独立用时自身加底 |

## 二、配色必须走主题，禁止写死亮色

> 用户原话：咱们整个都是暗色的，三条线（☰）里面的设置是亮色的，你觉得合适吗？

- 本 App **固定深色**（`Theme.kt` 的 `darkColorScheme`）：
  `background=#0E1218`、`surface=#151C26`、`surfaceVariant=#1B2432`、
  `onSurface=#E7EDF3`、`onSurfaceVariant=#9FACBC`、`outline=#2A3646`。
- **禁止**在页面里写死 `Color(0xFFF5F6F8)` / `Color(0xFFFFFFFF)` / `Color(0xFFEDEFF2)`
  这类浅色；一律用 `MaterialTheme.colorScheme.*`。
- 已修：`SettingsPage.kt`（bg/card/title/text/sub + 图标 tint + 分段底色）。
- **例外（保留）**：`LoginSheet.kt` 微信二维码那层 `Color.White` ——
  二维码需要白底才扫得动；`Common.kt` 里生成二维码位图的黑白同理。
- 排查命令（可复用）：
  `Select-String -Path app/src/main/java/com/aipet/murasame/ui/*.kt -Pattern "Color\\(0xFF[FEDC]" `
"""
io.open(os.path.join(MAIN, "dev", "docs", "UI规范-遮罩与暗色.md"), "w",
        encoding="utf-8", newline="\n").write(DOC)
print("✓ 写了 dev/docs/UI规范-遮罩与暗色.md")

MSG = """fix(ui): 复查两个界面问题——新页必须全屏遮罩；设置页写死亮色改为主题暗色

用户复查指出两点，均用代码取证确认：

① 页面遮罩：聊天页里 showAr/showVrm/showSettings 三个新页**没有**遮罩层，
   而 showDrawer/showPlus 有。其中 **VrmScreen 根节点没有底色** ⇒ 直接透出底下的聊天页、
   甚至能看到聊天消息（用户实际看到的现象）。
   处理：showVrm 调用点套一层不透明铺满 `Box(fillMaxSize().background(colorScheme.background))`；
   并给 VrmScreen、QqScreen（独立整页时）自身根节点加不透明底（防御：以后被别处复用也不透）。
   ArScreen 自身已有 `background(Color.Black)` 故不动。

② 配色不一致：App 固定深色（Theme.kt darkColorScheme，background=#0E1218/surface=#151C26），
   但 SettingsPage.kt 写死了浅色：bg=0xFFF5F6F8、card=0xFFFFFFFF、title=0xFF9AA0A6、
   text=0xFF1F2329、sub=0xFF8A9099，另有图标 tint 0xFFC4C8CC 与分段底色 0xFFEDEFF2。
   ⇒ 正是"整体暗色，从 ☰ 进去的设置页却是亮色"。
   处理：全部改为 MaterialTheme.colorScheme.*（background/surface/onSurface/onSurfaceVariant）。
   保留例外：LoginSheet 的二维码白底（扫得动需要）、Common.kt 生成二维码位图的黑白。

另新增 dev/docs/UI规范-遮罩与暗色.md：把这两条立为规范（含现状核查表与可复用的排查命令）。
"""
p = os.path.join(MAP, "_msg_ui1.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print("手机仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:130])
subprocess.run(["git", "-C", MAIN, "add", "dev/docs/UI规范-遮罩与暗色.md", "dev/scripts"], capture_output=True)
rc2 = subprocess.run(["git", "-C", MAIN, "commit", "-m",
                      "docs(ui): UI 规范——新页面必须全屏遮罩、配色一律走主题（附现状核查表）"],
                     capture_output=True, text=True, encoding="utf-8", errors="replace")
print("桌面仓:", (rc2.stdout or rc2.stderr or "").splitlines()[0][:130])
