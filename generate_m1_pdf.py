import os
import fitz
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable

os.makedirs("deliverables", exist_ok=True)
pdf_path = "deliverables/M1.pdf"

doc = SimpleDocTemplate(
    pdf_path,
    pagesize=letter,
    leftMargin=36,
    rightMargin=36,
    topMargin=36,
    bottomMargin=36
)

styles = getSampleStyleSheet()

primary_color = colors.HexColor("#0f3460")
secondary_color = colors.HexColor("#16213e")
accent_color = colors.HexColor("#e94560")
text_dark = colors.HexColor("#1a1a24")

title_style = ParagraphStyle(
    'DocTitle',
    parent=styles['Heading1'],
    fontSize=18,
    leading=22,
    textColor=primary_color,
    fontName='Helvetica-Bold',
    spaceAfter=2
)

subtitle_style = ParagraphStyle(
    'DocSubtitle',
    parent=styles['Normal'],
    fontSize=10,
    leading=13,
    textColor=colors.HexColor("#4a4a5a"),
    fontName='Helvetica',
    spaceAfter=8
)

h1_style = ParagraphStyle(
    'SectionHeader',
    parent=styles['Heading2'],
    fontSize=12,
    leading=15,
    textColor=primary_color,
    fontName='Helvetica-Bold',
    spaceBefore=6,
    spaceAfter=4,
    borderPadding=2
)

body_style = ParagraphStyle(
    'Body',
    parent=styles['Normal'],
    fontSize=8.5,
    leading=11.5,
    textColor=text_dark,
    fontName='Helvetica',
    spaceAfter=4
)

bullet_style = ParagraphStyle(
    'Bullet',
    parent=styles['Normal'],
    fontSize=8.5,
    leading=11.5,
    textColor=text_dark,
    fontName='Helvetica',
    leftIndent=12,
    firstLineIndent=-8,
    spaceAfter=3
)

story = []

# --- PAGE 1 ---
story.append(Paragraph("Megathon X — Qualcomm Track | Milestone 1: Technical Approach", title_style))
story.append(Paragraph("<b>Team:</b> B612 | <b>Project:</b> End-to-End On-Device AI Incident Report Assistant | <b>Hardware:</b> Snapdragon® 8 Gen 3 (HDK8650)", subtitle_style))
story.append(HRFlowable(width="100%", thickness=1.5, color=primary_color, spaceAfter=8))

# Section 1
story.append(Paragraph("1. Problem Statement & Deep Architectural Understanding", h1_style))
story.append(Paragraph(
    "Traditional enterprise incident logging (safety hazards, infrastructure failures, chemical spills) relies on tedious multi-field web/mobile forms that workers delay or fail to complete under pressure. Qualcomm's Megathon X challenge mandates replacing manual entry with a <b>voice-driven, hands-free conversational assistant</b> that extracts structured information from natural narration.",
    body_style
))
story.append(Paragraph("<b>Core Constraints & Official Requirements:</b>", body_style))
story.append(Paragraph("• <b>Zero Cloud Execution (Mandatory):</b> All models (Speech-to-Text, LLM extraction, and TTS synthesis) must execute strictly on-device utilizing Snapdragon NPU / DSP acceleration via Qualcomm AI Runtime (QAIRT / QNN). Cloud APIs are disqualified.", bullet_style))
story.append(Paragraph("• <b>Strict 10-Field Data Contract:</b> Schema requires extracting 4 Mandatory fields (<code>incident_type</code>, <code>incident_location</code>, <code>date_time</code>, <code>immediate_actions_taken</code>) and 6 Optional fields (<code>severity_level</code>, <code>persons_involved</code>, <code>equipment_asset_involved</code>, <code>incident_description</code>, <code>witness_information</code>, <code>recommended_follow_up_action</code>).", bullet_style))
story.append(Paragraph("• <b>Interactive Diamond Gate:</b> Missing mandatory fields must trigger an active conversational clarification loop asking single targeted questions rather than dumping errors. Once all 4 mandatory fields are satisfied, the system emits a tool call (<code>populate_incident_form</code>) for UI hydration and review.", bullet_style))

story.append(Spacer(1, 4))

# Section 2
story.append(Paragraph("2. Idea & Abstract", h1_style))
story.append(Paragraph(
    "We present <b>IncidentIQ On-Device</b>: a resilient edge-intelligence architecture running on the Qualcomm HDK8650 (SM8650P). The system couples <b>Snapdragon DSP-accelerated Whisper ASR</b> with a quantized <b>Llama-3.2 / SLM information extractor running on the Hexagon NPU via Genie/QAIRT</b>. Rather than relying on simple keyword matching or fragile one-shot prompting, our core innovation is a <b>Deterministic State-Machine Agent Brain</b> that preserves conversational history across turns, defends against SLM hallucinations via multi-layer JSON sanitation, and guarantees zero cloud dependency with instantaneous sub-second audio turnarounds.",
    body_style
))

story.append(Spacer(1, 4))

# Table preview of the 10 fields & Contract
table_data = [
    [Paragraph("<b>Field Name</b>", body_style), Paragraph("<b>Status</b>", body_style), Paragraph("<b>Extraction Logic / Description</b>", body_style)],
    [Paragraph("incident_type", body_style), Paragraph("<b>MANDATORY</b>", body_style), Paragraph("Extracted or classified (e.g., Water Leak, Chemical Spill, Power Outage, Injury)", body_style)],
    [Paragraph("incident_location", body_style), Paragraph("<b>MANDATORY</b>", body_style), Paragraph("Physical facility, floor, lab, room, or perimeter identified from narration", body_style)],
    [Paragraph("date_time", body_style), Paragraph("<b>MANDATORY</b>", body_style), Paragraph("Timestamp or temporal reference normalized into structured time format", body_style)],
    [Paragraph("immediate_actions_taken", body_style), Paragraph("<b>MANDATORY</b>", body_style), Paragraph("Containment steps executed (e.g., valve shutoff, evacuation, area cordoned)", body_style)],
    [Paragraph("6 Optional Fields", body_style), Paragraph("Optional", body_style), Paragraph("Severity (Low-Critical), personnel, equipment, description, witnesses, follow-up", body_style)]
]
t = Table(table_data, colWidths=[110, 80, 350])
t.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f0f4f8")),
    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#d0d7de")),
    ('TOPPADDING', (0,0), (-1,-1), 2),
    ('BOTTOMPADDING', (0,0), (-1,-1), 2),
]))
story.append(t)

story.append(PageBreak())

# --- PAGE 2 ---
story.append(Paragraph("3. High-Level Pipeline & System Architecture", h1_style))
story.append(Paragraph(
    "Our solution operates as a synchronized hardware-software pipeline bridging physical Snapdragon NPU execution with an intuitive live incident operations dashboard:",
    body_style
))

arch_steps = [
    [Paragraph("<b>Stage</b>", body_style), Paragraph("<b>Engine & Hardware Layer</b>", body_style), Paragraph("<b>Functionality & Data Flow</b>", body_style)],
    [Paragraph("<b>1. Audio Capture</b>", body_style), Paragraph("Host / On-Device Mic (16kHz PCM WAV)", body_style), Paragraph("Captures voice notes with VAD (Voice Activity Detection) / Push-to-Talk.", body_style)],
    [Paragraph("<b>2. Speech-to-Text</b>", body_style), Paragraph("Whisper on Snapdragon DSP / NPU", body_style), Paragraph("Whisper DLC encoder running on DSP + TFLite decoder transcribes speech locally.", body_style)],
    [Paragraph("<b>3. State Engine Brain</b>", body_style), Paragraph("State Engine (<code>agent_brain.py</code>)", body_style), Paragraph("Constructs structured prompts incorporating conversation history and known fields.", body_style)],
    [Paragraph("<b>4. SLM Extraction</b>", body_style), Paragraph("Llama-3.2 on Hexagon NPU (Genie/QAIRT)", body_style), Paragraph("NPU generates strict JSON schema output; parsed through regex-defensive parsers.", body_style)],
    [Paragraph("<b>5. Diamond Gate</b>", body_style), Paragraph("Deterministic Decision Logic", body_style), Paragraph("Evaluates the 4 mandatory fields. If missing -> <code>status: collecting</code> with 1-sentence clarification. If present -> <code>status: complete</code>.", body_style)],
    [Paragraph("<b>6. Tool Call & UI</b>", body_style), Paragraph("FastAPI Server & Streamlit Dashboard", body_style), Paragraph("Emits <code>populate_incident_form</code>, lights form fields green, renders transcript.", body_style)],
    [Paragraph("<b>7. Offline TTS</b>", body_style), Paragraph("Offline TTS Engine (Device Speaker)", body_style), Paragraph("Speaks clarification prompts or final incident summary aloud.", body_style)]
]
t_arch = Table(arch_steps, colWidths=[95, 155, 290])
t_arch.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f0f4f8")),
    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#d0d7de")),
    ('TOPPADDING', (0,0), (-1,-1), 2),
    ('BOTTOMPADDING', (0,0), (-1,-1), 2),
]))
story.append(t_arch)

story.append(Spacer(1, 4))

# Section 4
story.append(Paragraph("4. Planned Testing & Validation Methodology", h1_style))
story.append(Paragraph("Our quality assurance framework guarantees robust performance under real-world industrial environments across 4 rigorous testing pillars:", body_style))

story.append(Paragraph("• <b>Automated Integration & Contract Tests:</b> Complete Pytest test suite (currently 36 passing tests) validating every state transition, JSON sanitization edge case, illegal severity handling, and multi-turn conversational memory persistence.", bullet_style))
story.append(Paragraph("• <b>Diamond Gate Multi-Turn Dialogue Scenarios:</b> Verified two-phase recovery loops (e.g., Turn 1: <i>'A pipe burst on the second floor'</i> -> Prompt: <i>'At what time did this occur?'</i> -> Turn 2: <i>'At 2 PM and we isolated the valve'</i> -> Immediate form completion without overwriting existing data).", bullet_style))
story.append(Paragraph("• <b>NPU Hardware Bridge & Fallback Resiliency:</b> Validated over ADB TCP forwarding (<code>adb forward tcp:8080 tcp:8080</code>). Includes an automated device-health watchdog with 30s cooldown and deterministic local fallback so live judging demonstrations never stall.", bullet_style))
story.append(Paragraph("• <b>Acoustic & Noise Stress Testing:</b> Evaluates Whisper STT accuracy under noisy ambient industrial background sounds (machinery hum, room reverberation, informal speech pacing).", bullet_style))

story.append(Spacer(1, 6))
story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#c0c7d0"), spaceAfter=6))
story.append(Paragraph("<b>Deliverable Milestone:</b> M1 (Approach Document) | <b>Repository:</b> IIIT-ECell/megathon26-b612 | <b>Date:</b> October 10, 2026", subtitle_style))

doc.build(story)

# Verify page count with PyMuPDF
doc_check = fitz.open(pdf_path)
page_count = len(doc_check)
print(f"Generated {pdf_path} with EXACTLY {page_count} pages.")
assert page_count == 2, f"Error: Page count is {page_count}, must be 2!"
