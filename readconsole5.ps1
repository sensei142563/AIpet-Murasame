$pidArg = [int]$args[0]
$code = @"
using System;
using System.Runtime.InteropServices;
public static class C3 {
  [DllImport("kernel32.dll")] public static extern bool AttachConsole(uint pid);
  [DllImport("kernel32.dll")] public static extern bool FreeConsole();
  [DllImport("kernel32.dll")] public static extern IntPtr GetStdHandle(int n);
  [DllImport("kernel32.dll")] public static extern bool ReadFile(IntPtr h, byte[] b, uint n, out uint r, IntPtr o);
}
"@
Add-Type -TypeDefinition $code
[C3]::FreeConsole() | Out-Null
Start-Sleep -Milliseconds 300
if (-not [C3]::AttachConsole([uint32]$pidArg)) { Write-Output "ATTACH_FAIL"; exit 1 }
$h = [C3]::GetStdHandle(-12)
$sb = New-Object System.Text.StringBuilder
$buf = New-Object byte[] 8192
$read = 0
$deadline = (Get-Date).AddSeconds(4)
while ((Get-Date) -lt $deadline) {
  if ([C3]::ReadFile($h, $buf, 8192, [ref]$read, [IntPtr]::Zero) -and $read -gt 0) {
    $sb.Append([Text.Encoding]::UTF8.GetString($buf, 0, [int]$read)) | Out-Null
    $deadline = (Get-Date).AddSeconds(2)
  } else { Start-Sleep -Milliseconds 200 }
}
[C3]::FreeConsole() | Out-Null
Write-Output $sb.ToString()
