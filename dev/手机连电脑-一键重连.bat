@echo off
chcp 65001 >nul
setlocal
set ADB=E:\Android\SDK\platform-tools\adb.exe
set DEV=4BD9K24C06021770

echo ============================================
echo  AIpet-Murasame  手机 <-> 电脑  一键重连
echo  (USB 反向端口转发：绕开校园网客户端隔离)
echo ============================================
echo.

if not exist "%ADB%" (
  echo [x] 找不到 adb：%ADB%
  pause
  exit /b 1
)

echo [1/4] 检查设备 ...
"%ADB%" -s %DEV% get-state
if errorlevel 1 (
  echo    指定序列号连不上，改试默认设备 ...
  "%ADB%" get-state
  if errorlevel 1 (
    echo.
    echo [x] 手机未连接。请确认：
    echo     - USB 线已插好
    echo     - 手机已开启「USB 调试」
    echo     - 手机上弹出的「允许 USB 调试」已点允许
    pause
    exit /b 1
  )
  set DEV=
) else (
  set "DEVP=-s %DEV%"
)
if not defined DEVP set DEVP=

echo [2/4] 清理旧的转发 ...
"%ADB%" %DEVP% reverse --remove-all >nul 2>&1

echo [3/4] 建立转发 28565(Jev) 与 9881(语音) ...
"%ADB%" %DEVP% reverse tcp:28565 tcp:28565
"%ADB%" %DEVP% reverse tcp:9881  tcp:9881

echo [4/4] 当前转发列表：
"%ADB%" %DEVP% reverse --list

echo.
echo 完成。手机端设置里请填：
echo    Jev 电脑地址   = http://127.0.0.1:28565
echo    语音服务地址   = http://127.0.0.1:9881
echo.
echo 提示：拔线或重启手机后需要重新运行本脚本。
echo.
pause
