# scripts/copy_whisper_assets.ps1
# Copies everything the Whisper path of android_bridge/ needs from the (gitignored) local folders:
#   npu_models/whisper/*            -> android_bridge/app/src/main/assets/
#   SNPE libs (V75) from the SDK    -> android_bridge/app/src/main/jniLibs/arm64-v8a/
#   SNPE C++ headers from the SDK   -> android_bridge/app/src/main/cpp/inc/zdl/
# Run from anywhere:  .\scripts\copy_whisper_assets.ps1 [-SdkVersion 2.47.0.260601]
param([string]$SdkVersion = "2.47.0.260601")

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.IO.Compression.FileSystem

$root   = Split-Path -Parent $PSScriptRoot
$sdk    = Join-Path $root "qairt_sdk\$SdkVersion"
$models = Join-Path $root "npu_models\whisper"
$main   = Join-Path $root "android_bridge\app\src\main"

$assets = @("whisper_tiny_encoder_w8a16.dlc", "whisper-decoder-tiny.tflite", "filters_vocab_gen.bin")
# Same set the qidk sample ships for V75 (taken from the SDK's snpe-release.aar, like its resolveDependencies.sh)
$jni    = @("libSNPE.so", "libSnpeHtpPrepare.so", "libSnpeHtpV75Stub.so", "libSnpeHtpV75CalculatorStub.so", "libSnpeHtpV75Skel.so")

foreach ($f in $assets) {
    if (-not (Test-Path (Join-Path $models $f))) { throw "Missing $f in $models" }
}
$aar = Join-Path $sdk "lib\android\snpe-release.aar"
if (-not (Test-Path $aar))                      { throw "Missing $aar (extract the QAIRT SDK to qairt_sdk\$SdkVersion)" }
if (-not (Test-Path (Join-Path $sdk "include\SNPE"))) { throw "Missing SNPE headers in $sdk\include\SNPE" }

# 1. model assets (memory-mapped from the APK, so they ship uncompressed; see app/build.gradle)
$assetDir = Join-Path $main "assets"
New-Item -ItemType Directory -Force $assetDir | Out-Null
foreach ($f in $assets) { Copy-Item (Join-Path $models $f) $assetDir -Force }

# 2. native libraries out of the AAR
$jniDir = Join-Path $main "jniLibs\arm64-v8a"
New-Item -ItemType Directory -Force $jniDir | Out-Null
$zip = [System.IO.Compression.ZipFile]::OpenRead($aar)
try {
    foreach ($lib in $jni) {
        $entry = $zip.GetEntry("jni/arm64-v8a/$lib")
        if (-not $entry) { throw "$lib not found in $aar" }
        [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, (Join-Path $jniDir $lib), $true)
    }
} finally { $zip.Dispose() }

# 3. SNPE headers for the native build
$hdrDir = Join-Path $main "cpp\inc\zdl"
New-Item -ItemType Directory -Force $hdrDir | Out-Null
Copy-Item (Join-Path $sdk "include\SNPE\*") $hdrDir -Recurse -Force

Write-Host "Assets    -> $assetDir"
Get-ChildItem $assetDir | Select-Object Name, @{n="MB";e={[math]::Round($_.Length/1MB,1)}} | Format-Table -AutoSize
Write-Host "Libraries -> $jniDir"
Get-ChildItem $jniDir | Select-Object Name, @{n="MB";e={[math]::Round($_.Length/1MB,2)}} | Format-Table -AutoSize
Write-Host "Headers   -> $hdrDir"
Write-Host "Done. Open android_bridge/ in Android Studio and build."
