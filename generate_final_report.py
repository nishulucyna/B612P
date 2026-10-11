"""Generates deliverables/final_report.pdf (3 pages). Numbers come from measurements on the board; see scripts/ and deliverables/."""
import os

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deliverables", "final_report.pdf")
NAVY = colors.HexColor("#0F172A"); BLUE = colors.HexColor("#0369A1"); MUTED = colors.HexColor("#475569")
LINE = colors.HexColor("#CBD5E1"); SOFT = colors.HexColor("#F1F5F9"); CYAN = colors.HexColor("#0891B2")
AMBER = colors.HexColor("#F59E0B"); GREEN = colors.HexColor("#15803D"); GSOFT = colors.HexColor("#ECFDF3")

ss = getSampleStyleSheet()
BODY = ParagraphStyle("b", parent=ss["BodyText"], fontName="Helvetica", fontSize=8.7, leading=11.3, textColor=NAVY, spaceAfter=3)
SMALL = ParagraphStyle("s", parent=BODY, fontSize=7.7, leading=9.8, textColor=MUTED, spaceAfter=2)
CELL = ParagraphStyle("c", parent=BODY, fontSize=7.9, leading=9.8, spaceAfter=0)
HEAD = ParagraphStyle("h", parent=CELL, fontName="Helvetica-Bold", textColor=colors.white)
H1 = ParagraphStyle("h1", parent=BODY, fontName="Helvetica-Bold", fontSize=12.2, leading=15, textColor=BLUE, spaceBefore=7, spaceAfter=3)
TITLE = ParagraphStyle("t", parent=BODY, fontName="Helvetica-Bold", fontSize=21, leading=25, textColor=NAVY, spaceAfter=2)
BUL = ParagraphStyle("u", parent=BODY, leftIndent=11, bulletIndent=1, spaceAfter=1.5)


def P(t, st=BODY): return Paragraph(t, st)
def B(t): return Paragraph(t, BUL, bulletText="•")


def table(rows, widths, zebra=True):
    data = [[Paragraph(c, HEAD if i == 0 else CELL) if isinstance(c, str) else c for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=[w * inch for w in widths], repeatRows=1)
    st = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), 0.4, LINE), ("BACKGROUND", (0, 0), (-1, 0), NAVY),
          ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 2.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6)]
    if zebra:
        st += [("BACKGROUND", (0, i), (-1, i), SOFT) for i in range(2, len(rows), 2)]
    t.setStyle(TableStyle(st))
    return t


def pipeline():
    """The slide pipeline with the processor each step runs on."""
    steps = [("Microphone", "CPU", AMBER), ("Speech-to-text", "Whisper-small\nNPU / DSP", CYAN), ("LLM extraction", "Gemma or Qwen\nNPU (HTP)", CYAN),
             ("Mandatory\nfields?", "gate: CPU code", AMBER), ("Tool call +\nform", "CPU", AMBER), ("Screen + voice", "Piper TTS: CPU", AMBER)]
    W, H = 7.1 * inch, 0.9 * inch
    d = Drawing(W, H)
    bw, gap = 0.97 * inch, 0.29 * inch
    x = 0
    for i, (name, sub, col) in enumerate(steps):
        d.add(Rect(x, 22, bw, 40, rx=5, ry=5, fillColor=colors.white, strokeColor=col, strokeWidth=1.6))
        for j, ln in enumerate(name.split("\n")):
            d.add(String(x + bw / 2, 48 - j * 9, ln, fontName="Helvetica-Bold", fontSize=7.4, fillColor=NAVY, textAnchor="middle"))
        for j, ln in enumerate(sub.split("\n")):
            d.add(String(x + bw / 2, 10 - j * 8 + 0, ln, fontName="Helvetica", fontSize=6.6, fillColor=MUTED, textAnchor="middle"))
        if i < len(steps) - 1:
            ax = x + bw + 2
            d.add(Line(ax + 1, 42, ax + gap - 9, 42, strokeColor=MUTED, strokeWidth=1.3))
            d.add(Polygon([ax + gap - 9, 46, ax + gap - 9, 38, ax + gap - 2, 42], fillColor=MUTED, strokeColor=MUTED))
        x += bw + gap
    return d


def encoder_chart():
    rows = [("NPU (Hexagon, w8a16)", 167, CYAN), ("GPU (Adreno)", 316, colors.HexColor("#8B5CF6")), ("CPU (fp32)", 2168, AMBER)]
    W = 3.45 * inch
    d = Drawing(W, 62)
    mx, left, barw = 2168.0, 80, 1.55 * inch
    y = 44
    for name, ms, col in rows:
        d.add(String(0, y + 3, name, fontName="Helvetica", fontSize=6.9, fillColor=NAVY))
        d.add(Rect(left, y, max(4, barw * ms / mx), 10, fillColor=col, strokeColor=None))
        d.add(String(left + max(4, barw * ms / mx) + 4, y + 2.5, f"{ms} ms", fontName="Helvetica-Bold", fontSize=6.9, fillColor=NAVY))
        y -= 16
    return d


def footer(c, doc):
    c.saveState()
    c.setFont("Helvetica", 7); c.setFillColor(MUTED)
    c.drawString(0.6 * inch, 0.38 * inch, "AI Incident Report Assistant - Final Report | Megathon X, Qualcomm track | github.com/nishulucyna/B612P (main)")
    c.drawRightString(letter[0] - 0.6 * inch, 0.38 * inch, f"Page {doc.page} of 3")
    c.setStrokeColor(LINE); c.line(0.6 * inch, 0.52 * inch, letter[0] - 0.6 * inch, 0.52 * inch)
    c.restoreState()


S = []
# ================================================================================================================ page 1
S += [P("AI Incident Report Assistant", TITLE),
      P("Final report: voice-driven incident reporting that runs entirely on a Qualcomm HDK8650 (Snapdragon 8 Gen 3, Hexagon NPU)", ParagraphStyle("st", parent=BODY, fontSize=10, leading=13, textColor=MUTED)),
      HRFlowable(width="100%", color=BLUE, thickness=1.2, spaceBefore=3, spaceAfter=4),
      P("1. Summary", H1),
      P("A person describes an incident in natural speech. The phone transcribes it, extracts the ten form fields, checks the four mandatory ones and either asks "
        "<b>one</b> clarifying question or fills the form and speaks a confirmation. The user then reviews, edits and submits the report. "
        "<b>Everything runs on the phone with no network and no laptop</b>: speech recognition on the Hexagon DSP, the language model on the NPU, spoken replies from an "
        "offline voice engine. No cloud API is called at run time (models were downloaded once, beforehand, on a laptop)."),
      table([["Result (measured on the board, Wi-Fi off)", "Value"],
             ["Speech recognition (Whisper-small, encoder and decoder both on the DSP)", "4.4% word error rate on 10 natural narrations; 4.0% with 10 dB noise"],
             ["Information extraction and field mapping (22 narrations, 2 test sets)", "97 of 99 fields correct; 22 of 22 correct decisions on whether to ask or finish"],
             ["Time for one spoken report", "about 2 s transcription + 14 s extraction (4 s in the optional quick mode)"],
             ["Encoder speed (same model, same clip)", "167 ms on the NPU, 316 ms on the GPU, 2168 ms on the CPU (13x)"],
             ["Hardware evidence", "NPU message-channel interrupts 0/s idle, 40-60/s while working; audio DSP flat"]],
            [3.55, 3.75]),
      P("2. Pipeline, as specified in the problem statement", H1),
      pipeline(),
      P("Cyan = runs on the NPU/DSP; amber = ordinary CPU code. The mel spectrogram, tokenizer, the deterministic mandatory-field gate, the form and the UI are CPU code, as in Qualcomm's own reference apps.", SMALL),
      table([["Slide stage", "Implementation", "Details"],
             ["Speech-to-text", "Whisper-small, encoder w8a16 and decoder fp16 as SNPE graphs prepared for HTP v75", "Built here from OpenAI Whisper; encoder cosine 0.998 vs fp32, decoder 0.99999 vs PyTorch on the board"],
             ["LLM information extraction", "Gemma 4 E4B Q4_0 via GenieX (llama.cpp Hexagon backend); greedy decoding; JSON grammar", "Output limited to the 10 contract fields; same prompt always gives the same answer"],
             ["Mandatory fields present?", "Kotlin port of the agent brain (verified against the Python original), contract.json unchanged", "Missing field: ask one question. All four present: populate_incident_form tool call"],
             ["Populate form / review / submit", "Native touch UI: Edit, Clear, severity chips; Submit saves the 10 fields as JSON on the phone", "Edits pass through the same mandatory-field gate"],
             ["Screen and text-to-speech", "Live status, step-by-step processing, spoken replies from an offline Piper voice (sherpa-onnx engine)", "The voice engine declares no network permission"]],
            [1.35, 3.2, 2.75])]

# ================================================================================================================ page 2
S += [P("3. Models and where each part runs", H1),
      table([["Model", "Format", "Share of weights on the NPU", "Role / why chosen"],
             ["Whisper-small", "SNPE DLC: encoder w8a16 (187 MB), decoder fp16 (618 MB)", "100% (both graphs)", "Clear gain over Whisper-tiny under noise (WER 12.7% vs 18.3% at 5 dB) for +1 s"],
             ["Gemma 4 E4B (default)", "Q4_0 GGUF, 5.15 GB", "40% (2171 of 5426 MiB); the rest are large embedding tables", "Most careful at not inventing details; the model suggested in the documentation"],
             ["Qwen3-1.7B (quick mode)", "all-Q4_0 GGUF, 0.97 GB (re-quantised here)", "69% (82% of unique weights); all 28 layers", "3x faster, a third of the CPU time; needs an output guard"],
             ["Whisper-tiny", "DLC encoder + TFLite decoder", "encoder 100%", "First working pipeline; automatic fallback"],
             ["Piper en_US-lessac", "ONNX VITS voice, 87 MB", "0% (CPU)", "Spoken replies; the slide requires text-to-speech output"]],
            [1.3, 2.0, 1.85, 2.15]),
      P("Honest reading: all AI compute for speech recognition runs on the NPU. Gemma is a mixed model: about 40% of its weight bytes are on the NPU and its large lookup tables and some tensors stay in CPU memory, "
        "so token generation is only 1.1x faster than on the CPU (prompt processing is 6.4x faster). The Hexagon backend only runs Q4_0 tensors, which is why the all-Q4_0 Qwen file reaches 69%.", SMALL),
      P("4. Evidence that it really runs on the NPU", H1)]
ev = Table([[encoder_chart(), [
    B("<b>Hardware counter:</b> the interrupt counter of the CPU-to-cDSP message channel is 0/s idle and 40-60/s during speech recognition and extraction; the audio-DSP counter stays at 0."),
    B("<b>NPU temperature:</b> matrix and vector units rise from about 55 C to 92-95 C under load."),
    B("<b>Placement log:</b> GenieX reports where weights were placed; the app refuses to claim the NPU otherwise."),
    B("<b>Live in the app:</b> a small strip shows this counter, the temperature and which model is working.")]]],
           colWidths=[3.55 * inch, 3.75 * inch])
ev.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
S += [ev,
      P("Whisper-small encoder, one 30 s clip (snpe-net-run on the board).", SMALL),
      P("5. The five evaluation criteria", H1),
      table([["Criterion", "How it is met", "Evidence"],
             ["All AI on-device with Snapdragon acceleration, no cloud", "Whisper on the DSP, LLM on the NPU; no outbound network code; voice engine has no network permission; tested with Wi-Fi off", "Counters above; INTERNET permission is used only for an optional loopback link to the laptop UI"],
             ["Natural conversational speech, not commands", "Free speech goes to Whisper then an LLM; no command grammar or trigger words", "Test narrations include hesitations, chatter, self-correction, indirect wording"],
             ["Speech recognition accuracy", "Whisper-small on the DSP with noise-floor tracking and speech trimming", "WER 4.4% (clean) and 4.0% (10 dB noise); the smaller Whisper-tiny scored 12.7% to 19.7% on the same noisy sentences"],
             ["Extraction accuracy", "Grammar-constrained, greedy LLM output; placeholders removed", "97/99 fields on 22 narrations; invented values: 2 (Severity guessed; optional)"],
             ["Correct mapping to report fields", "Ten contract keys only; the four mandatory fields gate completion", "22/22 correct ask-or-complete decisions, including four reports that must NOT be completed"]],
            [1.65, 3.05, 2.6])]

# ================================================================================================================ page 3
S += [P("6. Accuracy and speed: both language models", H1),
      table([["", "Gemma 4 E4B (default)", "Qwen3-1.7B all-Q4_0 + guard (quick)"],
             ["Original 10 narrations, typed", "47/48 fields, gate 10/10", "46/48 fields, gate 10/10"],
             ["12 new held-out narrations, typed", "50/51 fields, gate 12/12", "51/51 fields, gate 12/12"],
             ["Speech through Whisper: clean / 10 dB noise", "44/48 / 45/48", "43/48 / 43/48"],
             ["3-turn clarification dialogue", "pass", "pass"],
             ["Time per extraction (4 CPU threads)", "13.9 s", "4.2 s"],
             ["CPU time per extraction", "52 cpu-s", "15 cpu-s"],
             ["Memory in use (app)", "3.75 GB, about 2.3 GB free", "about 0.65 GB resident"]],
            [2.5, 2.3, 2.5]),
      P("The app starts on Gemma; a <b>Model</b> toggle switches to Qwen in a few seconds and back. Without its output guard Qwen completed 2 of 12 held-out reports that should have asked a question "
        "(it wrote \"current time\" as the date); the guard removes such placeholder values and invented follow-up advice, and is applied in quick mode only. "
        "Test narrations were spoken by a synthetic voice, so the speech numbers are a proxy for real speakers.", SMALL),
      P("7. Engineering decisions that mattered", H1),
      B("<b>NPU only, never silently CPU.</b> The reference sample listed {DSP, CPU} and fell back quietly; the app now refuses to report NPU use unless placement is verified."),
      B("<b>Whisper decoder on the DSP.</b> Two bugs found by comparing against PyTorch: the converter transposes 3-D inputs, and an fp16 graph cannot hold token ids above 2048 (50258 became 50272), so embeddings are looked up on the CPU."),
      B("<b>Truly repeatable extraction.</b> Temperature 0 still left sampling on; top-k 1 with a fixed seed makes the same prompt give the same answer."),
      B("<b>CPU threads 8 to 4.</b> The SDK's eight busy-polling threads cost 98 CPU-seconds per extraction; four give the same speed for 52."),
      B("<b>No frozen screen.</b> The UI waited on a lock held for the whole 14 s model call; state is now published as lock-free snapshots."),
      B("<b>One verified brain.</b> The Kotlin port reproduces backend/agent_brain.py exactly (golden-file tests), so the locked contract and brain were never modified."),
      P("8. Limitations and next steps", H1),
      table([["Limitation", "Mitigation / next step"],
             ["Names and numbers are the weak point of speech recognition (\"Ravi\" heard as \"Rovey\", \"Room 2\" as \"room to\")", "Review screen lets the user correct any field; next: spoken read-back of low-confidence words"],
             ["About 14 s of waiting after speech with Gemma; model also guesses Severity when it was not said", "Quick Qwen mode (4 s); Severity is optional and editable"],
             ["In-progress report is only in memory; reports are local JSON; English only; one microphone distance (about a metre)", "Draft autosave, headset or push-to-talk, more languages, photo attachment, automatic time and place"],
             ["Test set is 22 narrations with a synthetic voice; the board clock was days behind", "Next: tests with real speakers on site; set the clock"]],
            [3.55, 3.75]),
      P("9. What would matter most in a real incident (not implemented)", H1),
      table([["Feature", "Why it matters when someone is stressed, hurried or offline"],
             ["Spoken read-back with yes/no for low-confidence names, numbers and rooms", "A wrong room or name is the most damaging error; Whisper exposes token probabilities, so doubtful words can be repeated aloud and confirmed hands-free"],
             ["Emergency fast path: one button, save immediately, mark critical, ask follow-ups afterwards", "The four-field gate must not delay the very first record of a life-threatening event"],
             ["Draft autosave, crash recovery and an outbox that syncs only if a network ever appears", "A killed app or empty battery must not lose a report; AI stays on-device"],
             ["Automatic time and place, photo or audio evidence, more languages, headset push-to-talk", "Fewer things to say, better evidence, and usable by reporters who are not comfortable in English or cannot hold the phone"],
             ["Safety checklist by incident type; audit trail with a hash; PIN lock; thermal and battery guard", "Reminds the reporter of immediate actions, proves the AI step ran on the device, protects names and injuries, avoids a throttled device"]],
            [3.0, 4.3]),
      P("10. Reproduce", H1),
      P("Code: <b>github.com/nishulucyna/B612P</b>, branch <b>main</b>. Phone only: run <font face='Courier'>scripts\\install_standalone.ps1</font> once over USB, unplug, open <b>Incident Assistant</b>, wait about 40 s "
        "for the green chip, tap the microphone. Evidence and tests: <font face='Courier'>scripts/npu_proof.py</font> (hardware trace, saved as deliverables/npu_proof.html), "
        "<font face='Courier'>scripts/e2e_eval.py</font> (accuracy), <font face='Courier'>python -m pytest</font>. Large model files are not in the repository.", BODY)]


def build():
    doc = SimpleDocTemplate(OUT, pagesize=letter, leftMargin=0.6 * inch, rightMargin=0.6 * inch, topMargin=0.5 * inch, bottomMargin=0.65 * inch,
                            title="AI Incident Report Assistant - Final Report", author="Megathon X team")
    doc.build(S, onFirstPage=footer, onLaterPages=footer)
    print("pages:", doc.page, "->", OUT)


if __name__ == "__main__":
    build()
