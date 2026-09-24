@echo off
chcp 65001 >nul
rem ============================================
rem  系统时间同步修复（解决 QQ 发送"网络连接异常"1006514）
rem  原因：主板时钟漂移导致本地时间与腾讯服务器偏差数秒，
rem        QQ 发送消息带时间戳校验，偏差过大会被服务器拒绝。
rem  用法：右键本文件 → 以管理员身份运行
rem ============================================

echo 正在配置时间同步服务器（time.windows.com）...
sc config w32time start= auto >nul 2>&1
net start w32time >nul 2>&1

w32tm /config /manualpeerlist:"time.windows.com,0x1 time.nist.gov,0x1" /syncfromflags:manual /update
if errorlevel 1 (
    echo [失败] 配置时间源失败，请确认已用"管理员身份运行"。
    pause
    exit /b 1
)

echo 正在与网络时间服务器同步...
w32tm /resync
if errorlevel 1 (
    echo [失败] 同步失败（可能网络不通或未用管理员运行），
    echo        也可以打开 Windows 设置 → 时间和语言 → 开启"自动设置时间"。
    pause
    exit /b 1
)

echo.
echo 同步完成。当前时间：
w32tm /query /status | findstr /i "源 上次成功同步时间"
echo.
echo 提示：建议保持系统"自动设置时间"开启，防止再次漂移。
pause
