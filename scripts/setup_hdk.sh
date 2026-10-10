#!/usr/bin/env bash
# scripts/setup_hdk.sh
# Prepares the Qualcomm HDK8650 (SM8650P, V75) so the NPU bridge works.
# Run after EVERY device reboot: SELinux goes back to enforcing and the HTP (DSP)
# runtime then silently falls back to CPU.
#
# Usage:
#   scripts/setup_hdk.sh              # normal per-boot setup
#   scripts/setup_hdk.sh --first-run  # also disable verity + reboot (once per device)
set -euo pipefail

PORT="${NPU_BRIDGE_PORT:-8080}"

command -v adb >/dev/null || { echo "adb not found on PATH (install Android platform-tools)"; exit 1; }

adb wait-for-device

if [[ "${1:-}" == "--first-run" ]]; then
  adb root
  adb disable-verity
  adb reboot
  adb wait-for-device
fi

adb root
adb wait-for-device
adb remount
adb shell setenforce 0
echo "SELinux: $(adb shell getenforce | tr -d '\r')"

adb forward "tcp:${PORT}" "tcp:${PORT}"
echo "Forwarded host tcp:${PORT} -> device tcp:${PORT}"
