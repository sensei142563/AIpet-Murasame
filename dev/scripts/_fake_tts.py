# -*- coding: utf-8 -*-
import io, os, sys, time
def out(s):
    sys.stdout.write(s + "\n"); sys.stdout.flush()
out("INFO:     未指定默认参考音频")
out("INFO:     半精: True")
out("INFO:     编码格式: wav")
time.sleep(0.3)
out('INFO:     127.0.0.1:51234 - "POST /tts HTTP/1.1" 200 OK')
time.sleep(0.3)
p = os.path.join("data", "tts_say.log")
with io.open(p, "a", encoding="utf-8") as f:
    f.write("%.3f\t今天有点累呢，主人\n" % time.time())
time.sleep(0.8)
out("INFO:     Application startup complete.")
out("INFO:     Uvicorn running on http://0.0.0.0:9880 (Press CTRL+C to quit)")
time.sleep(0.5)
out('INFO:     127.0.0.1:51235 - "POST /tts HTTP/1.1" 200 OK')
with io.open(p, "a", encoding="utf-8") as f:
    f.write("%.3f\t那要不要先休息一会儿？\n" % time.time())
time.sleep(0.5)
out("ERROR:    测试用的报错行")
time.sleep(0.5)
