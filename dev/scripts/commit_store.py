# -*- coding: utf-8 -*-
"""全量回归 + release + 提交（手机仓 & 桌面仓）。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PET = r"E:\university\order\python\pet"
CHAT = os.path.join(PET, "chatter")
MAP = os.path.join(MAIN, "dev", "merge-map")
ENV = dict(os.environ)
ENV["JAVA_HOME"] = r"E:\Android Studio\jbr"
ENV["PATH"] = r"E:\Android Studio\jbr\bin;" + ENV.get("PATH", "")

print("=== 全量单测 + release ===")
r = subprocess.run([os.path.join(CHAT, "gradlew.bat"), ":app:testDebugUnitTest", "assembleRelease",
                    "--console=plain"], cwd=CHAT, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", env=ENV, timeout=7200)
o = (r.stdout or "") + (r.stderr or "")
for l in o.splitlines():
    if l.strip().startswith("BUILD") or l.startswith("e: ") or "FAILED" in l:
        print("   " + l.strip()[:200])
d = os.path.join(CHAT, "app/build/test-results/testDebugUnitTest")
tot = fail = 0
for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
    if f.endswith(".xml"):
        x = io.open(os.path.join(d, f), encoding="utf-8", errors="replace").read()
        m = re.search(r'tests="(\d+)" skipped="\d+" failures="(\d+)" errors="(\d+)"', x)
        if m:
            tt = int(m.group(1)); fl = int(m.group(2)) + int(m.group(3))
            tot += tt; fail += fl
            print("   %-24s tests=%-3d 失败=%d" % (f.replace("TEST-com.aipet.murasame.", "").replace(".xml", ""), tt, fl))
print("   合计 %d 用例，失败 %d；退出码 %d" % (tot, fail, r.returncode))
if r.returncode != 0 or fail:
    sys.exit(1)

MSG = """fix(store): 资产种子改原子复制 + 长度校验；列表不再出现"空壳角色"（7 个单测）

对抗审查 Store.kt（宠物包/资源安装层），读代码得到两个结论：

一、**我原本假设的问题不存在**（如实记录）：copyAssetDir 已经有"目录级"自愈 ——
    每次启动递归，缺失文件会补齐，注释里就写着"补齐缺失文件（修复历史半截种子）"。

二、但**文件级**没有，这才是真问题：
    `if (childDst.exists()) continue` ⇒ 一个被复制到一半就被杀的文件**永远存在**、
    永远被跳过 ⇒ 该资源**永久截断**。用户看到的是"角色装好了，但某个文件坏了"，
    而且重启也好不了 —— 正是我们要避免的"看起来装好了、其实缺一半"。

修法：
  ① 复制改为**原子**：先写 `<name>.part` 再改名，正式文件名下永远不会出现半截内容；
  ② 增加**长度校验**：能拿到资产长度（openFd）时，长度不符即重拷（含历史遗留的截断文件）；
     拿不到长度（压缩资产）时沿用"存在即跳过"，避免每次启动重拷；
  ③ 启动时清理遗留的 `.part`（兜底）；
  ④ listPets：注册表有条目但磁盘上目录/pet.json 不存在的，**跳过并记日志** ——
     否则会产出一个"名字回退成 id、头像为空"的空壳角色混进列表，让人一头雾水。

新增 AssetSeed.kt（纯逻辑，可 JVM 单测）：needsCopy(dstExists, dstLen, assetLen)、
partOf()、cleanupParts()。
单测 AssetSeedTest（7 个）：缺失要拷；拿不到长度时保留；**半截文件必须重拷**（40/100、0/100）；
长度一致保留；长度偏大也重拷；.part 路径为同目录同名前缀；cleanupParts 只删 .part
（正式文件与目录必须保留）。

验证：AssetSeedTest 7/7；全量单测 116 个用例失败 0；release 构建通过。
诚实标注：压缩资产取不到长度这一分支无法在 JVM 单测里覆盖（属 Android AssetManager 行为），
但其行为已在代码与测试注释中写明；真机上首次启动的种子流程未验。
"""
p = os.path.join(MAP, "_msg_store.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", CHAT, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", CHAT, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("手机仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:140])
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
r2 = subprocess.run(["git", "-C", MAIN, "commit", "-m",
                     "chore(scripts): Store 资产种子加固脚本"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
print("桌面仓:", (r2.stdout or r2.stderr or "").splitlines()[0][:140])
for nm, repo in (("手机", CHAT), ("桌面", MAIN)):
    n = subprocess.run(["git", "-C", repo, "rev-list", "--count", "origin/main..HEAD"],
                       capture_output=True, text=True, encoding="utf-8").stdout.strip()
    st = subprocess.run(["git", "-C", repo, "status", "--porcelain"], capture_output=True,
                        text=True, encoding="utf-8").stdout.strip()
    print("  %s仓：未推送 %s 条，工作区 %s" % (nm, n, "干净 ✓" if not st else "%d 项" % len(st.splitlines())))
