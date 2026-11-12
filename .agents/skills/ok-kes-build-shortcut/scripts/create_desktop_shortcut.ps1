param(
    [Parameter(Mandatory = $true)]
    [string]$ExePath
)

$ErrorActionPreference = "Stop"

$exe = Resolve-Path -LiteralPath $ExePath
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "ok-kes.lnk"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $exe.Path
$shortcut.WorkingDirectory = Split-Path -Parent $exe.Path
$shortcut.IconLocation = "$($exe.Path),0"
$shortcut.Description = "ok-kes"
$shortcut.Save()

Write-Output $shortcutPath
Write-Output $exe.Path
