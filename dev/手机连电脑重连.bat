@echo off
setlocal
chcp 936 >nul
title AIpet 手机 连 电脑 重连

set ADB=E:\Android\SDK\platform-tools\adb.exe
set DEV=4BD9K24C06021770

echo ============================================
echo  AIpet-Murasame  手机 连 电脑  重连
echo  USB 反向端口转发：绕开校园网客户端隔离
echo ============================================
echo.

if not exist "%ADB%" goto NOADB

echo [1/4] 检查设备 ...
"%ADB%" -s %DEV% get-state >nul 2>&1
if not errorlevel 1 goto HAVE_DEV
echo     用序列号 %DEV% 连不上，改试默认设备 ...
"%ADB%" get-state >nul 2>&1
if not errorlevel 1 goto HAVE_DEFAULT
echo.
echo [x] 手机未连接。请确认：
echo     1. USB 线插好
echo     2. 手机已开启 开发者选项 - USB 调试
echo     3. 手机上弹出的 允许 USB 调试 已点允许
goto ENDPAUSE

:HAVE_DEV
echo     设备在线: %DEV%
echo [2/4] 清理旧转发 ...
"%ADB%" -s %DEV% reverse --remove-all >nul 2>&1
echo [3/4] 建立转发 28565 Jev 与 9881 语音 ...
"%ADB%" -s %DEV% reverse tcp:28565 tcp:28565
"%ADB%" -s %DEV% reverse tcp:9881 tcp:9881
echo [4/4] 当前转发列表：
"%ADB%" -s %DEV% reverse --list
goto DONE

:HAVE_DEFAULT
echo     设备在线: 默认设备
echo [2/4] 清理旧转发 ...
"%ADB%" reverse --remove-all >nul 2>&1
echo [3/4] 建立转发 28565 Jev 与 9881 语音 ...
"%ADB%" reverse tcp:28565 tcp:28565
"%ADB%" reverse tcp:9881 tcp:9881
echo [4/4] 当前转发列表：
"%ADB%" reverse --list
goto DONE

:NOADB
echo [x] 找不到 adb: %ADB%
goto ENDPAUSE

:DONE
echo.
echo 完成。手机端 设置 里填：
echo    Jev 电脑地址   = http://127.0.0.1:28565
echo    语音服务地址   = http://127.0.0.1:9881
echo.
echo 提示：拔线、重启手机、重启电脑后都要重新运行本脚本。
echo.

:ENDPAUSE
pause
