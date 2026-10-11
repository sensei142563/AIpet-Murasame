# -*- coding: utf-8 -*-
"""查清 accept_all.py 里 screenrecord 出现在哪；把自检从"朴素子串"改成"查是否真的调用"。"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
A = os.path.join(MAIN, "dev", "scripts", "accept_all.py")

lines = io.open(A, encoding="utf-8").read().split("\n")
print("=== screenrecord / kill -9 出现的所有位置（带上下文）===")
for i, l in enumerate(lines, 1):
    for k in ("screenrecord", "kill -9"):
        if k in l:
            stripped = l.strip()
            kind = "注释" if stripped.startswith("#") else "代码"
            print("   %4d| [%s] %s" % (i, kind, stripped[:120]))

print()
print("=== 把自检改成按语义判断 ===")
t = io.open(A, encoding="utf-8").read().replace("\r\n", "\n")
if "SELFTEST_SEMANTIC" not in t:
    # 在文件末尾前追加一个自检函数（供 --selftest-rules 使用），并改掉原来的朴素检查位置
    t = t.replace('''if __name__ == "__main__":''',
                  '''def selftest_rules():
    """SELFTEST_SEMANTIC：按**语义**检查本脚本是否违反截图技能的两条硬性规则。
    教训：不要用"文件里是否出现某个词"来判断 —— 注释、文档、README 文本都会命中。
    实测：`screenrecord` 只是出现在注释里，却被朴素子串检查报成"违规"。
    """
    src = io.open(os.path.abspath(__file__), encoding="utf-8").read()
    code_lines = [l for l in src.split("\\n") if not l.strip().startswith("#")]
    code = "\\n".join(code_lines)
    problems = []
    # ① 截图必须带 -p 且走 exec-out
    if "exec-out" not in code or 'screencap", "-p"' not in code:
        problems.append("截图调用缺少 exec-out 或 -p")
    # ② 不允许真的调用 screenrecord（注释里提到不算）
    if re.search(r"adb(_bytes)?\\([^)]*screenrecord", code):
        problems.append("真的调用了 screenrecord")
    # ③ 不允许 kill -9
    if re.search(r'"kill"\\s*,\\s*"-9"', code):
        problems.append("使用了 kill -9")
    # ④ 截图必须校验 PNG 魔数
    if b"PNG".decode() not in code or "\\\\x89PNG" not in code:
        problems.append("未校验 PNG 魔数")
    print("   [selftest-rules] " + ("全部符合截图技能要求 ✓" if not problems
                                    else "发现问题：" + "; ".join(problems)))
    # 自证：注入一段"只在注释里提 screenrecord"的文本，检查器应仍然通过
    fake = "# 这里提到 screenrecord 只是注释\\nadb('exec-out','screencap','-p')\\n"
    fake_code = "\\n".join(l for l in fake.split("\\n") if not l.strip().startswith("#"))
    ok_comment = not re.search(r"adb(_bytes)?\\([^)]*screenrecord", fake_code)
    print("   [selftest-rules] 注释里出现 screenrecord 时判为合规：%s（应为 True）" % ok_comment)
    return not problems and ok_comment


if __name__ == "__main__":''', 1)
    # 跑 selftest-rules 的分支
    t = t.replace('''    if "--selftest-diag" in sys.argv:''',
                  '''    if "--selftest-rules" in sys.argv:
        selftest_rules()
    if "--selftest-diag" in sys.argv:''', 1)
    io.open(A, "w", encoding="utf-8", newline="\n").write(t)
    print("✓ 已加 selftest_rules()（语义判断 + 自证）")

print()
print("=== 语法 + 跑 selftest-rules（含自证）===")
r = subprocess.run([sys.executable, "-c",
                    "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % A],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
print("   语法:", "OK" if r.returncode == 0 else "FAIL\n" + (r.stderr or "")[:400])
if r.returncode != 0:
    sys.exit(1)
r2 = subprocess.run([sys.executable, "-u", A, "--dry-run", "--selftest-rules"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=600, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
out = (r2.stdout or "") + (r2.stderr or "")
for l in out.split("\n"):
    if "selftest-rules" in l:
        print("   " + l.strip()[:150])
print("   EXIT:", r2.returncode)
