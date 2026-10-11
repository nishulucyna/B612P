package com.b612p.npubridge

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.res.Configuration
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Path
import android.graphics.Shader
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.tts.TextToSpeech
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.view.inputmethod.InputMethodManager
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * The incident assistant, running entirely on this device: touch UI, speech recognition on the DSP, extraction on the NPU, the
 * mandatory-field gate, spoken replies and review/submit. Nothing here needs the laptop or a network.
 * Look and flow follow the reference UI bundle (incident-ui/): calm light theme (dark follows the system), one step at a time,
 * per-field Edit / Clear, severity chips, review then submit. The NPU strip at the top is a live hardware counter, not decoration.
 */
class MainActivity : Activity() {
    private val ui = Handler(Looper.getMainLooper())
    private val app = AppSession

    // ---- palette (light and dark, from the reference design tokens) -----------------------------------------------------------
    private class Palette(dark: Boolean) {
        val bg = if (dark) 0xFF0B1220.toInt() else 0xFFF8FAFC.toInt()
        val card = if (dark) 0xFF111B2E.toInt() else 0xFFFFFFFF.toInt()
        val border = if (dark) 0xFF26344A.toInt() else 0xFFE2E8F0.toInt()
        val text = if (dark) 0xFFE2E8F0.toInt() else 0xFF0F172A.toInt()
        val muted = if (dark) 0xFFA3B1C6.toInt() else 0xFF475569.toInt()
        val neutral = if (dark) 0xFF16202F.toInt() else 0xFFF1F5F9.toInt()
        val blue = if (dark) 0xFF38BDF8.toInt() else 0xFF0369A1.toInt()
        val onBlue = if (dark) 0xFF04283D.toInt() else 0xFFFFFFFF.toInt()
        val ok = if (dark) 0xFF4ADE80.toInt() else 0xFF15803D.toInt()
        val okSurface = if (dark) 0xFF10281B.toInt() else 0xFFECFDF3.toInt()
        val okBorder = if (dark) 0xFF1F5137.toInt() else 0xFF86D6A6.toInt()
        val warn = if (dark) 0xFFFBBF24.toInt() else 0xFFB45309.toInt()
        val warnSurface = if (dark) 0xFF2B2008.toInt() else 0xFFFFFBEB.toInt()
        val warnBorder = if (dark) 0xFF5C4410.toInt() else 0xFFF2C97D.toInt()
        val bad = if (dark) 0xFFFCA5A5.toInt() else 0xFFB91C1C.toInt()
        val badSurface = if (dark) 0xFF2C1113.toInt() else 0xFFFEF2F2.toInt()
        val badBorder = if (dark) 0xFF5E2225.toInt() else 0xFFF4A9A9.toInt()
        val rec = if (dark) 0xFFF87171.toInt() else 0xFFB91C1C.toInt()
    }

    private lateinit var c: Palette

    private val labels = mapOf(
        "incident_type" to "Incident type", "severity_level" to "Severity level", "incident_location" to "Incident location",
        "date_time" to "Date and time", "persons_involved" to "Persons involved", "equipment_asset_involved" to "Equipment or asset",
        "incident_description" to "Description", "immediate_actions_taken" to "Immediate actions taken",
        "witness_information" to "Witnesses", "recommended_follow_up_action" to "Recommended follow-up",
    )

    // ---- views that are updated in place ----------------------------------------------------------------------------------------
    private lateinit var statusChip: TextView
    private lateinit var spark: SparkView
    private lateinit var npuRate: TextView
    private lateinit var npuTemp: TextView
    private lateinit var npuNote: TextView
    private lateinit var pillStt: TextView
    private lateinit var pillLlm: TextView
    private lateinit var content: LinearLayout
    private lateinit var typeRow: LinearLayout
    private lateinit var input: EditText
    private lateinit var micBtn: FrameLayout
    private lateinit var micIcon: ImageView
    private lateinit var micCaption: TextView
    private lateinit var undoBtn: View
    private lateinit var newBtn: View
    private lateinit var voiceIcon: ImageView
    private lateinit var voiceCaption: TextView
    private lateinit var scroll: ScrollView

    private var lastSignature = ""
    private var tts: TextToSpeech? = null
    private var ttsReady = false
    private var voiceOn = true

    // ---- small view helpers -----------------------------------------------------------------------------------------------------
    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()
    private fun dpf(v: Float) = v * resources.displayMetrics.density

    private fun shape(fill: Int, stroke: Int = 0, radius: Int = 12, oval: Boolean = false) = GradientDrawable().apply {
        if (oval) shape = GradientDrawable.OVAL else cornerRadius = dpf(radius.toFloat())
        setColor(fill)
        if (stroke != 0) setStroke(dp(1), stroke)
    }

    private fun text(t: String, sp: Float, color: Int, bold: Boolean = false) = TextView(this).apply {
        text = t; textSize = sp; setTextColor(color); includeFontPadding = false
        if (bold) setTypeface(typeface, Typeface.BOLD)
        setLineSpacing(0f, 1.15f)
    }

    private fun lp(top: Int = 0, bottom: Int = 0, h: Int = ViewGroup.LayoutParams.WRAP_CONTENT) =
        LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, h).apply { setMargins(0, dp(top), 0, dp(bottom)) }

    private fun icon(res: Int, size: Int, tint: Int) = ImageView(this).apply {
        setImageResource(res); setColorFilter(tint); layoutParams = LinearLayout.LayoutParams(dp(size), dp(size))
    }

    private fun box(fill: Int, stroke: Int) = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL
        background = shape(fill, stroke, 14)
        setPadding(dp(14), dp(12), dp(14), dp(14))
    }

    private fun card(fill: Int, stroke: Int, vararg kids: View): LinearLayout = box(fill, stroke).apply { kids.forEach { addView(it) } }

    private fun row(vararg kids: View) = LinearLayout(this).apply {
        orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL
        kids.forEachIndexed { i, v ->
            addView(v)
            if (i < kids.size - 1) (v.layoutParams as? LinearLayout.LayoutParams)?.rightMargin = dp(8)
        }
    }

    private fun pill(label: String, iconRes: Int?, fg: Int, bg: Int, stroke: Int, onClick: () -> Unit) = LinearLayout(this).apply {
        orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL
        background = shape(bg, stroke, 10)
        setPadding(dp(12), 0, dp(14), 0); minimumHeight = dp(36)
        if (iconRes != null) addView(icon(iconRes, 16, fg).also { (it.layoutParams as LinearLayout.LayoutParams).rightMargin = dp(6) })
        addView(text(label, 13.5f, fg, bold = true))
        setOnClickListener { onClick() }
    }

    // ---- lifecycle ----------------------------------------------------------------------------------------------------------------
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        c = Palette((resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        window.statusBarColor = c.bg
        window.navigationBarColor = c.card
        window.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE)
        if (c.bg == 0xFFF8FAFC.toInt()) {
            window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR or View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR
        }
        buildViews()
        // Spoken replies use the phone's own offline text-to-speech engine; nothing leaves the device.
        tts = TextToSpeech(this) { status ->
            if (status == TextToSpeech.SUCCESS) {
                val r = tts?.setLanguage(Locale.US)
                ttsReady = r != null && r >= TextToSpeech.LANG_AVAILABLE
            }
            if (!ttsReady) app.lastAudioNote = "Spoken replies are unavailable (no offline voice engine). The text on screen still works."
            ui.post { updateVoiceButton() }
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
            ui.postDelayed(this, 500)
        }
    }

    override fun onResume() { super.onResume(); NpuMonitor.start(); ui.post(tick) }
    override fun onPause() { ui.removeCallbacks(tick); NpuMonitor.stop(); tts?.stop(); super.onPause() }
    override fun onDestroy() { tts?.shutdown(); super.onDestroy() }

    private fun say(text: String?) {
        if (text.isNullOrBlank() || !voiceOn || !ttsReady) return
        tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "reply")
    }

    private fun updateVoiceButton() {
        voiceIcon.setColorFilter(if (ttsReady && voiceOn) c.blue else c.muted)
        voiceIcon.alpha = if (ttsReady) 1f else 0.4f
        voiceCaption.text = when { !ttsReady -> "No voice"; voiceOn -> "Voice on"; else -> "Voice off" }
    }

    // ---- static layout: header, NPU strip, scrolling content, action dock -----------------------------------------------------------
    private fun buildViews() {
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(c.bg) }

        // header
        val header = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL; setPadding(dp(16), dp(14), dp(16), dp(6))
        }
        header.addView(icon(R.drawable.ic_shield, 22, c.blue))
        header.addView(text("Incident Assistant", 17f, c.text, bold = true).apply { setPadding(dp(8), 0, 0, 0) },
            LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        statusChip = text("", 12f, c.ok, bold = true).apply { setPadding(dp(10), dp(5), dp(10), dp(5)) }
        header.addView(statusChip)
        root.addView(header)

        // compact live NPU strip: real cDSP counter + NPU temperature, and which model is working right now
        val strip = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = shape(c.card, c.border, 14)
            setPadding(dp(12), dp(8), dp(12), dp(8))
        }
        val top = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        top.addView(icon(R.drawable.ic_chip, 20, c.blue))
        top.addView(text("NPU", 13f, c.text, bold = true).apply { setPadding(dp(6), 0, dp(10), 0) })
        spark = SparkView(this, c.blue, c.muted)
        top.addView(spark, LinearLayout.LayoutParams(0, dp(30), 1f))
        val nums = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.END; setPadding(dp(10), 0, 0, 0) }
        npuRate = text("0/s", 13f, c.text, bold = true).apply { gravity = Gravity.END }
        npuTemp = text("", 11f, c.muted).apply { gravity = Gravity.END }
        nums.addView(npuRate); nums.addView(npuTemp)
        top.addView(nums, LinearLayout.LayoutParams(dp(64), ViewGroup.LayoutParams.WRAP_CONTENT))
        strip.addView(top)
        val pills = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; setPadding(0, dp(6), 0, 0); gravity = Gravity.CENTER_VERTICAL }
        pillStt = text("", 11f, c.muted, bold = true).apply { setPadding(dp(8), dp(3), dp(8), dp(3)) }
        pillLlm = text("", 11f, c.muted, bold = true).apply { setPadding(dp(8), dp(3), dp(8), dp(3)) }
        npuNote = text("", 10.5f, c.muted).apply { gravity = Gravity.END }
        pills.addView(pillStt)
        pills.addView(pillLlm, LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply { leftMargin = dp(6) })
        pills.addView(npuNote, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        strip.addView(pills)
        root.addView(strip, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply {
            setMargins(dp(16), dp(4), dp(16), dp(6))
        })

        // scrolling content
        content = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(16), dp(6), dp(16), dp(20)) }
        scroll = ScrollView(this).apply { addView(content) }
        root.addView(scroll, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))

        // action dock
        val dock = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(c.card)
            setPadding(dp(12), dp(8), dp(12), dp(8))
        }
        typeRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL; visibility = View.GONE }
        input = EditText(this).apply {
            hint = "Type what happened"; setHintTextColor(c.muted); setTextColor(c.text); textSize = 16f
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE or InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
            minLines = 1; maxLines = 4
            background = shape(c.neutral, c.border, 12); setPadding(dp(12), dp(8), dp(12), dp(8))
        }
        typeRow.addView(input, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        val send = FrameLayout(this).apply {
            background = shape(c.blue, 0, 12); setOnClickListener { onSend() }
            addView(icon(R.drawable.ic_send, 22, c.onBlue), FrameLayout.LayoutParams(dp(22), dp(22), Gravity.CENTER))
        }
        typeRow.addView(send, LinearLayout.LayoutParams(dp(48), dp(48)).apply { leftMargin = dp(8) })
        dock.addView(typeRow, lp(bottom = 8))

        val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER }
        fun small(res: Int, cap: String, onClick: () -> Unit): Triple<View, ImageView, TextView> {
            val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER; setOnClickListener { onClick() } }
            val ic = icon(res, 22, c.muted)
            val cp = text(cap, 10.5f, c.muted).apply { gravity = Gravity.CENTER; setPadding(0, dp(3), 0, 0) }
            col.addView(ic); col.addView(cp)
            return Triple(col, ic, cp)
        }
        val typeBtn = small(R.drawable.ic_edit, "Type") {
            typeRow.visibility = if (typeRow.visibility == View.VISIBLE) View.GONE else View.VISIBLE
            if (typeRow.visibility == View.VISIBLE) {
                input.requestFocus()
                (getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager).showSoftInput(input, 0)
            }
        }
        val undo = small(R.drawable.ic_back, "Undo") { act("undo") { app.session.undo() } }
        val fresh = small(R.drawable.ic_plus, "New") { act("reset") { app.savedPath = null; app.edited.clear(); app.session.reset() } }
        val voice = small(R.drawable.ic_volume, "Voice") {
            if (ttsReady) { voiceOn = !voiceOn; if (!voiceOn) tts?.stop() }
            updateVoiceButton()
        }
        undoBtn = undo.first; newBtn = fresh.first; voiceIcon = voice.second; voiceCaption = voice.third

        micIcon = icon(R.drawable.ic_mic, 28, c.onBlue)
        micBtn = FrameLayout(this).apply {
            setOnClickListener { onSpeak() }
            addView(micIcon, FrameLayout.LayoutParams(dp(28), dp(28), Gravity.CENTER))
        }
        micCaption = text("Tap to speak", 10.5f, c.muted).apply { gravity = Gravity.CENTER; setPadding(0, dp(3), 0, 0) }
        val micCol = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER }
        micCol.addView(micBtn, LinearLayout.LayoutParams(dp(64), dp(64)))
        micCol.addView(micCaption)

        fun w() = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
        row.addView(typeBtn.first, w()); row.addView(undo.first, w())
        row.addView(micCol, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1.4f))
        row.addView(fresh.first, w()); row.addView(voice.first, w())
        dock.addView(row)
        root.addView(dock)
        updateVoiceButton()
        setContentView(root)
    }

    // ---- actions (always off the UI thread: the model call takes seconds) ----------------------------------------------------------
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
                    is NothingToUndoException -> "Nothing to undo yet."
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
        typeRow.visibility = View.GONE
        (getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager).hideSoftInputFromWindow(input.windowToken, 0)
        app.lastAudioNote = null
        app.voiceTurn = false
        act("text") { app.busyText = "Understanding on the NPU..."; app.session.textTurn(text) }
    }

    private fun onSpeak() {
        if (app.busy) {                           // tap again while listening = stop and process what was heard
            if (app.busyText.startsWith("Listening")) app.recorder.stopRequested = true
            return
        }
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), 7)
            return
        }
        app.lastAudioNote = null
        tts?.stop()                              // do not record our own voice
        app.voiceTurn = true
        act("speak") {
            app.busyText = "Listening - speak now (tap again to stop)"
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
            .setPositiveButton("Save") { _, _ -> setField(key, box.text.toString().trim()) }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun setField(key: String, value: String) {
        if (app.busy) return
        if (value.isBlank()) app.edited.remove(key) else app.edited.add(key)
        act("edit") { app.session.editFields(mapOf(key to value)) }
    }

    /** "Submit Report": write the finished report (the 10 contract fields) to this device. */
    private fun saveReport(state: IncidentState): String {
        val dir = File(getExternalFilesDir(null), "reports").apply { mkdirs() }
        val stamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
        val file = File(dir, "incident_${stamp}_${state.sessionId}.json")
        file.writeText(MiniJson.dumpsFlat(IncidentBrain.ALL_FIELDS.associateWith { state.fields[it] }))
        return file.absolutePath
    }

    // ---- drawing ------------------------------------------------------------------------------------------------------------------
    private enum class Phase { IDLE, LISTENING, PROCESSING, COLLECTING, REVIEW, SUBMITTED }

    private fun phase(state: IncidentState, hasChat: Boolean): Phase = when {
        app.busy && app.busyText.startsWith("Listening") -> Phase.LISTENING
        app.busy -> Phase.PROCESSING
        state.status == "submitted" -> Phase.SUBMITTED
        state.status == "complete" -> Phase.REVIEW
        hasChat || state.fields.values.any { !it.isNullOrBlank() } -> Phase.COLLECTING
        else -> Phase.IDLE
    }

    private fun refresh(force: Boolean) {
        val state = app.session.state()
        val chat = app.session.transcript()
        val ph = phase(state, chat.isNotEmpty())
        val engines = BridgeService.state()

        // header chip
        val chipText: String; val chipFg: Int; val chipBg: Int; val chipBorder: Int
        when (engines) {
            BridgeService.STATE_OK -> { chipText = "●  On device"; chipFg = c.ok; chipBg = c.okSurface; chipBorder = c.okBorder }
            BridgeService.STATE_ALERT -> { chipText = "○  CPU fallback"; chipFg = c.warn; chipBg = c.warnSurface; chipBorder = c.warnBorder }
            else -> { chipText = "○  Loading models"; chipFg = c.warn; chipBg = c.warnSurface; chipBorder = c.warnBorder }
        }
        statusChip.text = chipText
        statusChip.setTextColor(chipFg)
        statusChip.background = shape(chipBg, chipBorder, 99)

        // live NPU strip
        val sttActive = app.busy && app.busyText.startsWith("Transcribing")
        val llmActive = app.busy && app.busyText.startsWith("Understanding")
        fun style(p: TextView, name: String, on: Boolean) {
            p.text = (if (on) "● " else "○ ") + name
            p.setTextColor(if (on) c.onBlue else c.muted)
            p.background = shape(if (on) c.blue else c.neutral, if (on) 0 else c.border, 99)
        }
        style(pillStt, "Whisper · DSP", sttActive)
        style(pillLlm, "Gemma · NPU", llmActive)
        if (NpuMonitor.available) {
            spark.setData(NpuMonitor.snapshot())
            npuRate.text = "%.0f/s".format(NpuMonitor.rate)
            npuTemp.text = if (NpuMonitor.tempC > 0) "%.0f°C".format(NpuMonitor.tempC) else ""
            npuNote.text = "live cDSP counter"
        } else {
            spark.setData(FloatArray(NpuMonitor.SAMPLES))
            npuRate.text = if (sttActive || llmActive) "busy" else "idle"
            npuTemp.text = ""
            npuNote.text = "counter not readable"
        }

        // dock
        val listening = ph == Phase.LISTENING
        val working = app.busy && !listening
        micBtn.background = shape(when { working -> c.border; listening -> c.rec; else -> c.blue }, 0, 32, oval = true)
        micIcon.setImageResource(if (listening) R.drawable.ic_stop else R.drawable.ic_mic)
        micIcon.setColorFilter(when { working -> c.muted; listening -> Color.WHITE; else -> c.onBlue })
        micCaption.text = when { listening -> "Tap to stop"; working -> "Working on device"; else -> "Tap to speak" }
        micBtn.isEnabled = !working
        undoBtn.alpha = if (app.busy) 0.4f else 1f
        newBtn.alpha = if (app.busy) 0.4f else 1f

        val elapsed = if (app.busy) (System.currentTimeMillis() - app.busySinceMillis) / 1000 else 0
        val signature = "$ph|${state.sessionId}|${state.status}|${state.fields}|${chat.size}|${app.lastError}|${app.lastAudioNote}|" +
            "${app.busyText}|${app.edited}|${app.savedPath}|$elapsed|$engines"
        if (!force && signature == lastSignature) return
        lastSignature = signature
        renderContent(ph, state, chat)
    }

    private fun summaryLine(state: IncidentState): String {
        val f = state.fields
        val parts = listOfNotNull(f["incident_type"], f["incident_location"]?.let { "at $it" }, f["date_time"]?.let { "- $it" })
        return parts.joinToString(" ").ifBlank { "Incident" }
    }

    private fun renderContent(ph: Phase, state: IncidentState, chat: List<ChatMessage>) {
        val keepScroll = scroll.scrollY
        content.removeAllViews()
        val filledMandatory = IncidentBrain.MANDATORY_FIELDS.count { !state.fields[it].isNullOrBlank() }
        val filled = state.fields.values.count { !it.isNullOrBlank() }

        // title block
        val title: String; val sub: String
        when (ph) {
            Phase.IDLE -> { title = "Report an incident"; sub = "Describe the incident naturally. I'll complete the report for you." }
            Phase.LISTENING -> { title = "Listening"; sub = "Speak now. Tap the red button when you are done." }
            Phase.PROCESSING -> { title = "Processing on device"; sub = "Speech recognition and the language model are running on the Snapdragon NPU." }
            Phase.COLLECTING -> {
                title = "Still need details"
                sub = "Waiting on " + state.missing.joinToString(", ") { (labels[it] ?: it).lowercase() }.ifBlank { "more details" } + "."
            }
            Phase.REVIEW -> { title = "Ready for review"; sub = "All required details are captured. Check the form, then submit." }
            Phase.SUBMITTED -> { title = "Report submitted"; sub = "Kept on this device." }
        }
        content.addView(text(title, 24f, c.text, bold = true), lp(top = 4))
        content.addView(text(sub, 13.5f, c.muted), lp(top = 4, bottom = 12))

        app.lastError?.let { msg ->
            content.addView(card(c.badSurface, c.badBorder,
                row(icon(R.drawable.ic_error, 18, c.bad), text("Something went wrong", 14f, c.bad, bold = true)),
                text(msg, 13.5f, c.text).apply { setPadding(0, dp(6), 0, dp(8)) },
                pill("Dismiss", R.drawable.ic_close, c.bad, c.card, c.badBorder) { app.lastError = null; refresh(true) }), lp(bottom = 10))
        }
        app.lastAudioNote?.let { msg ->
            content.addView(card(c.warnSurface, c.warnBorder,
                row(icon(R.drawable.ic_alert, 18, c.warn), text("Heads up", 13.5f, c.warn, bold = true)),
                text(msg, 13f, c.text).apply { setPadding(0, dp(4), 0, 0) }), lp(bottom = 10))
        }
        if (BridgeService.state() == BridgeService.STATE_ALERT) {
            content.addView(card(c.warnSurface, c.warnBorder,
                row(icon(R.drawable.ic_warning, 18, c.warn), text("Not fully on the NPU", 13.5f, c.warn, bold = true)),
                text(BridgeService.banner(), 12.5f, c.text).apply { setPadding(0, dp(4), 0, 0) }), lp(bottom = 10))
        }

        when (ph) {
            Phase.LISTENING -> {
                val secs = (System.currentTimeMillis() - app.busySinceMillis) / 1000
                content.addView(card(c.badSurface, c.badBorder,
                    row(icon(R.drawable.ic_mic, 18, c.rec), text("Recording  %d:%02d".format(secs / 60, secs % 60), 16f, c.rec, bold = true)),
                    text("The phone microphone is listening. I stop by myself after a pause.", 13f, c.muted).apply { setPadding(0, dp(4), 0, 0) }),
                    lp(bottom = 10))
            }
            Phase.PROCESSING -> content.addView(processingCard(), lp(bottom = 10))
            Phase.IDLE -> content.addView(card(c.neutral, c.border,
                row(icon(R.drawable.ic_shield, 16, c.muted),
                    text("Speech, extraction and spoken replies all run on this phone. Nothing is sent to the internet.", 12.5f, c.muted))), lp(bottom = 10))
            Phase.SUBMITTED -> {
                val done = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER_HORIZONTAL; setPadding(0, dp(8), 0, dp(8)) }
                done.addView(icon(R.drawable.ic_check_circle, 56, c.ok))
                done.addView(text(summaryLine(state), 15f, c.text).apply { gravity = Gravity.CENTER; setPadding(0, dp(10), 0, 0) })
                app.savedPath?.let {
                    done.addView(text("Saved on this device:\n$it", 11.5f, c.muted).apply { gravity = Gravity.CENTER; setPadding(0, dp(6), 0, dp(10)) })
                }
                done.addView(pill("Create another report", R.drawable.ic_plus, c.blue, c.card, c.blue) {
                    act("reset") { app.savedPath = null; app.edited.clear(); app.session.reset() }
                })
                content.addView(done, lp(bottom = 10))
            }
            else -> {}
        }

        if (ph == Phase.COLLECTING || ph == Phase.REVIEW || (ph == Phase.PROCESSING && filled > 0)) {
            val prog = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
            prog.addView(text("$filledMandatory of 4 required fields complete", 12.5f, c.muted), LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
            prog.addView(text("$filledMandatory of 4", 13f, if (filledMandatory == 4) c.ok else c.blue, bold = true))
            content.addView(prog, lp(bottom = 6))
            content.addView(BarView(this, filledMandatory / 4f, if (filledMandatory == 4) c.ok else c.blue, c.border), lp(bottom = 12, h = dp(6)))
        }

        if (ph == Phase.COLLECTING && state.missing.isNotEmpty()) {
            content.addView(card(c.warnSurface, c.warnBorder,
                row(icon(R.drawable.ic_alert, 18, c.warn), text("Needed: " + (labels[state.missing[0]] ?: state.missing[0]), 14f, c.warn, bold = true)),
                text(state.nextPrompt ?: "", 14.5f, c.text).apply { setPadding(0, dp(6), 0, 0) }), lp(bottom = 10))
        }

        if (chat.isNotEmpty() && ph != Phase.SUBMITTED) {
            for (m in chat.takeLast(4)) {
                val mine = m.role == "user"
                val bubble = text(m.text, 14f, if (mine) c.onBlue else c.text).apply {
                    background = shape(if (mine) c.blue else c.card, if (mine) 0 else c.border, 14)
                    setPadding(dp(12), dp(8), dp(12), dp(8))
                }
                val params = LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply {
                    gravity = if (mine) Gravity.END else Gravity.START
                    setMargins(if (mine) dp(48) else 0, 0, if (mine) 0 else dp(48), dp(6))
                }
                content.addView(bubble, params)
            }
            content.addView(View(this), lp(h = dp(6)))
        }

        if (ph == Phase.REVIEW) {
            content.addView(card(c.okSurface, c.okBorder,
                text("Incident summary", 11.5f, c.ok, bold = true),
                text(summaryLine(state), 15.5f, c.text, bold = true).apply { setPadding(0, dp(4), 0, dp(4)) },
                text("$filled of 10 fields captured", 12f, c.muted)), lp(bottom = 12))
        }

        if (ph != Phase.IDLE && ph != Phase.SUBMITTED && !((ph == Phase.PROCESSING || ph == Phase.LISTENING) && filled == 0)) {
            for (key in IncidentBrain.ALL_FIELDS) content.addView(fieldCard(key, state.fields[key]), lp(bottom = 8))
            val canSubmit = state.status == "complete" && !app.busy
            val submit = text("Confirm and submit report", 15.5f, if (canSubmit) c.onBlue else c.muted, bold = true).apply {
                gravity = Gravity.CENTER
                background = shape(if (canSubmit) c.blue else c.border, 0, 14)
                minimumHeight = dp(52); setPadding(0, dp(15), 0, dp(15))
                setOnClickListener {
                    if (canSubmit) act("submit") {
                        val t = app.session.submit()
                        app.savedPath = saveReport(t.state)
                        t
                    }
                }
            }
            content.addView(submit, lp(top = 6, bottom = 4))
            if (!canSubmit && ph == Phase.COLLECTING) {
                content.addView(text("Submit unlocks when the four required fields are filled.", 12f, c.muted).apply { gravity = Gravity.CENTER }, lp(bottom = 4))
            }
        }
        scroll.post { scroll.scrollTo(0, keepScroll) }
    }

    private fun processingCard(): View {
        val stage = if (app.busyText.startsWith("Transcribing")) 0 else 1
        val steps = listOf("Speech recognition" to "Whisper-small on the Hexagon DSP", "Incident extraction" to "Language model on the NPU",
            "Form update" to "Checking the required fields")
        val b = box(c.card, c.border)
        b.addView(text("Every step below runs on this phone. Nothing is sent to the internet.", 12f, c.muted), lp(bottom = 8))
        steps.forEachIndexed { i, (name, cap) ->
            val st = if (i < stage) 2 else if (i == stage) 1 else 0
            val dot = FrameLayout(this).apply {
                background = shape(when (st) { 2 -> c.ok; 1 -> c.blue; else -> c.border }, 0, 99, oval = true)
                if (st == 2) addView(icon(R.drawable.ic_check, 14, Color.WHITE), FrameLayout.LayoutParams(dp(14), dp(14), Gravity.CENTER))
            }
            val txt = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                addView(text(name, 14f, if (st == 0) c.muted else c.text, bold = st == 1))
                val typedSkip = i == 0 && !app.voiceTurn
                addView(text(when { typedSkip -> "Not needed - you typed it"; st == 2 -> "Done"; st == 1 -> "Running - $cap"; else -> "Waiting" }, 12f,
                    if (st == 1) c.blue else c.muted).apply { setPadding(0, dp(1), 0, 0) })
            }
            val r = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
            r.addView(dot, LinearLayout.LayoutParams(dp(22), dp(22)).apply { rightMargin = dp(12) })
            r.addView(txt)
            b.addView(r, lp(top = 4, bottom = 4))
        }
        val secs = (System.currentTimeMillis() - app.busySinceMillis) / 1000
        b.addView(text("${secs}s", 12f, c.muted).apply { gravity = Gravity.END }, lp(top = 4))
        return b
    }

    private fun fieldCard(key: String, value: String?): View {
        val submitted = app.session.state().status == "submitted"
        val required = key in IncidentBrain.MANDATORY_FIELDS
        val has = !value.isNullOrBlank()
        val card = box(if (has) c.okSurface else if (required) c.warnSurface else c.card, if (has) c.okBorder else if (required) c.warnBorder else c.border)
        val head = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        head.addView(text(labels[key] ?: key, 14f, c.text, bold = true), LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        head.addView(text(if (required) "Required" else "Optional", 10.5f, if (required) c.warn else c.muted, bold = true).apply {
            background = shape(if (required) c.warnSurface else c.neutral, if (required) c.warnBorder else c.border, 99)
            setPadding(dp(8), dp(2), dp(8), dp(2))
        })
        card.addView(head)
        card.addView(text(if (has) value!! else "Not captured yet", 15f, if (has) c.text else c.muted).apply { setPadding(0, dp(6), 0, dp(4)) })
        if (has) {
            val edited = key in app.edited
            card.addView(row(icon(R.drawable.ic_check_circle, 13, if (edited) c.blue else c.ok),
                text(if (edited) "Edited by you" else "Captured on device", 11.5f, if (edited) c.blue else c.ok)))
        }
        if (key == "severity_level" && !submitted) {
            val chips = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; setPadding(0, dp(8), 0, 0) }
            for (lvl in IncidentBrain.SEVERITIES) {
                val on = value.equals(lvl, ignoreCase = true)
                chips.addView(text(lvl, 13f, if (on) c.onBlue else c.text, bold = on).apply {
                    gravity = Gravity.CENTER
                    background = shape(if (on) c.blue else c.card, if (on) 0 else c.border, 99)
                    setPadding(dp(4), dp(8), dp(4), dp(8))
                    setOnClickListener { setField(key, lvl) }
                }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f).apply { rightMargin = dp(6) })
            }
            card.addView(chips)
        }
        if (!submitted) {
            val actions = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; setPadding(0, dp(8), 0, 0) }
            actions.addView(pill(if (has) "Edit" else "Add", R.drawable.ic_edit, c.blue, c.card, c.blue) { editField(key, value ?: "") })
            if (has) {
                val clear = pill("Clear", R.drawable.ic_clear, c.bad, c.card, c.badBorder) { setField(key, "") }
                actions.addView(clear, LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply { leftMargin = dp(8) })
            }
            card.addView(actions)
        }
        return card
    }

    // ---- tiny custom views ------------------------------------------------------------------------------------------------------
    /** Sparkline of the NPU interrupt rate. */
    private class SparkView(context: Context, private val color: Int, private val faint: Int) : View(context) {
        private var data = FloatArray(NpuMonitor.SAMPLES)
        private val dens = resources.displayMetrics.density
        private val line = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            style = Paint.Style.STROKE; strokeWidth = 2.5f * dens; strokeCap = Paint.Cap.ROUND; strokeJoin = Paint.Join.ROUND
        }
        private val fill = Paint(Paint.ANTI_ALIAS_FLAG)
        private val base = Paint().apply { strokeWidth = dens }

        fun setData(d: FloatArray) { data = d; invalidate() }

        override fun onDraw(canvas: Canvas) {
            val w = width.toFloat(); val h = height.toFloat()
            if (w <= 0f || data.size < 2) return
            val pad = 3f * dens
            val mx = maxOf(20f, data.maxOrNull() ?: 0f)
            base.color = (faint and 0x00FFFFFF) or 0x40000000
            canvas.drawLine(0f, h - pad, w, h - pad, base)
            val path = Path(); val area = Path()
            data.forEachIndexed { i, v ->
                val x = w * i / (data.size - 1)
                val y = h - pad - (h - 2 * pad) * (v / mx).coerceIn(0f, 1f)
                if (i == 0) { path.moveTo(x, y); area.moveTo(x, h); area.lineTo(x, y) } else { path.lineTo(x, y); area.lineTo(x, y) }
            }
            area.lineTo(w, h); area.close()
            fill.shader = LinearGradient(0f, 0f, 0f, h, (color and 0x00FFFFFF) or 0x55000000, (color and 0x00FFFFFF) or 0x00000000, Shader.TileMode.CLAMP)
            canvas.drawPath(area, fill)
            line.color = color
            canvas.drawPath(path, line)
        }
    }

    private class BarView(context: Context, private val frac: Float, private val color: Int, private val track: Int) : View(context) {
        private val p = Paint(Paint.ANTI_ALIAS_FLAG)
        override fun onDraw(canvas: Canvas) {
            val r = height / 2f
            p.color = track; canvas.drawRoundRect(0f, 0f, width.toFloat(), height.toFloat(), r, r, p)
            p.color = color; canvas.drawRoundRect(0f, 0f, width * frac.coerceIn(0f, 1f), height.toFloat(), r, r, p)
        }
    }
}
