# Install the `matyos` command on Windows.
#
#   - Run after downloading matyos.exe (place it next to this script) OR after
#     building it (dist\matyos.exe).
#   - Copies the binary to %LOCALAPPDATA%\Programs\Matyos and adds that folder
#     to your user PATH, so `matyos` works in any new terminal.
#
# Usage:   powershell -ExecutionPolicy Bypass -File install.ps1

$ErrorActionPreference = "Stop"

$dest = Join-Path $env:LOCALAPPDATA "Programs\Matyos"

# Find the binary: prefer ./matyos.exe (downloaded), else ./dist/matyos.exe (built).
$candidates = @(
    (Join-Path $PSScriptRoot "matyos.exe"),
    (Join-Path $PSScriptRoot "dist\matyos.exe")
)
$src = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $src) {
    Write-Error "matyos.exe not found next to this script or in dist\. Download it from the Releases page first."
    exit 1
}

New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item $src (Join-Path $dest "matyos.exe") -Force
Write-Host "Installed matyos.exe to $dest"

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (-not $userPath) { $userPath = "" }
if ($userPath.Split(';') -notcontains $dest) {
    $newPath = if ($userPath) { "$userPath;$dest" } else { $dest }
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "Added $dest to your user PATH."
    Write-Host "Open a NEW terminal, then run:  matyos version"
} else {
    Write-Host "$dest is already on your PATH. Run:  matyos version"
}
