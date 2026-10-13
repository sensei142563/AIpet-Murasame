import importlib,sys
bad=[]
for n in sys.argv[1:]:
    try: importlib.import_module(n)
    except Exception as e: bad.append(n)
print('MISSING:' + ','.join(bad))
