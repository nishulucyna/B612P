"""Check the UI the way a phone sees it (needs the demo running; optional dependency: pip install playwright
and `playwright install chromium`).

    python scripts/ui_phone_check.py [--url http://localhost:8501] [--api http://127.0.0.1:8000] [--mic-wav clip.wav]

Opens the page in a Pixel 7 profile and checks: no horizontal scrolling, no sidebar covering the report, the voice
controls are on the page, and a typed turn works. With --mic-wav it also feeds that WAV to the browser as a fake
microphone and checks the "Use this device's microphone" path end to end (record -> upload -> board -> transcript).
It resets the incident session before and after. Exit code 0 only if everything passed.
"""

import argparse
import json
import re
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def api(base: str, path: str, method: str = "GET"):
    req = urllib.request.Request(base + path, method=method, data=b"" if method == "POST" else None)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8501")
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--mic-wav", default=None, help="16 kHz mono WAV to use as the phone microphone")
    args = ap.parse_args()

    api(args.api, "/api/reset", "POST")
    chrome_args = []
    if args.mic_wav:
        chrome_args = ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
                       f"--use-file-for-fake-audio-capture={args.mic_wav}"]
    with sync_playwright() as p:
        browser = p.chromium.launch(args=chrome_args)
        device = dict(p.devices["Pixel 7"])
        device["viewport"] = {"width": 412, "height": 2300}
        page = browser.new_context(**device, permissions=["microphone"], ignore_https_errors=True).new_page()
        page.goto(args.url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)

        print(f"Phone view of {args.url}")
        check("no horizontal scrolling", page.evaluate("document.documentElement.scrollWidth - window.innerWidth") <= 1)
        check("no sidebar covering the page", page.locator('[data-testid="stSidebar"]').count() == 0)
        check("Speak button on the page", page.get_by_role("button", name=re.compile("Speak")).count() == 1)
        check("Undo button on the page", page.get_by_role("button", name=re.compile("Undo")).count() >= 1)
        check("status chip says the NPU", page.get_by_text(re.compile("running on the Snapdragon NPU")).count() >= 1)

        page.get_by_text("Type instead").click()
        page.get_by_role("textbox").first.fill("A pipe burst on the second floor!")
        page.get_by_role("button", name=re.compile("Process Input")).click()
        try:
            page.wait_for_selector("text=Got that", timeout=120000)
            check("typed turn answered with a follow-up question", True)
        except Exception:  # noqa: BLE001
            check("typed turn answered with a follow-up question", False)

        if args.mic_wav:
            api(args.api, "/api/reset", "POST")
            page.reload(wait_until="networkidle")
            page.wait_for_timeout(2500)
            print("Phone microphone (fake device playing the WAV):")
            secure = page.evaluate("window.isSecureContext")
            check("page is a secure context (https or localhost)", bool(secure),
                  "" if secure else "use start_demo.ps1 -Https for the Wi-Fi address")
            if secure:
                page.get_by_text("Use this device's microphone").click()
                page.wait_for_timeout(1200)
                page.get_by_role("button", name=re.compile("record", re.I)).first.click()
                page.wait_for_timeout(8000)
                page.get_by_role("button", name=re.compile("stop", re.I)).first.click()
                deadline = time.time() + 150
                while time.time() < deadline and not api(args.api, "/api/transcript"):
                    page.wait_for_timeout(1500)
                lines = [m["text"] for m in api(args.api, "/api/transcript") if m["role"] == "user"]
                check("the board transcribed the recording", bool(lines), lines[0][:70] if lines else "nothing arrived")
        browser.close()

    api(args.api, "/api/reset", "POST")
    print("\n" + ("All checks passed." if not failures else f"{len(failures)} check(s) FAILED: {', '.join(failures)}"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
