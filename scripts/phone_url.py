"""Print the addresses to open the demo UI on a phone (with a QR code), and how to use the board's own screen.

    python scripts/phone_url.py [--port 8501] [--https]

A phone on the same Wi-Fi opens http(s)://<laptop address>:<port>. Browsers only allow microphone access on
HTTPS or on localhost, so for the phone's microphone use the HTTPS address (start_demo.ps1 -Https) or the USB
route (adb reverse, which makes the page "localhost" on the device).
"""

import argparse
import ipaddress
import os
import socket
import subprocess
import sys
from pathlib import Path


def lan_addresses() -> list[tuple[str, str]]:
    """(adapter, ipv4) for the laptop's non-loopback IPv4 addresses, best candidate first."""
    found: list[tuple[str, str]] = []
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and "
             "$_.IPAddress -notlike '169.254*' } | ForEach-Object { $_.InterfaceAlias + '|' + $_.IPAddress }"],
            capture_output=True, text=True, timeout=15,
        ).stdout
        for line in out.splitlines():
            if "|" in line:
                name, ip = line.strip().split("|", 1)
                found.append((name, ip))
    except Exception:  # noqa: BLE001 - fall back to the socket trick below
        pass
    if not found:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("10.255.255.255", 1))  # no packet is sent; just picks the outgoing interface
                found.append(("default", s.getsockname()[0]))
        except OSError:
            pass

    def rank(item: tuple[str, str]) -> int:
        name = item[0].lower()
        if "wi-fi" in name or "wifi" in name or "wlan" in name:
            return 0
        if "vethernet" in name or "virtual" in name or "vbox" in name or item[1].startswith("192.168.56."):
            return 3                       # virtual adapters (VirtualBox, WSL, Hyper-V): phones cannot reach these
        return 1

    return sorted(found, key=rank)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8501)
    ap.add_argument("--https", action="store_true")
    ap.add_argument("--open", action="store_true", help="open the QR code image in the default viewer")
    args = ap.parse_args()
    scheme = "https" if args.https else "http"

    addrs = [a for a in lan_addresses() if ipaddress.ip_address(a[1]).is_private]
    print("\nOpen the UI on a phone")
    print("----------------------")
    if not addrs:
        print("No network address found. Connect the laptop to Wi-Fi, or use the USB route below.")
    for i, (name, ip) in enumerate(addrs):
        url = f"{scheme}://{ip}:{args.port}"
        print(f"  {'*' if i == 0 else ' '} {url}    ({name})")
    if addrs:
        url = f"{scheme}://{addrs[0][1]}:{args.port}"
        try:
            import segno

            qr = segno.make(url, error="m")
            png = Path(__file__).resolve().parent.parent / "temp_audio" / "phone_qr.png"
            png.parent.mkdir(exist_ok=True)
            qr.save(str(png), scale=10, border=3)
            print(f"\nQR code for {url}\n  saved as {png}")
            try:  # terminal version, where the console can show block characters
                qr.terminal(compact=True)
            except UnicodeEncodeError:
                pass
            if args.open:
                os.startfile(str(png))  # Windows: opens the image so the phone can scan it from the screen
        except ImportError:
            print("\n(pip install segno to print a QR code here)")
        print("The phone must be on the same Wi-Fi as the laptop. Some guest/campus Wi-Fi blocks device-to-device traffic;"
              " if the page does not load, use the USB route.")
        if args.https:
            print("HTTPS uses a self-signed certificate: tap Advanced > Proceed once. Then the phone microphone works.")
        else:
            print("Plain http works for viewing and typing, but the browser will NOT allow the phone microphone.\n"
                  "For that, restart with: scripts\\start_demo.ps1 -Https (or use the USB route).")

    print("\nOn the board's own screen (or a phone plugged in with USB debugging)")
    print("-------------------------------------------------------------------")
    print(f"  adb reverse tcp:{args.port} tcp:{args.port}")
    print(f"  adb shell am start -a android.intent.action.VIEW -d {scheme}://localhost:{args.port}")
    print(f"  (or open {scheme}://localhost:{args.port} in Chrome there). 'localhost' counts as secure, so its microphone works.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
