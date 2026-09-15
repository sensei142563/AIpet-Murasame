$pidArg = [int]$args[0]
$code = @"
using System;
using System.IO;
using System.Text;
using System.Runtime.InteropServices;
public static class C {
  [DllImport("kernel32.dll")] public static extern bool AttachConsole(uint pid);
  [DllImport("kernel32.dll")] public static extern bool FreeConsole();
  [DllImport("kernel32.dll")] public static extern IntPtr GetStdHandle(int n);
  [DllImport("kernel32.dll")] public static extern bool ReadFile(IntPtr h, byte[] b, uint n, out uint r, IntPtr o);
}
"@
Add-Type -TypeDefinition $code
if (-not [C]::AttachConsole([uint32]$pidArg)) { Write-Output "ATTACH_FAIL"; exit 1 }
$h = [C]::GetStdHandle(-12)
$sb = New-Object System.Text.StringBuilder
$buf = New-Object byte[] 4096
$read = 0
$deadline = (Get-Date).AddSeconds(3)
$c1 = [Console]::ForegroundColor; $c2 = [Console]::BackgroundColor
[Console]::ForegroundColor = [ConsoleColor]::Black; [Console]::BackgroundColor = [ConsoleColor]::White
while ((Get-Date) -lt $deadline) {
  if ([C]::ReadFile($h, $buf, 4096, [ref]$read, [IntPtr]::Zero) -and $read -gt 0) {
    $s = [Text.Encoding]::UTF8.GetString($buf, 0, [int]$read)
    $sb.Append($s) | Out-Null
    $deadline = (Get-Date).AddSeconds(1.5)
  } else { Start-Sleep -Milliseconds 150 }
}
[Console]::ForegroundColor = $c1; [Console]::BackgroundColor = $c2
[C]::FreeConsole() | Out-Null
Write-Output "=====BRIDGE_CONSOLE_TAIL====="
Write-Output $sb.ToString()
