docs(readme): 更正「桌宠本体三件套」的角色说明 —— 三个标签原来全错位

README 原第 1430 行：
    | `api.py` / `main.py` / `run.py` | 桌宠本体：启动器 / FastAPI 后端 / 主窗口 |
按顺序对应就是：api.py=启动器、main.py=FastAPI 后端、run.py=主窗口 —— **三个全错**。

实测（逐个文件抓特征）：
    api.py   → FastAPI/uvicorn（后端接口），840 行
    main.py  → FastAPI + PyQt 图形界面 + Qt 控件 + 拉起子进程，1451 行 ⇒ **主窗口本体**
    run.py   → 拉起子进程 + 环境安装/引导，1257 行 ⇒ **启动器**

改为按**启动顺序**写清：
    `run.py` = 启动器（引导环境、拉起各服务与主窗口）
    `main.py` = 主窗口（PyQt 界面 + 本地 FastAPI 接口）
    `api.py` = 独立的 FastAPI 后端接口

## 说明
这是今天**第三次**遇到"标签对错了对象"（前两次：测试里断言按「视觉来源」而界面用「识别来源」；
`data/tts_model.json` 里 gpt/sovits 互换）。三次都不是崩溃型 bug，
但都会让人（和脚本）**看错东西**，而且都能一路不被发现。
分不清"我改的这个标签对的是哪一项"，是这类问题的共同点。
