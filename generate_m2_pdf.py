"""Builds deliverables/M2.pdf (Milestone 2, mid-submission, two pages). Run: python generate_m2_pdf.py"""

import os

from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

os.makedirs("deliverables", exist_ok=True)
PDF = "deliverables/M2.pdf"

doc = SimpleDocTemplate(PDF, pagesize=letter, leftMargin=34, rightMargin=34, topMargin=30, bottomMargin=28,
                        title="B612 - Megathon X Qualcomm Track - Milestone 2", author="Team B612")
W = letter[0] - 68

primary = colors.HexColor("#0f3460")
accent = colors.HexColor("#e94560")
grey = colors.HexColor("#4a4a5a")
band = colors.HexColor("#eef2f8")
styles = getSampleStyleSheet()

title = ParagraphStyle("t", parent=styles["Heading1"], fontSize=16, leading=19, textColor=primary,
                       fontName="Helvetica-Bold", spaceAfter=1)
sub = ParagraphStyle("s", parent=styles["Normal"], fontSize=8.4, leading=10.5, textColor=grey, spaceAfter=3)
h = ParagraphStyle("h", parent=styles["Heading2"], fontSize=11.2, leading=13.5, textColor=primary,
                   fontName="Helvetica-Bold", spaceBefore=4, spaceAfter=2)
body = ParagraphStyle("b", parent=styles["Normal"], fontSize=8.9, leading=11.2, textColor=colors.HexColor("#1a1a24"),
                      spaceAfter=2)
bul = ParagraphStyle("bl", parent=body, leftIndent=9, bulletIndent=0, spaceAfter=1)
cell = ParagraphStyle("c", parent=body, fontSize=7.9, leading=9.5, spaceAfter=0)
cellb = ParagraphStyle("cb", parent=cell, fontName="Helvetica-Bold")
hdr = ParagraphStyle("hd", parent=cell, fontName="Helvetica-Bold", textColor=colors.white)


def P(t, s=body):
    return Paragraph(t, s)


def B(t):
    return Paragraph(t, bul, bulletText="•")


def table(rows, widths, header=True, bold_first=True):
    data = []
    for i, r in enumerate(rows):
        data.append([Paragraph(str(c), hdr if (header and i == 0) else (cellb if (bold_first and j == 0) else cell))
                     for j, c in enumerate(r)])
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    st = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#c5cde0")),
          ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
          ("TOPPADDING", (0, 0), (-1, -1), 1.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6)]
    if header:
        st += [("BACKGROUND", (0, 0), (-1, 0), primary)]
    st += [("BACKGROUND", (0, k), (-1, k), band) for k in range(2 if header else 1, len(rows), 2)]
    t.setStyle(TableStyle(st))
    return t


def wer_chart():
    snr = [30, 25, 20, 15, 10, 7, 4]
    series = {"tiny (on the board)": [0, 0, 6, 11, 17, 22, 39], "base": [0, 0, 0, 6, 11, 17, 56],
              "small": [0, 0, 0, 0, 0, 0, 17]}
    d = Drawing(230, 104)
    lp = LinePlot()
    lp.x, lp.y, lp.width, lp.height = 28, 22, 190, 62
    lp.data = [[(s, v) for s, v in zip(snr, vals)] for vals in series.values()]
    for i, c in enumerate([accent, primary, colors.HexColor("#2a9d8f")]):
        lp.lines[i].strokeColor = c
        lp.lines[i].strokeWidth = 1.4
        lp.lines[i].symbol = None
    lp.xValueAxis.valueMin, lp.xValueAxis.valueMax = 4, 30
    lp.xValueAxis.valueSteps = [4, 7, 10, 15, 20, 25, 30]
    lp.xValueAxis.labels.fontSize = 6
    lp.yValueAxis.valueMin, lp.yValueAxis.valueMax = 0, 60
    lp.yValueAxis.valueSteps = [0, 20, 40, 60]
    lp.yValueAxis.labels.fontSize = 6
    d.add(lp)
    d.add(String(122, 95, "Word error rate (%) vs speech-to-noise (dB)", fontSize=6.6, textAnchor="middle",
                 fillColor=grey))
    d.add(String(123, 4, "signal over room noise (dB) - higher is cleaner", fontSize=6, textAnchor="middle",
                 fillColor=grey))
    lg = Legend()
    lg.x, lg.y, lg.fontSize, lg.dx, lg.dy, lg.deltay = 120, 84, 6, 6, 5, 7
    lg.colorNamePairs = [(c, n) for c, n in zip([accent, primary, colors.HexColor("#2a9d8f")], series)]
    lg.alignment = "right"
    d.add(lg)
    return d



def architecture():
    from reportlab.graphics.shapes import Line, Rect

    d = Drawing(W, 106)

    def box(x, y, w, h, title_, lines, fill):
        d.add(Rect(x, y, w, h, rx=3, ry=3, fillColor=fill, strokeColor=primary, strokeWidth=0.7))
        d.add(String(x + w / 2, y + h - 9, title_, fontSize=7, fontName="Helvetica-Bold", textAnchor="middle",
                     fillColor=primary))
        for i, t in enumerate(lines):
            d.add(String(x + w / 2, y + h - 18 - 7.5 * i, t, fontSize=6.1, textAnchor="middle", fillColor=grey))

    def arrow(x1, y1, x2, y2):
        d.add(Line(x1, y1, x2, y2, strokeColor=accent, strokeWidth=1))
        if abs(x2 - x1) >= abs(y2 - y1):
            sx = -3 if x2 > x1 else 3
            d.add(Line(x2, y2, x2 + sx, y2 + 2, strokeColor=accent, strokeWidth=1))
            d.add(Line(x2, y2, x2 + sx, y2 - 2, strokeColor=accent, strokeWidth=1))
        else:
            sy = -3 if y2 > y1 else 3
            d.add(Line(x2, y2, x2 + 2, y2 + sy, strokeColor=accent, strokeWidth=1))
            d.add(Line(x2, y2, x2 - 2, y2 + sy, strokeColor=accent, strokeWidth=1))

    d.add(Rect(0, 0, 292, 106, fillColor=None, strokeColor=colors.HexColor("#9aa7c7"), strokeDashArray=[3, 2]))
    d.add(String(6, 96, "LAPTOP (no AI inference)", fontSize=6.5, fontName="Helvetica-Bold", fillColor=grey))
    d.add(Rect(306, 0, W - 306, 106, fillColor=None, strokeColor=accent, strokeDashArray=[3, 2]))
    d.add(String(312, 96, "HDK8650 board: all models run here (DSP / NPU)", fontSize=6.5, fontName="Helvetica-Bold",
                 fillColor=accent))
    lt = colors.HexColor("#f4f6fb")
    rose = colors.HexColor("#fdecef")
    box(8, 50, 84, 36, "Microphone", ["raw capture,", "noise tracking,", "SNR estimate"], lt)
    box(104, 50, 100, 36, "Orchestrator", ["FastAPI + agent_brain", "Diamond Gate,", "tool call, undo"], lt)
    box(104, 6, 100, 34, "Offline TTS", ["Windows voices", "speaks the reply"], lt)
    box(214, 6, 72, 34, "Streamlit UI", ["form, chat,", "NPU status chip"], lt)
    arrow(92, 68, 104, 68)
    arrow(154, 50, 154, 40)
    arrow(190, 50, 236, 40)
    box(318, 50, W - 326, 36, "Bridge app (Android)", ["loopback HTTP :8080, reached via adb forward",
                                                        "status banner, NPU placement check"], lt)
    box(318, 6, 120, 34, "Whisper (STT)", ["encoder w8a16 DLC on DSP (SNPE)", "decoder on TFLite"], rose)
    box(446, 6, W - 454, 34, "LLM (GenieX)", ["Gemma 4 E4B Q4_0 on HTP0", "grammar-constrained JSON"], rose)
    arrow(204, 62, 318, 62)
    arrow(318, 76, 204, 76)
    d.add(String(261, 79, "HTTP over USB", fontSize=5.8, textAnchor="middle", fillColor=grey))
    arrow(378, 50, 378, 40)
    arrow(500, 50, 500, 40)
    return d


story = [
    P("Megathon X · Qualcomm Track | Milestone 2: Mid-Submission", title),
    P("Team B612 | On-Device AI Incident Report Assistant | Hardware: Qualcomm HDK8650 (SM8650, Snapdragon 8 Gen 3, "
      "Android 14) | Code: branch feat/npu-runtime merged to main | October 11, 2026", sub),
    HRFlowable(width="100%", thickness=0.8, color=accent, spaceAfter=2),

    P("1. Current approach and changes since M1", h),
    P("The full voice pipeline now runs on the HDK8650: microphone → Whisper encoder on the Hexagon DSP → "
      "LLM on the Hexagon NPU → deterministic Diamond Gate (agent_brain.py) → <i>populate_incident_form</i> "
      "tool call → Streamlit form + offline spoken reply. An Android app on the board hosts both models behind a "
      "loopback HTTP server (reached over <i>adb forward</i>); a FastAPI orchestrator on the laptop drives the "
      "brain, the offline TTS and the UI. No cloud call exists at run time."),
    architecture(),
    Spacer(1, 3),
    P("<b>What differs from the M1 plan:</b>"),
    table([
        ["Part", "M1 plan", "Now (measured on the board)", "Why it changed"],
        ["LLM", "Llama-3.2 via Genie/QAIRT",
         "Gemma 4 E4B (Q4_0, 5.2 GB) via GenieX / llama.cpp Hexagon backend; Qwen3-1.7B kept as a 3x faster option",
         "AI Hub's Llama/Genie export lists only 8 Elite-class chips (v79/v81) and Llama is gated; GenieX ships "
         "libggml-htp-v75 for our chip."],
        ["Speech-to-text", "Whisper DLC on DSP + TFLite decoder",
         "As planned: whisper-tiny encoder, w8a16 DLC with an SM8650 HTP cache, on the DSP through SNPE (encoder 14 ms); "
         "decoder on TFLite (CPU)", "Decoder needs variable-length input; sample app uses TFLite."],
        ["NPU honesty", "not specified",
         "Encoder built for the DSP only (no silent CPU fallback); LLM placement verified from the runtime's own log; "
         "red/green banner on board and in the UI",
         "SNPE and llama.cpp both fall back to CPU quietly; CPU use is not a valid signal (threads spin)."],
        ["Output control", "regex-defensive JSON parser",
         "+ grammar-constrained decoding (only the 10 form fields) and removal of 'Unknown/N/A' placeholders",
         "Small models wrote 'Unknown' for unspoken fields, which blocked the follow-up question."],
        ["Audio and UI", "VAD / push-to-talk; Streamlit",
         "Raw WASAPI capture, adaptive noise tracking, per-recording SNR estimate with a warning, Undo last turn; "
         "UI is now a pure client of the orchestrator API (the mock is gone)",
         "Windows' default capture path garbled speech; a misheard turn must not pollute the report."],
    ], [68, 80, 200, W - 348]),
    P("<b>Correction to M1:</b> M1 promised 'sub-second' turnarounds. Measured: speech-to-text 0.6–1.7 s per utterance, "
      "LLM extraction 10–15 s per turn with Gemma (4–5 s with Qwen3-1.7B), so a full turn is about 10–15 s.", body),

    P("2. Experiments run so far and results", h),
    P("<b>2.1 Whisper on the DSP.</b> Converted with the QAIRT 2.47 Windows toolchain (no Docker). FP32 DLC vs PyTorch: cosine "
      "1.000; w8a16 vs FP32: 0.994 (one real clip). On-board transcripts of clean synthetic speech were exact for two of three "
      "test sentences (the third misheard 'forklift')."),
    P("<b>2.2 LLM on the NPU</b> (same four extraction cases, incl. a two-turn dialogue; all produced correct fields):"),
    table([
        ["Model", "Weights on HTP0 / CPU", "Decode", "Per extraction", "Notes"],
        ["Gemma 4 E4B Q4_0", "2171 MiB / 3255 MiB (embedding tables)", "~11 tok/s", "10–15 s (avg 12.7 s over 14 calls)",
         "Chosen (larger model, per the documentation)"],
        ["Qwen3-1.7B Q4_0", "759 MiB / 487 MiB", "~29 tok/s", "~4.6 s", "Same accuracy on our cases; one-line swap"],
    ], [78, 130, 42, 108, W - 358]),
    P("Without constrained output Qwen failed the follow-up turn ('Unknown' written for the missing time, 18.8 s); with the grammar "
      "all four cases passed. A 14-call stress test exposed a real bug: GenieX kept the KV cache between independent prompts and "
      "failed with 'context exhausted' after a few turns. Resetting the context per call fixed it (14/14 passed)."),
    P("<b>2.3 Speech recognition vs noise.</b> A live miss ('conference room 2 around 10 AM' heard as 'at the end') led to a "
      "controlled study: the clean sentence mixed with our room's recorded noise at set levels.", body),
]

chart_row = Table([[wer_chart(), [
    P("<b>Findings.</b> The board's NPU Whisper-tiny is exact at 25–30 dB (speaking 20–30 cm from the mic) and degrades "
      "below 15 dB. Sentences played through the laptop speaker reach only ~5–7 dB, where tiny garbles them; small stays "
      "exact down to 7 dB.", cell),
    Spacer(1, 3),
    P("<b>Capture path A/B</b> (same played sentence, scored by the board): Windows' default 16 kHz path → '[Music]' / 'a water "
      "between you and the other'; raw exclusive-mode capture at the mic's native rate → 'water leak here conference for two "
      "round 10 AM. Maintenance has already been in the area'. Now the default, with automatic fallback.", cell),
    Spacer(1, 3),
    P("<b>Tried and rejected:</b> noise reduction (no gain); a Whisper vocabulary hint (average error 11% → 9% over 9 cases and "
      "it invented text from silence).", cell),
]]], colWidths=[236, W - 236])
chart_row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
story.append(chart_row)

story += [
    P("3. Progress on testing", h),
    B("<b>Automated:</b> 43 pytest tests (36 at M1): Diamond Gate, multi-turn memory, orchestrator API, a synthetic-sentence "
      "pause-detection test at strong/normal/faint levels, undo, signal-to-noise estimate."),
    B("<b>On-board self-test</b> (scripts/demo_selftest.py): 17 checks through the real stack (board reports Whisper and LLM on "
      "the NPU, spoken report, two-turn dialogue, tool call, submit, reset): all pass. Headless UI run: two turns → complete "
      "→ submit → reset; and misheard turn → Undo → corrected turn."),
    B("<b>Bugs found only by running on the board, and fixed:</b> native crash after a successful DSP run (undefined return) and a "
      "dangling output pointer in the sample code; GenieX context exhaustion; 'Unknown' placeholders; a microphone recorder that "
      "never detected a pause on a noisy mic; Windows capture mangling speech; a possible silent CPU fallback."),
    B("<b>Reproducibility:</b> one command (scripts/start_demo.bat) prepares the board, waits until both models are loaded and "
      "starts everything; runbook in docs/demo_runbook.md; benchmark and capture experiments are scripted in the repo."),

    P("<b>Latency per stage</b> (measured on the board; one full spoken turn is about 10–15 s with Gemma):"),
    table([
        ["Stage", "Time", "Notes"],
        ["Recording ends after the last word", "~1.8 s", "pause window; capped at 15 s of audio"],
        ["Whisper (encoder on DSP + TFLite decoder)", "0.6–1.7 s", "encoder alone ~14 ms"],
        ["LLM extraction", "10–15 s (Gemma) / 4–5 s (Qwen3-1.7B)", "decode-bound, ~100 generated tokens; ~1.5 s prompt"],
        ["Diamond Gate, form update, spoken reply", "< 1 s", "reply is spoken after the response is sent"],
    ], [200, 130, W - 330]),
    P("<b>Open risks:</b> (1) recognition accuracy below ~15 dB (see 2.3) – mitigated by the quality warning, Undo and the plan below; "
      "(2) Gemma's 10–15 s per turn is slow on stage; (3) GenieX is not validated by Qualcomm on SM8650 (it runs, and the "
      "weights are verified on HTP0); (4) the board's SELinux and port-forward settings reset on reboot, handled by the launcher; "
      "(5) the offline (Wi-Fi off) run has not been done yet.", body),

    P("4. Plan for the remaining time", h),
    B("<b>Recognition accuracy (main risk).</b> Move from whisper-tiny to base/small on the NPU. Qualcomm publishes prebuilt "
      "packages for our chip (public, 181 MB / 573 MB); this needs their Voice AI ASR SDK, or a self-built decoder on SNPE as the "
      "fallback. Until then: speak 20–30 cm from the mic, with the quality warning and Undo as the safety net."),
    B("<b>Latency.</b> Keep Gemma as the headline model, with Qwen3-1.7B as a tested 3x faster switch; spoken filler during the wait."),
    B("<b>Validation.</b> Live-voice rehearsal with a headset mic across scripted scenarios; run the full demo with Wi-Fi off to show "
      "no cloud dependency; repeat the self-test after every change."),
    B("<b>Hardening and delivery.</b> Final demo script, fallback plan (laptop mock clearly labelled), merge all branches to main, "
      "final write-up."),
]

doc.build(story)

import fitz  # noqa: E402  (PyMuPDF, used only to confirm the page limit)

pages = len(fitz.open(PDF))
print(f"{PDF}: {pages} page(s)")
assert pages <= 2, "M2 must be at most 2 pages"
