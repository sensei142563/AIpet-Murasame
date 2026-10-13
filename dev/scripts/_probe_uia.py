
import sys
print("exe =", sys.executable)
print("prefix =", sys.prefix)
for name in ("comtypes", "comtypes.client", "uiautomation", "win32com", "pilk", "pynput"):
    try:
        __import__(name)
        print("  %-18s 有" % name)
    except Exception as e:
        print("  %-18s 缺 (%s)" % (name, type(e).__name__))
try:
    from comtypes.gen import UIAutomationClient as UIA
    print("  UIAutomationClient 有")
except Exception as e:
    print("  UIAutomationClient 缺 (%s)" % type(e).__name__)
