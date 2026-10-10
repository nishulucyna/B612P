@echo off
REM scripts\setup_hdk.bat - cmd twin of setup_hdk.sh. Run after EVERY device reboot.
REM Usage: scripts\setup_hdk.bat [--first-run]
setlocal
if "%NPU_BRIDGE_PORT%"=="" (set PORT=8080) else (set PORT=%NPU_BRIDGE_PORT%)

where adb >nul 2>nul || (echo adb not found on PATH & exit /b 1)

adb wait-for-device
if "%1"=="--first-run" (
  adb root
  adb disable-verity
  adb reboot
  adb wait-for-device
)
adb root
adb wait-for-device
adb remount
adb shell setenforce 0
adb shell "chmod -R a+rX /data/local/tmp/npu_models 2>/dev/null || true"
adb shell getenforce
adb forward tcp:%PORT% tcp:%PORT%
echo Forwarded host tcp:%PORT% -^> device tcp:%PORT%
