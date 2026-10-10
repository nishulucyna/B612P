# scripts/setup_hdk.ps1 - PowerShell twin of setup_hdk.sh for the Windows host.
# Run after EVERY device reboot (SELinux returns to enforcing, HTP falls back to CPU).
# Usage: .\scripts\setup_hdk.ps1 [-FirstRun]
param([switch]$FirstRun)

$ErrorActionPreference = "Stop"
$port = if ($env:NPU_BRIDGE_PORT) { $env:NPU_BRIDGE_PORT } else { "8080" }

if (-not (Get-Command adb -ErrorAction SilentlyContinue)) {
    throw "adb not found on PATH (install Android platform-tools)"
}

adb wait-for-device

if ($FirstRun) {
    adb root
    adb disable-verity
    adb reboot
    adb wait-for-device
}

adb root
adb wait-for-device
adb remount
adb shell setenforce 0
Write-Host ("SELinux: " + (adb shell getenforce))

adb forward "tcp:$port" "tcp:$port"
Write-Host "Forwarded host tcp:$port -> device tcp:$port"
