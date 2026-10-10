# How to Think About Any Problem Statement
### A risk assessment framework, illustrated with Megathon 2025 as case studies

---

> **The goal of this document is not to predict what appears in 2026.**
> It's to build a repeatable thinking process so that when you see *any* problem statement — at any hackathon, at any time — you can score it, compare it, and make a confident decision within the first 90 minutes.

---

## The Core Insight First

Most teams pick a problem statement based on **interest** or **familiarity**. That's the wrong axis. The right question is:

> *"Given our team's specific skills and 24 hours of time, which problem has the highest ratio of (upside if we win) to (probability of a broken demo)?"*

That's a risk-adjusted return question. This document is about how to calculate it fast.

---

## The 8-Dimension Framework

For any problem statement, score it on these 8 dimensions. Each captures a different type of risk or opportunity. Don't average them — they interact. The synthesis section explains how.

---

### Dimension 1: Constraint Hardness
*"How unforgiving is the hardest requirement?"*

**What to look for:** Every problem statement has requirements. Some are soft ("recommended") and some are hard ("strictly no cloud API"). Constraint hardness measures how badly a single requirement can sink your entire demo.

**Score:** 1 (soft, flexible) → 5 (binary, non-negotiable)

**The key question:** *If we can't satisfy the hardest constraint, does the whole project fail — or is there a graceful degradation?*

**Megathon 2025 examples:**

| Track | Hardest Constraint | Score | Why |
|-------|--------------------|-------|-----|
| Qualcomm | All inference on NPU — strictly no cloud | **5** | Zero partial credit. Model not on NPU = problem not satisfied. |
| OSDG | Must be implemented in C | **5** | No C, no submission. Hard gate. |
| Bhashini | Must use Bhashini APIs (ASR, MT, TTS, OCR) | **4** | Strong constraint. If the API is down, you have no fallback — but cached responses are possible. |
| Chubb PS1 | Explainability required (Grad-CAM / saliency maps) | **2** | Grad-CAM is a 5-line wrapper. Soft in practice. |
| Chubb PS2 | Use Kaggle auto insurance dataset | **1** | Trivially swappable. Almost no constraint. |
| SARAL | Extend an existing open-source codebase | **3** | You're locked to someone else's architecture, but not binary. |

**The rule:** Any constraint scored 4–5 requires either pre-event preparation or a very specific team skill. Without that, the problem is a trap dressed as an opportunity.

---

### Dimension 2: Preparation Dependency
*"How much of the work has to happen before the hack starts?"*

**What to look for:** Some problems are cold-start safe — you can build a winning solution from zero in 24 hours. Others require significant prep (SDK installation, model training, codebase onboarding, API key acquisition) *before* the event. High preparation dependency means it's actually a 3-week problem with a 24-hour finale.

**Score:** 1 (cold-start safe) → 5 (cannot be competitive without significant pre-event work)

**The key question:** *If our team walked in tomorrow with zero preparation, could we build a winning solution?*

**Megathon 2025 examples:**

| Track | What Must Be Pre-Prepared | Score |
|-------|--------------------------|-------|
| Qualcomm NPU | QNN SDK, device setup, ONNX conversion pipeline, INT8 quantization workflow | **5** |
| OSDG (C editor) | Must have implemented OT/CRDT before. Cannot learn distributed systems from scratch in 24h. | **5** |
| Bhashini | API key registration (5 min), latency testing (30 min). Doable in the first hour of the hack. | **2** |
| Chubb PS1 | Helpful to have a Grad-CAM template and a pretrained vision model ready. Not required. | **2** |
| Chubb PS2 | None. Load CSV, train XGBoost, add SHAP. Cold-startable in 4 hours. | **1** |
| SARAL | 2 hours reading the codebase. Extension idea should be decided beforehand. | **3** |

**The rule:** If Prep score ≥ 4, treat this as a "prepared teams only" problem. If you haven't prepped, skip it — not as failure, as strategy.

---

### Dimension 3: Crowd Factor
*"How many teams will build similar solutions?"*

**What to look for:** The popularity of a problem is driven by perceived accessibility. Easy entry = many teams = the delta between a good solution and a great one becomes tiny. When 50 teams have working demos, winning depends on presentation and one differentiating insight — not execution.

**Score:** 1 (very few teams pick this) → 5 (most of the room attempts this)

**The key question:** *If 50 teams all ship a working solution, what is the last remaining differentiator?*

**Megathon 2025 examples:**

| Track | Why Popular / Unpopular | Score |
|-------|-----------------------|-------|
| Chubb PS2 (churn) | ML on a Kaggle CSV. Every third-year student can start this in hour 1. | **5** |
| Bhashini | No hardware, no training, just API integration. Feels accessible to everyone. | **4** |
| Chubb PS1 (claims) | CV + fraud — interesting but requires knowing YOLO or Grad-CAM. Medium barrier. | **4** |
| Qualcomm | Hardware setup intimidates most teams. Strong self-selection. | **3** |
| SARAL | Vague, requires reading someone else's code. Most teams avoid ambiguity. | **2** |
| OSDG (C editor) | Systems programming in C. 90% of participants immediately skip. | **1** |

**The rule:** Crowd Factor and win probability are *inversely correlated for generic solutions*. A crowded problem can still be won — but only with a non-obvious angle that separates you from the crowd. High crowd + no differentiating angle = certain loss.

---

### Dimension 4: Demo-ability
*"How visually and emotionally compelling is a working demo?"*

**What to look for:** Judges watch demos for 3–5 minutes. Some problems produce demos that are *viscerally impressive* — something happens in real-time that feels magical. Others produce technically correct but emotionally flat demos (a table with accuracy numbers, a chart).

**Score:** 1 (flat, table-based output) → 5 (real-time, visual, emotionally resonant)

**The key question:** *What is the single most impressive moment in the demo? Would a non-technical judge remember it 20 minutes later?*

**Megathon 2025 examples:**

| Track | Best Demo Moment | Score |
|-------|-----------------|-------|
| Qualcomm | Phone camera pointed at a street. Prompt: "make it Van Gogh." 3 seconds later — a Starry Night version of the street. No internet. | **5** |
| Chubb PS1 | Upload a damaged car photo. Click analyze. See a heatmap of damage. See "TAMPERED" with a forgery highlight on the suspicious region. | **4** |
| Bhashini | Speak in Telugu. One second later, the response plays back in Hindi. A non-technical judge *hears* language crossing in real time. | **4** |
| SARAL | Upload a research paper. 30 seconds later, a 60-second explainer reel is ready. Strong, but less surprising if you've seen the tool. | **3** |
| OSDG | Two terminals editing simultaneously without conflict. Technically impressive, but only to engineers. | **3** |
| Chubb PS2 | Dashboard shows churn scores. SHAP bar chart. Visually correct, emotionally flat. | **2** |

**The rule:** All else equal, always pick the problem with the higher demo-ability score. Judges are human. They respond to what they *see and feel*, not what they *read about*.

---

### Dimension 5: Your Team's Skill Overlap
*"How much of what this problem requires does your team already know how to build?"*

**What to look for:** Skill overlap determines your starting point. High overlap means less time learning, more time building. This dimension is entirely personal — the same problem that's hard for one team is trivial for another.

**Score (for your team specifically):** 1 (zero overlap, must learn everything) → 5 (direct transfer, you've built components of this before)

**How to calculate it:** For each required component, ask: "Has someone on our team shipped something like this before?" If yes: +1. If they've done it under production pressure: +2. If none of us has touched this: 0.

**Megathon 2025 examples (scored for your team specifically):**

| Track | Components Needed | Your Score | Reasoning |
|-------|------------------|------------|-----------|
| Bhashini | Real-time audio pipeline, WebSocket, FastAPI, API integration | **4** | Sentinel is literally this. You've built a real-time audio pipeline under pressure. Bhashini replaces the ML model with their API. |
| Chubb PS1 | Computer vision (damage), XAI (Grad-CAM), image tampering detection | **3** | Grad-CAM is new but trivial to learn. Image tampering detection maps to your deepfake mindset. CV is new but well-tooled. |
| Qualcomm | QNN SDK, model quantization, Android or QIDK dev board | **2** | You understand inference pipelines conceptually. QNN is a new stack. Hardware setup is a new skill. |
| Chubb PS2 | Tabular ML (XGBoost), SHAP, Streamlit dashboard | **2** | You *can* do this, but so can everyone. No advantage. |
| SARAL | Reading an LLM pipeline codebase, adding features without breaking things | **2** | You know LLMs. You don't know SARAL's architecture. Codebase onboarding risk is real. |
| OSDG | Systems programming in C, CRDT, socket programming | **1** | No overlap. Full stop. |

**The rule:** Skill overlap is the single most important dimension for estimating how much of your 24 hours goes to *debugging* vs. *building*. Low overlap = most of your time on Stack Overflow, not on your actual solution.

---

### Dimension 6: Scope Ambiguity
*"How much time will you spend deciding what to build?"*

**What to look for:** Some problems are tightly scoped (MVP is obvious after one read). Others are open-ended (you define your own scope). Ambiguity is a time sink — every hour arguing about what to build in Hour 1 is an hour not building.

**Score:** 1 (crystal clear, MVP is obvious) → 5 (almost no guidance, you define everything)

**The key question:** *After reading the problem statement once, does your whole team know exactly what to build? Or would there be disagreement?*

**Megathon 2025 examples:**

| Track | Score | Why |
|-------|-------|-----|
| OSDG | **1** | Exact feature list: cursors, conflicts, offline, auth. Reads like a spec. |
| Chubb PS2 | **1** | Churn score + dashboard + SHAP. You know what to build on Day 1. |
| Chubb PS1 | **2** | Two components (damage + fraud). Some ambiguity in "fraud signals" but manageable. |
| Qualcomm | **3** | Medium ambiguity. The constraint (NPU only) is clear; *what* to generate and how is not. |
| Bhashini | **4** | Pick a domain, pick 4+ scenarios — that's a 30-minute team discussion before a line of code. |
| SARAL | **5** | "Extend SARAL." No rubric. No minimum requirements. You're guessing what impresses the judge. |

**The rule:** High ambiguity ≠ bad problem. But it means your first 30–60 minutes must be spent on *alignment*, not coding. If your team debates easily, deliberately avoid high-ambiguity problems.

---

### Dimension 7: Sponsor Signal Alignment
*"Does solving for this sponsor's specific agenda give you a strategic advantage with the judge?"*

**What to look for:** Every sponsor is at the hackathon for a specific reason — validating their technology, finding hires, exploring a market, demonstrating social impact. The judge sees your demo through the lens of that agenda. Framing your solution in *their language* is a multiplier on every other dimension.

**This is not a 1–5 score. It's three questions:**

1. **What does the sponsor want to validate?** (Their tech? A business hypothesis? A social outcome?)
2. **Who is their judge and what is their technical lens?** (A hardware engineer judges differently than a government AI program officer.)
3. **What story do they want to be able to tell their boss about the winning team?**

**Megathon 2025 examples:**

| Sponsor | Why They're There | Their Judge's Lens | Story They Want to Tell |
|---------|------------------|--------------------|------------------------|
| Qualcomm | Validate Snapdragon NPU for independent developers | Senior Engineering Manager — cares about efficient inference, real-world utility | "A student team ran Stable Diffusion on our NPU. No cloud. See what developers do with our hardware." |
| Bhashini | Demonstrate real-world use cases of their language APIs | Government AI program officer — cares about social impact, language coverage, accessibility | "A student team built an app that lets a Telugu-speaking farmer access government services in their native language." |
| Chubb | Find novel approaches to insurance tech | Insurance industry professional — cares about accuracy, explainability, scalability, realism | "A student team built a fraud detector that catches image tampering *and* explains the reasoning. We could use this." |
| SARAL/Prof. PK | Inspire builders to extend their open-source research tool | Academic researcher — cares about research democratization, new user segments, social reach | "A student team extended SARAL to reach people who currently can't access scientific knowledge at all." |
| OSDG | Systems CS challenge from a student club | CS fundamentals — cares about correctness, concurrency handling, elegance | "A team built a correct collaborative editor in C — proving they understand the fundamentals, not just the frameworks." |

**The rule:** Before your pitch, explicitly answer: *"What story does this sponsor want to tell about the winning team?"* Then reverse-engineer your demo and pitch to make that story easy for them to tell.

---

### Dimension 8: Failure Mode Risk
*"What are the most likely ways this project crashes before demo time — and how recoverable are they?"*

**What to look for:** Every project has failure modes. Some are recoverable (API returns wrong format → add error handling). Some are catastrophic (hardware device doesn't boot → demo is gone). Risk assessment isn't about avoiding all risk — it's about choosing risks that are *manageable* vs. *existential*.

**Score:** 1 (all failure modes are recoverable) → 5 (existential failure modes with no fallback)

**The Three Failure Mode Categories:**
- **Category A: Technical** — Your own code breaks or the model doesn't work.
- **Category B: Infrastructure** — A dependency you don't control (API, hardware, network) fails.
- **Category C: Time** — You run out of time before the demo is coherent.

**Megathon 2025 examples:**

| Track | Cat. A | Cat. B | Cat. C | Overall Risk |
|-------|--------|--------|--------|-------------|
| Qualcomm | High (model conversion fails silently) | High (QNN device setup fails) | High (NPU pipeline debugging takes 15+ hrs) | **5 — Existential** |
| OSDG | High (concurrency bugs are invisible under load) | Low (all local) | High (24h is not enough time for correct OT) | **4** |
| Bhashini | Medium (API integration bugs) | High (Bhashini sandbox outage) | Low (MVP achievable in 10 hours) | **3** |
| Chubb PS1 | Low-medium (Grad-CAM is well-supported) | Low (Kaggle data is local) | Low (modular — each component is independently demoable) | **2** |
| SARAL | Medium (extension might break existing functionality) | Medium (depends on SARAL backend) | Medium (codebase onboarding is unpredictable) | **3** |
| Chubb PS2 | Low (XGBoost is very stable) | Low (all local data) | Very Low (4-hour problem) | **1** |

**The fallback rule:** For any failure mode scored 4–5, ask: *"Can we demo this convincingly with pre-recorded video or hardcoded mock data if the live demo fails?"* If yes: survivable. If the live demo failing means no coherent presentation at all: existential risk.

---

## Putting It Together: The Decision Matrix

Fill this in for each problem statement you're evaluating:

```
Problem Statement: _______________

Constraint Hardness:        [ /5]  — Can we satisfy the hardest requirement?
Preparation Dependency:     [ /5]  — Did we prep for this? Be honest.
Crowd Factor:               [ /5]  — How many teams build the same thing?
Demo-ability:               [ /5]  — Is the "wow moment" visible and memorable?
Skill Overlap (your team):  [ /5]  — How much of this have we built before?
Scope Ambiguity:            [ /5]  — Do we know what to build after one read?
Sponsor Signal:             [qualitative] — What story do they want to tell?
Failure Mode Risk:          [ /5]  — Do existential failure modes exist?
```

**How to interpret the scores:**

- **Constraint Hardness + Preparation Dependency ≥ 4 each, and you haven't prepped:** Skip. No amount of excitement overrides this.
- **Crowd Factor ≥ 4, Skill Overlap ≤ 3, no differentiating angle ready:** You're building the same thing as 40 other teams. Skip or have a non-obvious angle locked in Hour 1.
- **Demo-ability + Sponsor Signal aligned:** These determine your *ceiling*. Optimize for the problem where both are high — that's where the maximum impression lives.
- **Scope Ambiguity + Failure Mode Risk both high:** These determine your *floor*. This is the combination that produces teams with zero demoable output by pitch time.

**The composite question:** *"Can our team hit this problem's ceiling without falling through its floor?"*

---

## The Differentiation Drill — Finding the Niche

After scoring, run this 20-minute exercise before you commit. It determines whether you have a *winning angle* or a *table-stakes solution*.

**Step 1: Name the obvious solution.**
What would a generic team build? This is your floor. The obvious solution loses in a crowded field.

**Step 2: Name the ignored user.**
Every problem imagines a user. Who is the user the problem *forgot*? Who has this problem most acutely but is never in the room when the problem statement is written?

**Step 3: Name the ignored dimension.**
Most solutions solve the problem in one dimension (text only, or image only, or point-in-time only). What happens when you add another? Temporal patterns. Cross-modal inconsistency. Behavioral signals over time. The solution that operates in *more* dimensions than the competition is almost always more interesting.

**Step 4: Name the cross-domain technical component.**
What is one technique from a different domain that could be applied here? Hackathon wins often come from cross-domain transfer — applying your expertise in domain A to solve domain B in a way no domain-B specialist would think of.

**Step 5: Validate the combination.**
Does your niche angle still satisfy the problem's hard constraints? Can it be built in 24 hours? Can it be demoed in 5 minutes? If all three: you have a winning angle.

**Megathon 2025 worked examples:**

| Track | Obvious Solution | Ignored User | Ignored Dimension | Non-Obvious Technical Component |
|-------|-----------------|--------------|-------------------|--------------------------------|
| Qualcomm | Style transfer filter app | Creators without design skills | Real-time camera + semantic understanding of *content* | ControlNet-style conditioning: the model knows *what* it's looking at, not just applying a filter |
| Bhashini | Healthcare chatbot with language toggle | A farmer in interior Andhra who cannot read in *any* language | Voice-first, zero-literacy UX — no text interface at all | Fully voice-I/O loop: ASR → LLM → TTS, no text entry point |
| Chubb PS1 | "Is this car damaged?" detector | An investigator reviewing 200 claims/day who can't check each one | Temporal: fraud *across multiple claims*, not within one | Image similarity + cross-claim consistency = fraud *network* detection |
| Chubb PS2 | Churn prediction dashboard | The non-technical branch manager who can't read a SHAP chart | Natural language querying of predictions | LLM + Pandas code generation = "talk to your customer data" |
| SARAL | Add a new output format | Researchers who *write* in Indian languages (not just read) | Indian-language papers as *input* (not just output) | OCR for regional scripts → feed into the SARAL pipeline for non-English source material |

---

## The Hour-0 Decision Protocol

When you see the problem statements for the first time, use this sequence exactly:

**Minutes 0–15:** Read every problem statement once. Don't discuss yet. Score each on Constraint Hardness and Preparation Dependency in your head. Immediately eliminate any problem where both scores are ≥ 4 *and* you haven't prepped.

**Minutes 15–30:** Score remaining problems on Skill Overlap and Demo-ability. Rank them. You should now have 1–3 candidates.

**Minutes 30–45:** Run the Differentiation Drill on each candidate. Find the niche angle. The problem where your differentiating angle is clearest is your winner.

**Minutes 45–60:** Agree on one problem as a team. Write the one-sentence project description on paper. Assign roles. Start building.

**The fail-safe:** If you're still debating at Minute 75, pick the problem with the lowest Failure Mode Risk score and start building the "boring" solution. You can add the differentiating angle once the base is working. You cannot add anything if you've spent 4 hours debating and shipped nothing.

---

## The Six Archetypes — What Every Hackathon Gives You

The 5 tracks from Megathon 2025 are a representative sample of problem types that appear at almost every hackathon. Learn to recognize the archetype in the first read:

| Archetype | 2025 Example | Recognizable By | Winning Strategy |
|-----------|-------------|----------------|-----------------|
| **Hardware constraint** | Qualcomm NPU | A sponsor with specific hardware/SDK they want validated | Pre-prep the SDK. The hardware gate filters 80% of teams automatically. |
| **Multilingual / social impact** | Bhashini | Government or social sector sponsor, language/accessibility focus | Find the ignored user who has no voice in the room. Voice-first UX is almost always the differentiator. |
| **Domain AI (structured)** | Chubb PS1 | Industry sponsor, specific business problem, provided datasets | Apply cross-domain technical transfer. Your deepest skill from a different domain is your edge. |
| **Domain AI (easy / safe)** | Chubb PS2 | Same sponsor, lower-bar second problem | Only attempt with a genuinely non-obvious angle locked in. Otherwise, the crowd wins. |
| **Extend existing project** | SARAL | Academic or startup presenting their own tool | Read the codebase before the hack. Know what it *doesn't* do. Build for the downstream user they haven't reached yet. |
| **Systems / fundamentals** | OSDG | CS-culture sponsor, low-level technical challenge | Only for teams with the specific prerequisite skills. Usually not the main prize. |

---

## The One Thing That Determines Everything

After all the analysis, one meta-factor overrides all 8 dimensions:

> **The team that ships a *working, specific, explainable* solution beats the team with the more impressive idea that partially works.**

Every dimension in this framework is scaffolding for one moment: standing on that stage with a demo that runs and a story that's specific.

- **Specific** means: you can name the exact person whose life this changes.
- **Working** means: the happy path runs end-to-end without crashing.
- **Explainable** means: a non-technical judge can retell your story 10 minutes later.

That's the target. Everything else is in service of it.

---

## Overview: The 5 Tracks at a Glance

| # | Sponsor | Statement | Type | Difficulty | Crowd Factor | Your Edge |
|---|---------|-----------|------|-----------|--------------|-----------|
| 1 | **Qualcomm** | Real-time generative art from camera feed (on-device, NPU only) | Hardware + GenAI | 🔴 Very Hard | 🟡 Medium | 🟡 Partial |
| 2 | **Bhashini** | Multilingual AI app (ASR, MT, TTS, OCR) — 4 domains, 4+ scenarios | Full-stack AI | 🟡 Medium | 🔴 Very High | 🟢 Strong |
| 3 | **Chubb PS1** | AI Multimodal Claims Assessment & Fraud Intelligence | CV + NLP | 🟡 Medium | 🔴 Very High | 🟢 Strong |
| 4 | **Chubb PS2** | AI Churn Reasoning & Retention for Auto Insurance | ML + Dashboard | 🟢 Low | 🔴 Extremely High | 🔴 Weak |
| 5 | **SARAL/DemRes** | Extend SARAL: research paper → engaging content (reels, podcasts, slides) | LLM + Multimodal | 🟢 Low-Medium | 🟡 Medium | 🟡 Partial |
| 6 | **OSDG** | Rich collaborative text editor with concurrency + offline merge (in C) | Systems/CS | 🔴 Brutal | 🟢 Low | 🔴 None |

---

## Track 1: Qualcomm — Generative Art from Camera Feed (On-Device, NPU)

### The Exact Problem
> *Real-time (almost) generative art from camera feed. Camera captures snapshots. User prompts for generative art — convert image to vintage style, repaint image, etc. All models must run on NPU on edge device only. Strictly no cloud API. Value addition: voice input.*

**Evaluation criteria:**
- All models accelerate on NPU (non-negotiable)
- Realistic output for multiple scenes
- Image quality retention
- Value addition (voice input)

---

### Metric-by-Metric Breakdown

#### 🎯 Clarity of the Ask
**8/10 — Very clear.** The constraints are unusually specific: on-device only, NPU-only inference, camera feed, generative art, and voice input as bonus. There is almost no ambiguity. You know exactly what to build.

#### 🔧 Technical Difficulty
**9/10 — Extremely hard.** This is the hardest problem from a pure implementation standpoint. Here's why:

- **The NPU constraint is not a nice-to-have — it is mandatory.** You cannot call a cloud API. You cannot run inference on CPU and claim NPU. This means you need the **Qualcomm AI Hub / QIDK SDK** actually set up and working on a Snapdragon device before the hack starts.
- Stable Diffusion (even compressed variants like LCM-LoRA or SDXL-Turbo) at INT8 quantization on a mobile NPU requires non-trivial model conversion (PyTorch → ONNX → QNN binary), and the conversion alone can take hours if you haven't done it before.
- Camera feed integration + prompt parsing + inference + output rendering — all in a real-time pipeline — is a serious engineering challenge.
- The winning team from 2025 (SnapGen) did exactly this and won. That means the bar is now **a known, solved solution**. You'd need to match or exceed it, which is extremely hard without the same prep.

#### 👥 Crowd Factor (How Many Teams Pick This)
**5/10 — Medium pickup, very high dropout.** Many teams will be excited by the "AI art" framing and try this. Probably 20–30% attempt it. But the NPU-only constraint filters teams to almost zero working demos by hour 18. In 2025, the winning team likely prepared the Qualcomm SDK setup *before* the hack started — without that, this problem is nearly uncompletable in 24 hours.

#### 🏆 Win Probability for an Average Team
**2/10 — Very low.** Without pre-installed Qualcomm SDK, device access, and familiarity with quantization pipelines, you will spend the first 12 hours just trying to get inference running on-device. Demo day will show a half-working prototype at best.

#### 🟢 Your Specific Edge
**Partial.** You have real-time inference experience (Sentinel WebSocket pipeline, FastAPI). You understand model efficiency intuitively. But you've never worked with the Qualcomm NPU stack specifically. That's a hard gap to close in 24 hours.

**If Qualcomm returns in 2026:** The smart move is to prepare the QNN SDK and do a model conversion dry-run *before* the event. The problem itself is achievable — but only with prep.

#### 💡 The Niche Angle Nobody Takes
Most teams will do "vintage photo" style transfer. The niche angle is **real-time semantic re-framing**: the model doesn't just apply a style filter, it understands *what's in the scene* (a face, a street, a sunset) and generates art that is *contextually appropriate* to the content. You'd need a lightweight vision encoder + ControlNet-style conditioning — but the storytelling is much stronger: *"This isn't just a filter — it understands what it's looking at."*

#### 📊 Judging Rubric Alignment
The Qualcomm judge is a Senior Engineering Manager. They care most about: **does it actually run on the NPU?** And secondary: is the output quality impressive? The "voice input" bonus is trivial to add (Whisper-tiny on NPU or even via Bhashini ASR).

#### 🎪 Hackathon Suitability
**5/10.** The problem is brilliant for a week-long hackathon. For 24 hours with zero setup, it's punishing. The best teams treat Qualcomm as a 3-week preparation problem, not a 24-hour build problem.

---

## Track 2: Bhashini — Multilingual AI App (4 Domains, 4+ Scenarios)

### The Exact Problem
> *Build an innovative application leveraging Bhashini ASR, MT, TTS, OCR APIs. Pick one domain: Tourism / Healthcare / Workplace-Bank / Agriculture. Address at least 4 scenarios. Must include: real-time speech-to-speech (<10s), document translation, scanned image OCR + translation, query/extraction/summarization, multi-modal (2+ modalities). Full-stack deployable mobile-responsive web app.*

**Evaluation criteria (with weights):**
- Innovation & Solutioning (features, scenario coverage)
- Usage of Models (modalities, real-time S2S, multi-modality handling)
- Design & Architecture (resource utilization, performance)
- Application Experience (UI cleanliness, integrated functionality)
- Presentation & Documentation
- Bonus: real-time S2S <10s, conversational speech, model adaptation

---

### Metric-by-Metric Breakdown

#### 🎯 Clarity of the Ask
**6/10 — Moderately clear, but dangerously broad.** The problem gives you a menu of domains and scenarios, which sounds helpful but is actually a trap. Teams that try to address everything end up with a "bits and pieces" app that Bhashini explicitly warns against. The path to winning is **ruthless curation**: one domain, 4–5 tightly integrated scenarios, seamless UX.

#### 🔧 Technical Difficulty
**5/10 — Medium, dominated by integration complexity.** The ML models are provided by Bhashini — you don't train anything. But integration is subtle:
- Bhashini API can be slow and rate-limited. Real-time S2S under 10 seconds requires careful buffering and pre-processing.
- The OCR quality for regional scripts (Telugu, Kannada, etc.) varies significantly. You need fallback handling.
- Connecting 4+ modalities into a coherent UX without it feeling like a demo — this is where most teams fail.

The biggest technical risk: **Bhashini API availability** during the hackathon. If the sandbox goes down, your entire project breaks. Mitigation: cache sample API responses early and build a fallback mode.

#### 👥 Crowd Factor (How Many Teams Pick This)
**9/10 — Extremely popular.** This is the most accessible problem. No hardware required, no model training, just API integration and UI. Expect 40–50% of teams to attempt Bhashini. The winning team must distinguish itself with *depth* (deeply serving one persona) rather than *breadth* (touching all 5 scenarios superficially).

#### 🏆 Win Probability for an Average Team
**4/10 for a generic approach.** Most teams build a generic "healthcare chatbot" or "tourist translator" that does the same thing. The winning team does something specific and unusual. Win probability rises to **7/10 if you pick the right angle.**

#### 🟢 Your Specific Edge
**Strong.** Your audio pipeline experience (WebSocket, real-time processing, FastAPI) is directly useful for the real-time speech-to-speech component — which is the hardest technical requirement and the one most teams fail on. While other teams battle with buffering and latency, you've already solved this for Sentinel.

#### 💡 The Niche Angle Nobody Takes
**Everyone builds for the tech-savvy user.** The winning Bhashini angle is the **zero-literacy user**:

Pick **Agriculture** domain. Your persona is a farmer in interior Andhra Pradesh who cannot read or write in any language. Every interaction must be voice-first, voice-out. The workflow:
- Farmer holds phone → speaks in Telugu about a disease they see on their crop → app converts to text (Bhashini ASR)
- LLM queries agricultural knowledge base → generates advice in Telugu
- App reads advice aloud (Bhashini TTS) AND shows a simple visual (image of healthy vs diseased leaf)
- Farmer photographs their document (e.g., a loan agreement) → OCR + MT → LLM explains it in simple terms → TTS reads the explanation

This is a **fully voice-first, multimodal, multilingual loop** that nobody else will build, because everyone assumes the user can type.

The "winning" scenario framing for judges: *"This app assumes the user cannot read. That's 265 million people in India."*

#### 📊 Judging Rubric Alignment
Bhashini judges care about: **does the multilingual flow actually work end-to-end?** They are not impressed by English-heavy apps that add a language selector at the end. They want to see a demonstration in an actual Indian language. Prepare a demo where you and a teammate speak to the app in Telugu/Hindi/Tamil. That visual is unforgettable for judges.

#### 🎪 Hackathon Suitability
**9/10.** This is the ideal 24-hour problem. APIs are ready, datasets are publicly available, and a working MVP is achievable by hour 12. The remaining 12 hours go into polish, UX, and the one "wow" scenario.

---

## Track 3: Chubb PS1 — AI Multimodal Claims Assessment & Fraud Intelligence

### The Exact Problem
> *Build an AI-powered prototype for: (1) Image damage detection + severity + cost band, (2) Fraud detection (image tampering, behavioral inconsistency, duplicate claims). Components: vision model for car damage, text model for claim narrative understanding, fraud signal detection. Explainability required (Grad-CAM / saliency maps). Datasets provided: Kaggle car damage, CompCars, CASIA2.*

**Evaluation criteria:**
- Innovation & System Design (20%)
- Technical Depth (25%)
- Accuracy & Robustness (25%)
- Usability & Explainability (15%)
- Presentation & Impact (15%)

---

### Metric-by-Metric Breakdown

#### 🎯 Clarity of the Ask
**8/10 — Very clear.** Two explicit components (damage assessment + fraud detection), specific datasets provided, specific techniques suggested (Grad-CAM). This is one of the most well-defined problem statements.

#### 🔧 Technical Difficulty
**6/10 — Medium.** The core ML pipeline is standard:
- Car damage detection: fine-tune a ResNet/EfficientNet or use a pretrained YOLO model on the Kaggle dataset → severity classification (minor/moderate/severe) → cost band mapping
- Fraud detection: CASIA2 dataset for image tampering → a forgery detection model (ELA analysis, or a pretrained CNN)
- XAI: Grad-CAM is a 3-line PyTorch implementation using existing libraries

The hard part is **integration**: combining vision + text (claim narrative) + fraud signals into a coherent backend, and then displaying it in a clean UI with Grad-CAM overlays. This is achievable in 24 hours but requires clean task splitting.

#### 👥 Crowd Factor (How Many Teams Pick This)
**8/10 — Very popular.** Insurance + AI is a well-understood combination. Expect 30–40% of teams to try this. The Kaggle dataset is pre-linked, which lowers the barrier even further. Competition is fierce.

#### 🏆 Win Probability for an Average Team
**5/10.** A standard YOLO + fraud heuristic + Grad-CAM implementation is not enough. The winning team adds something non-obvious.

#### 🟢 Your Specific Edge
**Strong.** Key insight: **fraud detection in claim images maps directly to your deepfake detection work.** Image tampering detection (CASIA2 dataset) is essentially the image domain version of what Sentinel does in the audio domain — detecting synthetic/manipulated content. You have mental models for:
- How to approach binary classification on manipulated media
- What ensemble strategies work (you used a dual-model ensemble for Sentinel)
- How to handle cross-domain generalization (your ASVspoof experience)

You can frame a dual-model ensemble approach (one for damage severity, one for image authenticity) and explain *why* the ensemble works — which most teams won't be able to articulate.

#### 💡 The Niche Angle Nobody Takes
**Everyone builds a "did this car get damaged?" detector.** The niche is **temporal fraud analysis**: detecting *serial* fraudsters across multiple claims over time.

Add a layer: when a new claim comes in, the system checks:
1. Was this exact vehicle photographed at the same damage location in a previous claim? (duplicate claim detection via image similarity)
2. Does the claim narrative contain suspicious patterns seen in rejected historical claims? (text-based fraud signature matching)
3. Is the damage pattern inconsistent with the reported accident description? (cross-modal inconsistency — similar to your audio-visual consistency work in Sentinel)

Frame this as: *"We don't just detect fraud in isolation — we detect fraud networks."* That's the insight that wins.

#### 📊 Judging Rubric Alignment
Technical Depth (25%) and Accuracy & Robustness (25%) carry the most weight. Run your models on the full validation set and report actual numbers: *"Our damage severity classifier achieves 87% accuracy on 500 held-out images."* Bring numbers to the pitch. Chubb judges are industry professionals who trust metrics, not vibes.

Also: the Grad-CAM visualization is explicitly encouraged. Make it beautiful — a heatmap overlaid on the damaged car photo is one of the most visually compelling demo elements possible.

#### 🎪 Hackathon Suitability
**8/10.** Good problem for 24 hours. The datasets are given, the techniques are known, the win is in execution depth + the one non-obvious feature.

---

## Track 4: Chubb PS2 — AI Churn Reasoning & Retention for Auto Insurance

### The Exact Problem
> *Train an ML model on historical customer/policy/demographic data to predict churn probability. Output: per-customer churn score, reasons for churn, interactive dashboard with regional trends. Add explainability (SHAP/LIME). Dataset: Kaggle Auto Insurance churn dataset.*

**Evaluation criteria:**
- Innovation & Explainability (30%)
- Technical Approach (25%)
- Accuracy & Robustness (20%)
- User Experience (15%)
- Presentation & Impact (15%)

---

### Metric-by-Metric Breakdown

#### 🎯 Clarity of the Ask
**9/10 — Crystal clear.** The deliverable is essentially: train a churn predictor on a public Kaggle dataset, add SHAP, build a dashboard. Almost nothing is ambiguous.

#### 🔧 Technical Difficulty
**3/10 — Low.** This is an undergraduate ML assignment:
- Load Kaggle dataset → feature engineering → train XGBoost/LightGBM → compute SHAP values → plot
- Dashboard: Streamlit or Plotly Dash with a filter for region, policy type, churn score
- Retention recommendations: if SHAP says "high premium is the top driver", recommend a premium reduction offer

This is completable in 6 hours by any ML-competent team. The remaining 18 hours go into polish.

#### 👥 Crowd Factor (How Many Teams Pick This)
**9/10 — The most popular problem.** This is the "safe" choice. Any third-year CS student with basic ML knowledge will pick this because it feels achievable. This is exactly why **you should not pick this**.

The problem with easy problems: **the winning bar is very high because everyone has a working solution.** When 100 teams all have an XGBoost churn model with SHAP, you need something extraordinary to stand out — and there's not much room for extraordinary in churn prediction.

#### 🏆 Win Probability for an Average Team
**3/10.** The field is too crowded. The delta between a "good" solution and the winning solution in this domain is small, and it depends heavily on how well you present, not what you build.

#### 🟢 Your Specific Edge
**Weak.** There's no obvious connection to your audio/real-time ML background. You'd be competing purely on execution speed and presentation quality — two things everyone else can match.

#### 💡 The Niche Angle Nobody Takes
If forced to pick this, the angle is **conversational churn analysis**: replace the dashboard with a natural language interface. Instead of the insurance manager clicking through filters, they ask: *"Show me all customers in Hyderabad over 40 with two or more lapsed policies and a high churn score"* — and the system queries the database and explains the reasoning in plain English.

The technical angle: LLM + Pandas code generation + SHAP explanation generation = a "talk-to-your-customer-data" interface that feels like the future of business intelligence. Much more impressive than a Tableau clone.

#### 📊 Judging Rubric Alignment
Innovation & Explainability (30%) is the heaviest criterion — which means the judges know a basic solution is boring. They're explicitly incentivizing non-obvious approaches. The team that adds the LLM NL interface wins on this dimension.

#### 🎪 Hackathon Suitability
**6/10.** Easy to start, hard to differentiate. The "safe" choice is usually the "can't win" choice in competitive hackathons.

---

## Track 5: SARAL / DemocratiseResearch — Extend SARAL

### What SARAL Is
SARAL (by Prof. PK / Precog Lab, IIIT Hyderabad) is a live product that converts research papers (PDF) into:
- Short video reels (with AI narration and auto-generated slides)
- Podcasts
- Poster summaries
- Slide decks

It supports 18 Indian languages via Bhashini TTS. It's recognized by India's Ministry of Science & Technology. It already has a Chrome extension and a deployed web app at `saral.democratiseresearch.in`.

The presentation was a live demo of SARAL by Prof. PK himself, with links to GitHub, news articles, and usage instructions. The problem statement was effectively: **"Here is this tool we built. Make it better. Extend it. Use it as a platform."**

---

### Metric-by-Metric Breakdown

#### 🎯 Clarity of the Ask
**4/10 — Very vague.** Unlike every other track, SARAL gives you no rubric, no evaluation criteria, no specific deliverable. You're being asked to build something on top of an existing open-source project. The judge is Prof. PK himself (a well-known IIIT professor, ACM India VP, TEDx speaker). What impresses him is unclear — you'd need to understand what SARAL *doesn't* do.

The lack of a rubric cuts both ways: you can do anything, but you don't know what "winning" looks like.

#### 🔧 Technical Difficulty
**5/10 — Medium, dominated by codebase onboarding.** You'd need to read the SARAL codebase, understand how it works, and build a new feature without breaking existing functionality. In a 24-hour hack, the time cost of "reading someone else's code" is significant.

The core SARAL pipeline: PDF → extract text + structure → LLM (script generation) → Bhashini TTS (voice) → slide generation → video assembly. Extending it means adding a new output format, a new input format, or a new interaction modality.

#### 👥 Crowd Factor (How Many Teams Pick This)
**Medium — maybe 10–15%.** This is a less popular choice because:
1. The problem is vague
2. You have to read existing code
3. It feels less "impressive" than building from scratch

But lower competition means more room to stand out.

#### 🏆 Win Probability for an Average Team
**4/10.** Low clarity makes it risky. But if you have a strong idea for what to add, win probability rises significantly — you're essentially pitching to the creator of the tool.

#### 🟢 Your Specific Edge
**Partial.** Your LLM integration experience is relevant. Your audio pipeline work (Whisper, Twilio, FastAPI) is relevant if you build a "paper → podcast with actual conversation between AI hosts" feature. But there's no deepfake detection angle here.

#### 💡 The Non-Obvious Extension Nobody Builds
**"SARAL for Indian language papers"** — currently SARAL converts papers *to* Indian languages, but most Indian researchers write in English. The gap is: papers written in Indian languages (conference proceedings, government reports, AYUSH medical research, agricultural extension reports) are *not readable* by the tool. Build an OCR + regional script understanding layer that lets SARAL process papers written in Telugu/Hindi/Bengali and convert *those* into multilingual video explainers.

Alternatively: **"SARAL Live"** — instead of processing a static PDF, take a live talk recording (Zoom meeting, conference talk video), transcribe it with Whisper, extract key contributions, and generate a SARAL-style explainer reel automatically. You'd be extending from papers → talks.

#### 📊 Judging Rubric Alignment
You're pitching to Prof. PK, who built this with a specific research agenda: democratizing scientific knowledge for non-expert audiences. The winning extension **directly serves someone who currently cannot access scientific knowledge** — a student in a rural school, a farmer who needs to understand a soil science paper, a policymaker who needs a 90-second brief on a complex study.

Don't build for researchers (they already use SARAL). Build for the downstream beneficiary.

#### 🎪 Hackathon Suitability
**6/10.** Good fit if you go in with a clear extension idea. Bad fit if you're deciding what to build in Hour 1 — codebase onboarding will eat your time.

---

## Track 6: OSDG — Collaborative Rich Text Editor in C

### The Exact Problem
> *Build a rich text editor in C. Requirements: multiple simultaneous editors, authorization, live cursors/highlights, conflict handling (locks), offline editing with merge conflict resolution. Recommended: executable code blocks, multimedia, AI completions, chat, version history.*

---

### Metric-by-Metric Breakdown

#### 🎯 Clarity of the Ask
**9/10 — Very clear.** The minimum requirements are extremely explicit. The recommended features are clearly marked as optional.

#### 🔧 Technical Difficulty
**10/10 — The hardest problem by a large margin.** Building a collaborative text editor with CRDTs (or OT) is a well-known hard problem in distributed systems. Companies like Figma, Notion, and Google have spent years on their real-time collaboration engines. Doing it in **C** (not C++, not Rust, not Go — C) adds substantial complexity:
- No standard library for WebSockets in C
- Memory management for a rich text buffer
- Implementing OT (Operational Transformation) or CRDT from scratch in C
- Network stack implementation in a language with no async primitives

Even the "minimum" requirements (offline editing + merge conflict resolution) would take a strong systems programmer 2–3 weeks to implement correctly.

#### 👥 Crowd Factor (How Many Teams Pick This)
**Low — maybe 3–5%.** Only CS students who have taken OS and systems courses will even attempt this. Most hackathon participants self-select out immediately.

#### 🏆 Win Probability for an Average Team
**1/10.** Unless your team has a dedicated systems programmer who has implemented OT or CRDTs before, this is an exercise in not finishing. The "C" constraint specifically rules out almost every shortcut.

#### 🟢 Your Specific Edge
**None.** Your background is in audio ML and full-stack web. You have no systems programming background that maps here.

#### 💡 Should You Pick This?
**No.** The only people who should pick OSDG are teams where at least two members have implemented lock-based concurrency, socket programming, and data structure serialization in C before. This is a "if you have to ask, the answer is no" problem.

#### 🎪 Hackathon Suitability
**2/10 for the average team.** Exceptionally well-suited for a 72-hour hackathon with experienced systems programmers. For a 24-hour hack with a mixed team, it's a trap.

---

## Synthesis: The Decision Matrix

| Track | Win Probability (You) | Crowd Competition | Prep Required | Spectacle Factor |
|-------|----------------------|-------------------|---------------|-----------------|
| Qualcomm | 🟡 Medium (with prep) | 🟡 Medium | 🔴 Very High | 🟢 Very High |
| Bhashini | 🟢 **High** | 🔴 Very High | 🟡 Medium | 🟢 High |
| Chubb PS1 | 🟢 **High** | 🔴 High | 🟡 Medium | 🟢 High |
| Chubb PS2 | 🔴 Low | 🔴 Extremely High | 🟢 Low | 🔴 Low |
| SARAL | 🟡 Medium | 🟢 Low | 🟡 Medium | 🟡 Medium |
| OSDG | 🔴 Very Low | 🟢 Very Low | 🔴 Very High | 🟡 Medium |

---

## What This Tells You About Megathon 2026

1. **Qualcomm is back** and they will almost certainly give another on-device AI problem. The 2025 problem was "generative art". 2026 will likely be something similarly constraint-heavy (NPU-only). **Prep the QNN SDK now — this is the only track where pre-event prep is the entire game.**

2. **Bhashini-style problems are evergreen.** Multilingual AI for India is a permanent government priority. Even if Bhashini isn't a direct sponsor in 2026, the domain is likely to appear (IndiaAI Mission, Lloyds/insurance may have language access requirements, etc.).

3. **The "safe" problem (Chubb PS2 / basic ML churn)** is always the most crowded and hardest to win. Avoid it unless you have a genuinely non-obvious angle ready in Hour 1.

4. **Chubb PS1 (multimodal fraud/claims)** is the sweet spot: well-defined enough to build quickly, technically interesting enough to differentiate, and directly maps to your deepfake detection intuitions (manipulation detection across modalities).

5. **OSDG-style CS fundamentals problems** (systems, concurrency) are unlikely to recur from the same sponsor, but IIIT Hyderabad's CS culture means *some* low-level CS problem may appear. Don't prep for it — just be honest about team skill sets at Hour 0.

---

## Your Priority Prep List (Based on This Analysis)

1. **🔴 Qualcomm Prep (Days 1–5):** Install QNN SDK, convert a simple model to ONNX, understand INT8 quantization. If Qualcomm asks something hardware-related, you can't fake this.

2. **🟢 Bhashini API familiarization (Days 6–8):** Get API keys, test ASR/TTS/MT/OCR, build the real-time S2S pipeline. This is your most likely winning track given your audio background.

3. **🟢 Vision + XAI for claims (Days 9–11):** Fine-tune EfficientNet on Kaggle car damage dataset. Implement Grad-CAM. Build the fraud detection pipeline (ELA analysis on CASIA2). This covers the Chubb PS1 angle with your deepfake detection intuitions.

4. **🟡 SARAL extension idea (Day 12):** Read the SARAL codebase for 2 hours. Decide on your extension angle before the hack. If SARAL returns, you walk in ready.
