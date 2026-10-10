# scripts/start_demo.ps1 - one command to get the live demo running.
#
#   powershell -ExecutionPolicy Bypass -File scripts\start_demo.ps1
#
# 1. checks Python packages and finds adb
# 2. prepares the HDK8650 (root, SELinux permissive, model folder readable, port forward)
# 3. (re)starts the bridge app on the board and waits until Whisper and the LLM are loaded
# 4. starts the orchestrator (port 8000) and the Streamlit UI (port 8501), opens the browser
#
# Strict by default: the orchestrator uses ONLY the board (NPU_BACKEND=device). If the board
# fails, requests fail loudly instead of quietly using the laptop mock. Use -AllowMock to let it
# fall back to the mock (the UI then shows an orange MOCK banner).
param(
    [switch]$AllowMock,
    [switch]$NoBrowser,
    [switch]$ReinstallApk,
    [switch]$Https,         # serve the UI over HTTPS (self-signed) so a phone on the Wi-Fi may use its own microphone
    [switch]$OpenOnBoard,   # EXPERIMENTAL: open the UI in Chrome on the board itself (see the warning below)
    [int]$ApiPort = 8000,
    [int]$UiPort = 8501
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Step($m) { Write-Host ""; Write-Host "== $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "  OK  $m" -ForegroundColor Green }
function Fail($m) { Write-Host ""; Write-Host "FAILED: $m" -ForegroundColor Red; exit 1 }

# ---- tools ------------------------------------------------------------------
Step "Looking for tools"
$adb = $null
$cmd = Get-Command adb -ErrorAction SilentlyContinue
if ($cmd) { $adb = $cmd.Source }
if (-not $adb) {
    $candidate = Join-Path $env:LOCALAPPDATA "Android\Sdk\platform-tools\adb.exe"
    if (Test-Path $candidate) { $adb = $candidate }
}
if (-not $adb) { Fail "adb not found. Install Android platform-tools or add it to PATH." }
Ok "adb: $adb"

$pycmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pycmd) { Fail "python not found on PATH." }
$py = $pycmd.Source
Ok "python: $py"

$missing = (& $py scripts\check_deps.py) -join ""
if ("$missing".Trim()) { Fail "Missing Python packages: $missing  ->  pip install -r requirements.txt -r frontend/requirements.txt" }
Ok "Python packages present"

# ---- board --------------------------------------------------------------------
Step "Connecting to the board"
& $adb start-server 2>$null | Out-Null
$connected = (& $adb devices) | Select-String "\tdevice$"
if (-not $connected) {
    Fail ("No board visible to adb. Check: 12 V adapter on and the board powered (power button), USB-C DATA cable " +
          "straight into the laptop, S5801-1 (Force USB Boot) OFF, USB debugging enabled. Then run 'adb devices'.")
}
Ok ("board: " + (($connected | Select-Object -First 1).ToString().Split("`t")[0]))

& $adb root 2>&1 | Out-Null
Start-Sleep -Seconds 2
& $adb wait-for-device
& $adb shell setenforce 0
$se = (& $adb shell getenforce).Trim()
if ($se -ne "Permissive") { Fail "SELinux is '$se' (needs Permissive or the NPU is not usable). Is the board rooted (adb root)?" }
Ok "SELinux: $se"
& $adb shell "chmod -R a+rX /data/local/tmp/npu_models" | Out-Null

$model = (& $adb shell "ls /data/local/tmp/npu_models/llm/model.gguf 2>&1") -join ""
if ($model -match "No such file") {
    Fail "No LLM on the board. Push one:  adb push npu_models\llm\model.gguf /data/local/tmp/npu_models/llm/model.gguf"
}
Ok "LLM file present on the board"

& $adb forward tcp:8080 tcp:8080 | Out-Null
Ok "port forward 8080 -> board"

# ---- app on the board ----------------------------------------------------------
Step "Bridge app on the board"
$installed = (& $adb shell pm list packages com.b612p.npubridge) -join ""
$apk = Join-Path $root "android_bridge\app\build\outputs\apk\debug\app-debug.apk"
if ($ReinstallApk -or -not $installed) {
    if (-not (Test-Path $apk)) {
        Fail "App not installed and no APK built. Build it:  cd android_bridge; .\gradlew.bat assembleDebug"
    }
    Write-Host "  installing APK..."
    & $adb install -r -t $apk | Out-Null
}
Ok "app installed"
& $adb shell am force-stop com.b612p.npubridge
& $adb shell am start -n com.b612p.npubridge/.MainActivity | Out-Null
Write-Host "  loading Whisper (DSP) and the LLM (NPU) - the LLM takes about 10-30 s..."
& $py scripts\wait_for_board.py --timeout 300
if ($LASTEXITCODE -ne 0) { Fail "The board did not become ready (see above). Check the app's banner on the board's screen." }
Ok "board ready"

# ---- orchestrator + UI ----------------------------------------------------------
function PortBusy($p) { return [bool](Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue) }
if (PortBusy $ApiPort) { Fail "Port $ApiPort is already in use. Run scripts\stop_demo.ps1 first." }
if (PortBusy $UiPort)  { Fail "Port $UiPort is already in use. Run scripts\stop_demo.ps1 first." }

Step "Starting the orchestrator and the UI"
$env:NPU_BACKEND   = $(if ($AllowMock) { "auto" } else { "device" })
$env:CONTRACT_PATH = Join-Path $root "runtime_state.json"
$env:TTS_ENABLED   = "1"
$env:INCIDENT_API  = "http://127.0.0.1:$ApiPort"
$env:API_PORT      = "$ApiPort"

Start-Process -FilePath $py -WorkingDirectory $root -WindowStyle Minimized `
    -ArgumentList @("scripts\run_orchestrator.py", "--port", "$ApiPort")
$up = $false
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Seconds 1
    try { Invoke-RestMethod "http://127.0.0.1:$ApiPort/api/health" -TimeoutSec 2 | Out-Null; $up = $true; break } catch { }
}
if (-not $up) { Fail "The orchestrator did not start on port $ApiPort." }
Ok "orchestrator: http://127.0.0.1:$ApiPort  (NPU_BACKEND=$($env:NPU_BACKEND))"

$scheme = $(if ($Https) { "https" } else { "http" })
$uiArgs = @("-m", "streamlit", "run", "frontend/app.py", "--server.headless", "true",
            "--server.address", "0.0.0.0", "--server.port", "$UiPort", "--browser.gatherUsageStats", "false")
if ($Https) {
    & $py scripts\make_cert.py
    if ($LASTEXITCODE -ne 0) { Fail "Could not create the HTTPS certificate (pip install cryptography)." }
    $uiArgs += @("--server.sslCertFile", "certs\lan.pem", "--server.sslKeyFile", "certs\lan.key")
}
Start-Process -FilePath $py -WorkingDirectory $root -WindowStyle Minimized -ArgumentList $uiArgs
$up = $false
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Seconds 1
    if (PortBusy $UiPort) { $up = $true; break }
}
if (-not $up) { Fail "The UI did not start on port $UiPort." }
Ok "UI: ${scheme}://localhost:$UiPort  (listening on all network interfaces)"

# The board / a USB-connected phone reaches the UI as 'localhost' over the USB cable (works without Wi-Fi, and
# 'localhost' is a secure origin, so the device microphone is allowed).
& $adb reverse "tcp:$UiPort" "tcp:$UiPort" | Out-Null
Ok "USB route: on the board, ${scheme}://localhost:$UiPort"
if ($OpenOnBoard) {
    Write-Host "  WARNING: a browser on the board competes with the 5 GB LLM for memory. In testing it left the board with" -ForegroundColor Yellow
    Write-Host "           ~300 MB free and the bridge stopped answering. Use it only with the small Qwen model, and close" -ForegroundColor Yellow
    Write-Host "           Chrome on the board (adb shell am force-stop com.android.chrome) if requests start failing." -ForegroundColor Yellow
    & $adb shell am start -a android.intent.action.VIEW -d "${scheme}://localhost:$UiPort" | Out-Null
    Write-Host "  opened Chrome on the board (open the bridge app again afterwards to see its status banner)"
}
if (-not $NoBrowser) { Start-Process "${scheme}://localhost:$UiPort" }

$phoneArgs = @("scripts\phone_url.py", "--port", "$UiPort")
if ($Https) { $phoneArgs += "--https" }
if (-not $NoBrowser) { $phoneArgs += "--open" }
& $py @phoneArgs

Write-Host ""
Write-Host "Demo is up." -ForegroundColor Green
Write-Host "  - Keep the board's screen on and the app in the foreground (green banner = on the NPU)."
Write-Host "  - Check everything:  python scripts\demo_selftest.py"
Write-Host "  - Try your voice:    python scripts\mic_check.py"
Write-Host "  - Stop:              powershell -File scripts\stop_demo.ps1"
Write-Host "  - After any board reboot, run this script again."
