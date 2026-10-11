package com.b612p.npubridge

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.speech.tts.TextToSpeech
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import android.view.inputmethod.InputMethodManager
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView

/**
 * The incident assistant, running entirely on this device: touch UI, speech recognition and the language model on the
 * NPU, and the report logic. Nothing here needs the laptop or a network (the HTTP bridge for the laptop UI keeps running
 * in BridgeService, but this screen does not use it).
 */
class MainActivity : Activity() {
    private val ui = Handler(Looper.getMainLooper())
    private val app = AppSession

    private val cBg = Color.parseColor("#060d1c")
    private val cCard = Color.parseColor("#0f1a30")
    private val cLine = Color.parseColor("#1e3a5f")
    private val cText = Color.parseColor("#e5edf9")
    private val cMuted = Color.parseColor("#8da2c8")
    private val cBlue = Color.parseColor("#3b82f6")
    private val cGreen = Color.parseColor("#22c55e")
    private val cAmber = Color.parseColor("#f59e0b")
    private val cRed = Color.parseColor("#ef4444")

    private val labels = mapOf(
        "incident_type" to "Incident type", "severity_level" to "Severity", "incident_location" to "Location",
        "date_time" to "Date & time", "persons_involved" to "Persons involved", "equipment_asset_involved" to "Equipment / asset",
        "incident_description" to "Description", "immediate_actions_taken" to "Immediate actions taken",
        "witness_information" to "Witnesses", "recommended_follow_up_action" to "Recommended follow-up",
    )

    private lateinit var chip: TextView
    private lateinit var busyLine: TextView
    private lateinit var input: EditText
    private lateinit var dynamic: LinearLayout
    private lateinit var speakBtn: Button
    private lateinit var undoBtn: Button
    private lateinit var resetBtn: Button
    private lateinit var sendBtn: Button
    private var lastSignature = ""
    private lateinit var voiceBtn: Button
    private var tts: TextToSpeech? = null
    private var ttsReady = false
    private var voiceOn = true

    // ---- small view helpers ------------------------------------------------------------
    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    private fun rounded(fill: Int, stroke: Int = Color.TRANSPARENT, radius: Int = 12, strokeDp: Int = 1) =
        GradientDrawable().apply {
            setColor(fill); cornerRadius = dp(radius).toFloat(); if (stroke != Color.TRANSPARENT) setStroke(dp(strokeDp), stroke)
        }

    private fun label(t: String, sp: Float, color: Int = cText, bold: Boolean = false) = TextView(this).apply {
        text = t; textSize = sp; setTextColor(color); if (bold) setTypeface(typeface, Typeface.BOLD)
    }

    private fun params(top: Int = 0, bottom: Int = 0) =
        LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply {
            setMargins(0, dp(top), 0, dp(bottom))
        }

    private fun button(t: String, primary: Boolean, onClick: () -> Unit) = Button(this).apply {
        text = t; isAllCaps = false; textSize = 16f; setTextColor(if (primary) Color.WHITE else cText)
        background = rounded(if (primary) cBlue else Color.parseColor("#1e293b"), if (primary) cBlue else Color.parseColor("#475569"))
        minHeight = dp(52); setOnClickListener { onClick() }
    }

    private fun card(vararg children: View, stroke: Int = cLine, fill: Int = cCard) = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL
        background = rounded(fill, stroke)
        setPadding(dp(14), dp(10), dp(14), dp(12))
        children.forEach { addView(it) }
    }

    // ---- lifecycle -------------------------------------------------------------------------
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        window.statusBarColor = cBg
        window.navigationBarColor = cBg
        buildStaticViews()
        // Spoken replies use the phone's own offline text-to-speech engine; nothing leaves the device.
        tts = TextToSpeech(this) { status ->
            if (status == TextToSpeech.SUCCESS) {
                val r = tts?.setLanguage(Locale.US)
                ttsReady = r != null && r >= TextToSpeech.LANG_AVAILABLE
            }
            if (!ttsReady) app.lastAudioNote = "Spoken replies are unavailable (no offline text-to-speech engine). The text on screen still works."
            ui.post { voiceBtn.text = voiceLabel() }
        }
        // starts the AI engines (and the optional laptop bridge); safe to call again
        startService(Intent(this, BridgeService::class.java)
            .putExtra(BridgeService.EXTRA_ALLOW_CPU_FALLBACK, intent.getBooleanExtra(BridgeService.EXTRA_ALLOW_CPU_FALLBACK, false))
            .putExtra("llm_unit", intent.getStringExtra("llm_unit"))        // dev benchmark switches, see scripts/npu_proof.py
            .putExtra("llm_file", intent.getStringExtra("llm_file"))
            .putExtra("llm_threads", intent.getIntExtra("llm_threads", GenieEngine.DEFAULT_THREADS)))
    }

    private val tick = object : Runnable {
        override fun run() {
            refresh(force = false)
            ui.postDelayed(this, 1000)
        }
    }

    override fun onResume() { super.onResume(); ui.post(tick) }
    override fun onPause() { ui.removeCallbacks(tick); tts?.stop(); super.onPause() }
    override fun onDestroy() { tts?.shutdown(); super.onDestroy() }

    private fun voiceLabel() = when {
        !ttsReady -> "Voice: unavailable"
        voiceOn -> "Voice: on"
        else -> "Voice: off"
    }

    private fun say(text: String?) {
        if (text.isNullOrBlank() || !voiceOn || !ttsReady) return
        tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "reply")
    }

    private fun buildStaticViews() {
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(14), dp(16), dp(14), dp(40)) }

        root.addView(label("AI Incident Report Assistant", 22f, bold = true))
        root.addView(label("Runs on this device: Whisper on the DSP, the language model on the NPU. No cloud, no laptop.", 12.5f, cMuted),
            params(top = 2, bottom = 10))

        chip = label("", 13f, Color.WHITE).apply { setPadding(dp(12), dp(9), dp(12), dp(9)) }
        root.addView(chip, params(bottom = 10))

        speakBtn = button("Speak", true) { onSpeak() }
        undoBtn = button("Undo", false) { act("undo") { app.session.undo() } }
        resetBtn = button("Reset", false) { act("reset") { app.savedPath = null; app.session.reset() } }
        val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        row.addView(speakBtn, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 2f).apply { rightMargin = dp(8) })
        row.addView(undoBtn, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f).apply { rightMargin = dp(8) })
        row.addView(resetBtn, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        root.addView(row, params(bottom = 8))
        voiceBtn = button("Voice: ...", false) {
            if (ttsReady) { voiceOn = !voiceOn; if (!voiceOn) tts?.stop() }
            voiceBtn.text = voiceLabel()
        }
        voiceBtn.minHeight = dp(40)
        root.addView(voiceBtn, params(bottom = 8))

        busyLine = label("", 14f, cAmber, bold = true)
        root.addView(busyLine, params(bottom = 6))

        input = EditText(this).apply {
            hint = "Or type what happened..."; setHintTextColor(cMuted); setTextColor(cText); textSize = 16f
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE or InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
            minLines = 2; gravity = Gravity.TOP
            background = rounded(cCard, cLine); setPadding(dp(12), dp(10), dp(12), dp(10))
        }
        root.addView(input, params(bottom = 6))
        sendBtn = button("Send", true) { onSend() }
        root.addView(sendBtn, params(bottom = 12))

        dynamic = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        root.addView(dynamic)

        root.isFocusableInTouchMode = true
        setContentView(ScrollView(this).apply {
            setBackgroundColor(cBg); isFillViewport = true
            descendantFocusability = android.view.ViewGroup.FOCUS_BEFORE_DESCENDANTS
            addView(root)
        })
        root.requestFocus()
    }

    // ---- actions (always off the UI thread: the model call takes seconds) ---------------------------
    private fun act(name: String, work: () -> Turn?) {
        if (app.busy) return
        app.busy = true; app.busyText = "Working..."; app.busySinceMillis = System.currentTimeMillis(); app.lastError = null
        refresh(force = true)
        app.worker.execute {
            try {
                val turn = work()
                if (turn != null) {
                    val line = if (turn.state.status == "submitted") "The incident report has been submitted." else turn.speech
                    ui.post { say(line) }
                }
            } catch (e: Exception) {
                app.lastError = when (e) {
                    is NothingToUndoException -> "Nothing to undo."
                    is NotReadyToSubmitException -> "Cannot submit yet. Still missing: " + e.missing.joinToString(", ") { labels[it] ?: it }
                    else -> e.message ?: e.toString()
                }
            } finally {
                app.busy = false
                ui.post { refresh(force = true) }
            }
        }
    }

    private fun onSend() {
        val text = input.text.toString().trim()
        if (text.isEmpty()) return
        input.setText("")
        (getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager).hideSoftInputFromWindow(input.windowToken, 0)
        app.lastAudioNote = null
        act("text") { app.busyText = "Understanding on the NPU..."; app.session.textTurn(text) }
    }

    private fun onSpeak() {
        if (app.busy) {                           // second tap while listening = stop and process what was heard
            app.recorder.stopRequested = true
            return
        }
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), 7)
            return
        }
        app.lastAudioNote = null
        tts?.stop()                              // do not record our own voice
        act("speak") {
            app.busyText = "Listening - speak now (tap Speak again to stop)"
            val rec = app.recorder.record()
            val note = "Microphone: loudest %.0f, room noise %.0f".format(rec.peakLevel, rec.noiseLevel)
            if (!rec.speechDetected) {
                app.lastAudioNote = "No clear speech heard. $note. If both are near zero no microphone is connected: plug in a headset."
                return@act app.session.nothingHeard()
            }
            app.busyText = "Transcribing on the NPU..."
            val text = app.transcribe(rec.wav)
            val snr = rec.snrDb
            app.lastAudioNote = if (snr != null && snr < 12)
                "The recording was noisy or faint (about %.0f dB signal-to-noise). If the text looks wrong, tap Undo, move closer and try again.".format(snr)
            else null
            if (text.isBlank()) return@act app.session.nothingHeard()
            app.busyText = "Understanding on the NPU..."
            app.session.textTurn(text)
        }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 7 && grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED) onSpeak()
        else app.lastError = "Microphone permission was denied, so Speak cannot work. Type the report instead."
        refresh(force = true)
    }

    /** Review step: correct or fill a field by hand. Goes through the same mandatory-field gate as a spoken turn. */
    private fun editField(key: String, current: String) {
        if (app.busy) return
        val box = EditText(this).apply {
            setText(current); setSelection(current.length); inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE
            setPadding(dp(16), dp(12), dp(16), dp(12))
        }
        AlertDialog.Builder(this)
            .setTitle(labels[key] ?: key)
            .setView(box)
            .setPositiveButton("Save") { _, _ -> act("edit") { app.session.editFields(mapOf(key to box.text.toString().trim())) } }
            .setNegativeButton("Cancel", null)
            .show()
    }

    /** "Submit Report": write the finished report (the 10 contract fields) to this device. */
    private fun saveReport(state: IncidentState): String {
        val dir = File(getExternalFilesDir(null), "reports").apply { mkdirs() }
        val stamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
        val file = File(dir, "incident_${stamp}_${state.sessionId}.json")
        file.writeText(MiniJson.dumpsFlat(IncidentBrain.ALL_FIELDS.associateWith { state.fields[it] }))
        return file.absolutePath
    }

    // ---- drawing ------------------------------------------------------------------------------------
    private fun refresh(force: Boolean) {
        val state = app.session.state()
        val chat = app.session.transcript()
        val engines = BridgeService.state()
        chip.text = BridgeService.banner()
        chip.background = rounded(when (engines) {
            BridgeService.STATE_ALERT -> Color.parseColor("#7f1d1d")
            BridgeService.STATE_OK -> Color.parseColor("#14532d")
            else -> Color.parseColor("#7c4a03")
        })
        val elapsed = if (app.busy) (System.currentTimeMillis() - app.busySinceMillis) / 1000 else 0
        busyLine.text = if (app.busy) "${app.busyText}  (${elapsed}s)" else ""
        busyLine.visibility = if (app.busy) View.VISIBLE else View.GONE
        val idle = !app.busy
        undoBtn.isEnabled = idle; resetBtn.isEnabled = idle; sendBtn.isEnabled = idle
        speakBtn.text = if (app.busy && app.busyText.startsWith("Listening")) "Stop" else "Speak"
        speakBtn.isEnabled = idle || app.busyText.startsWith("Listening")

        val signature = "${state.sessionId}|${state.status}|${state.fields}|${chat.size}|${app.lastError}|${app.lastAudioNote}|${app.busy}"
        if (!force && signature == lastSignature) return
        lastSignature = signature
        renderDynamic(state, chat)
    }

    private fun renderDynamic(state: IncidentState, chat: List<ChatMessage>) {
        dynamic.removeAllViews()

        app.lastError?.let {
            dynamic.addView(card(label(it, 14f, Color.WHITE), stroke = cRed, fill = Color.parseColor("#450a0a")), params(bottom = 8))
        }
        app.lastAudioNote?.let {
            dynamic.addView(card(label(it, 13f, Color.parseColor("#fde68a")), stroke = cAmber, fill = Color.parseColor("#3a2a05")), params(bottom = 8))
        }

        val head: String; val body: String; val accent: Int
        when (state.status) {
            "submitted" -> { head = "SUBMITTED"; body = "The incident report was submitted" + (app.savedPath?.let { " and saved on this device:\n$it" } ?: "") + ".\nTap Reset to start a new one."; accent = cGreen }
            "complete" -> { head = "REPORT READY - REVIEW AND SUBMIT"; body = state.toolCall?.summaryForTts ?: ""; accent = cGreen }
            else -> { head = "ASSISTANT - NEXT QUESTION"; body = state.nextPrompt ?: ""; accent = cBlue }
        }
        dynamic.addView(card(label(head, 11f, accent, bold = true), label(body, 16f), stroke = accent), params(bottom = 10))

        if (chat.isNotEmpty()) {
            dynamic.addView(label("Conversation", 13f, cMuted, bold = true), params(bottom = 4))
            for (m in chat.takeLast(6)) {
                val mine = m.role == "user"
                val bubble = label(m.text, 14.5f).apply {
                    background = rounded(if (mine) Color.parseColor("#1d4ed8") else cCard, if (mine) Color.TRANSPARENT else cLine)
                    setPadding(dp(12), dp(8), dp(12), dp(8))
                }
                val lp = LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply {
                    gravity = if (mine) Gravity.END else Gravity.START
                    setMargins(if (mine) dp(40) else 0, 0, if (mine) 0 else dp(40), dp(6))
                }
                dynamic.addView(bubble, lp)
            }
        }

        val filled = state.fields.values.count { !it.isNullOrBlank() }
        val mandatoryMet = IncidentBrain.MANDATORY_FIELDS.count { !state.fields[it].isNullOrBlank() }
        dynamic.addView(label("Incident report  -  $filled/10 fields, $mandatoryMet/4 required", 13f, cMuted, bold = true), params(top = 8, bottom = 0))
        if (state.status != "submitted") dynamic.addView(label("Tap any field to correct it.", 12f, cMuted), params(bottom = 4))
        for (key in IncidentBrain.ALL_FIELDS) {
            val v = state.fields[key]
            val required = key in IncidentBrain.MANDATORY_FIELDS
            val color = when {
                !v.isNullOrBlank() -> cGreen
                required -> cAmber
                else -> cLine
            }
            val title = (labels[key] ?: key).uppercase() + if (required) "   REQUIRED" else ""
            val fieldCard = card(label(title, 10.5f, if (!v.isNullOrBlank()) cGreen else if (required) cAmber else cMuted, bold = true),
                label(if (v.isNullOrBlank()) "- awaiting voice input -" else v, if (v.isNullOrBlank()) 14f else 16f,
                    if (v.isNullOrBlank()) cMuted else cText),
                stroke = color, fill = if (!v.isNullOrBlank()) Color.parseColor("#0b2418") else cCard)
            if (state.status != "submitted") fieldCard.setOnClickListener { editField(key, v ?: "") }      // review: tap to correct
            dynamic.addView(fieldCard, params(bottom = 6))
        }

        val submit = button(if (state.status == "submitted") "Submitted" else "Confirm & submit report", state.status == "complete") {
            act("submit") {
                val t = app.session.submit()
                app.savedPath = saveReport(t.state)
                t
            }
        }.apply { isEnabled = state.status == "complete" }
        dynamic.addView(submit, params(top = 8, bottom = 4))
        dynamic.addView(label("Everything above ran on this device. No network was used.", 11.5f, cMuted), params(top = 6))
    }
}
