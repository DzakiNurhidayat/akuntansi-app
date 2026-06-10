$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$batFile = Join-Path $projectDir "run.bat"
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "Akuntansi.lnk"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $batFile
$shortcut.WorkingDirectory = $projectDir
$shortcut.IconLocation = "shell32.dll,21"
$shortcut.Description = "Jalankan Cleaning Service Accounting App"
$shortcut.Save()

Write-Host "Shortcut berhasil dibuat di Desktop: $shortcutPath"
