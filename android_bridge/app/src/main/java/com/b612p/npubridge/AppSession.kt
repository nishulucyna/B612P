package com.b612p.npubridge

import java.util.concurrent.Executors

/**
 * Process-wide objects of the on-device app: the incident being reported and a single background thread for the slow
 * work (recording, Whisper, the LLM). They outlive the activity, so rotating the screen or reopening the app keeps the report.
 */
object AppSession {
    /** The language model on the NPU; throws until it has finished loading. */
    private fun llmCall(prompt: String): String {
        val llm = BridgeService.llmEngine() ?: throw IllegalStateException("The AI engines are still starting.")
        if (!llm.isReady) throw IllegalStateException(llm.status())
        return llm.generate(prompt)
    }

    val session = IncidentSession { prompt -> llmCall(prompt) }
    val worker = Executors.newSingleThreadExecutor { r -> Thread(r, "incident-worker") }
    val recorder = Recorder()

    @Volatile var busy = false
    @Volatile var busyText = ""
    @Volatile var busySinceMillis = 0L
    @Volatile var lastError: String? = null
    @Volatile var lastAudioNote: String? = null

    /** Speech recognition on the NPU for a recorded WAV. */
    fun transcribe(wav: ByteArray): String {
        val stt = BridgeService.sttEngine() ?: throw IllegalStateException("The AI engines are still starting.")
        if (!stt.isReady) throw IllegalStateException(stt.status())
        return stt.transcribe(wav).trim()
    }
}
