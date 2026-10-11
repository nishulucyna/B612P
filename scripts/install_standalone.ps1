<#
 One-time setup of the standalone (laptop-free, offline) incident assistant on the HDK8650 over USB.
   powershell -ExecutionPolicy Bypass -File scripts\install_standalone.ps1
 Needs: adb, android_bridge\app\build\outputs\apk\debug\app-debug.apk (gradlew assembleDebug),
        npu_models\llm\model.gguf (Gemma), whisper_build\whisper_small_encoder_w8a16.dlc,
        whisper_build\whisper_decoder_small_fp16_htp.dlc, whisper_build\whisper_small_embed.bin,
        llm_prep\tts\sherpa-tts-lessac-medium.apk (offline Piper voice engine).
 After this the board needs no laptop and no network. Run it again after a reboot only for the `setenforce 0` line.
#>
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$adb = (Get-Command adb -ErrorAction SilentlyContinue).Source
if (-not $adb) { $adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" }
function Adb { & $adb @args }
function Need($p) { if (-not (Test-Path $p)) { throw "missing: $p" } ; $p }

$apk   = Need "$root\android_bridge\app\build\outputs\apk\debug\app-debug.apk"
$tts   = Need "$root\llm_prep\tts\sherpa-tts-lessac-medium.apk"
$gguf  = Need "$root\npu_models\llm\model.gguf"
$enc   = Need "$root\whisper_build\whisper_small_encoder_w8a16.dlc"
$dec   = Need "$root\whisper_build\whisper_decoder_small_fp16_htp.dlc"
$emb   = Need "$root\whisper_build\whisper_small_embed.bin"

Adb devices
Adb shell "mkdir -p /data/local/tmp/npu_models/llm /data/local/tmp/npu_models/whisper"
Write-Host "pushing models (about 6.5 GB, a few minutes) ..."
Adb push $gguf /data/local/tmp/npu_models/llm/model.gguf
Adb push $enc  /data/local/tmp/npu_models/whisper/
Adb push $dec  /data/local/tmp/npu_models/whisper/
Adb push $emb  /data/local/tmp/npu_models/whisper/
# Optional "Qwen - quick" button in the app: the all-Q4_0 Qwen3-1.7B file (see docs/demo_runbook.md). Without it the button shows "not installed".
$quick = "$root\llm_prep\qwen3_1p7b\qwen3-1.7b-pureq4_0.gguf"
if (Test-Path $quick) { Adb push $quick /data/local/tmp/npu_models/llm/ } else { Write-Host "(quick model not found, skipping: the Qwen button will say not installed)" }
Write-Host "installing apps ..."
Adb install -r $apk
Adb install -r $tts
Adb shell pm grant com.b612p.npubridge android.permission.RECORD_AUDIO
Adb shell settings put secure tts_default_synth com.k2fsa.sherpa.onnx.tts.engine
Adb shell setenforce 0          # the app reads models from /data/local/tmp; repeat after every board reboot
Adb shell am force-stop com.android.chrome   # a running Chrome starves the 5 GB model of memory
Adb shell am start -n com.b612p.npubridge/.MainActivity
Write-Host "Done. Unplug the laptop if you like: open 'Incident Assistant' on the phone, wait ~40 s for the green bar, tap Speak."
