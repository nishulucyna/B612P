package com.b612p.npubridge

import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.log10
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

/** One microphone recording, ready for the speech recogniser (16 kHz mono 16-bit WAV). */
class Recording(
    val wav: ByteArray,
    val speechDetected: Boolean,
    val snrDb: Double?,
    val seconds: Double,
    /** Loudest and room-noise level (int16 RMS) - tells you at a glance whether a microphone is connected. */
    val peakLevel: Double,
    val noiseLevel: Double,
)

/**
 * Records one utterance on the device and stops by itself after a pause. A port of the laptop recorder
 * (backend/audio_pipeline.py): the room noise is tracked continuously, speech needs two loud blocks in a row, and a pause is
 * "most of the last 1.8 s was quiet". The audio is trimmed to the speech and levelled before it goes to Whisper.
 */
class Recorder {
    @Volatile var stopRequested = false

    fun record(maxSeconds: Int = 15, onStatus: (String) -> Unit = {}): Recording {
        val sampleRate = 16000
        val block = sampleRate / 10                                   // 0.1 s
        val minBuffer = AudioRecord.getMinBufferSize(sampleRate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val bufferBytes = max(minBuffer, block * 2 * 4)

        // VOICE_RECOGNITION asks Android for the least processed signal (no AGC / noise suppression), like the laptop's raw path.
        var rec: AudioRecord? = null
        for (source in intArrayOf(MediaRecorder.AudioSource.VOICE_RECOGNITION, MediaRecorder.AudioSource.MIC)) {
            val candidate = AudioRecord(source, sampleRate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, bufferBytes)
            if (candidate.state == AudioRecord.STATE_INITIALIZED) { rec = candidate; break }
            candidate.release()
        }
        if (rec == null) throw IllegalStateException("The microphone could not be opened (is the RECORD_AUDIO permission granted?)")

        val blocks = ArrayList<ShortArray>()
        val levels = ArrayList<Double>()
        var speechBlocks = 0
        var loudBlocks = 0
        var firstSpeech = -1
        var lastLoud = -1
        var speechDetected = false
        val window = 18
        val recentQuiet = ArrayDeque<Boolean>()
        var threshold = 100.0
        var noiseFloor = 0.0
        stopRequested = false
        rec.startRecording()
        onStatus("Listening - speak now")
        try {
            while (!stopRequested && blocks.size * block < maxSeconds * sampleRate) {
                val buf = ShortArray(block)
                var got = 0
                while (got < block && !stopRequested) {
                    val n = rec.read(buf, got, block - got)
                    if (n <= 0) throw IllegalStateException("The microphone stopped delivering audio (read returned $n)")
                    got += n
                }
                if (got < block) break
                blocks.add(buf)
                val level = rms(buf)
                levels.add(level)
                if (levels.size < 5) continue
                noiseFloor = min(percentile(levels, 20.0), 1000.0)
                threshold = min(max(100.0, noiseFloor * 2.2), 3000.0)
                if (level >= threshold) {
                    speechBlocks++
                    loudBlocks++
                    lastLoud = blocks.size - 1
                    if (speechBlocks >= 2 && !speechDetected) { speechDetected = true; firstSpeech = blocks.size - 2 }
                } else {
                    speechBlocks = 0
                }
                if (speechDetected && loudBlocks >= 4) {
                    recentQuiet.addLast(level < max(threshold * 0.6, noiseFloor * 1.5))
                    if (recentQuiet.size > window) recentQuiet.removeFirst()
                    if (recentQuiet.size == window && recentQuiet.count { it } >= 0.85 * window) break
                }
            }
        } finally {
            rec.stop()
            rec.release()
        }

        var first = 0
        var last = blocks.size
        if (speechDetected && firstSpeech >= 0) {
            first = max(0, firstSpeech - 5)
            last = min(blocks.size, lastLoud + 1 + 7)
        }
        val kept = blocks.subList(first, max(first, last))
        val samples = ShortArray(kept.size * block)
        kept.forEachIndexed { i, b -> System.arraycopy(b, 0, samples, i * block, block) }

        var snr: Double? = null
        val speechLevels = levels.filter { it >= threshold }
        val noise = if (levels.isEmpty()) 0.0 else percentile(levels, 20.0)
        if (speechDetected && speechLevels.isNotEmpty() && noise > 0) {
            val speechRms = sqrt(speechLevels.sumOf { it * it } / speechLevels.size)
            snr = 20.0 * log10(max(speechRms, 1e-6) / max(noise, 1.0))
        }
        normalise(samples)
        return Recording(toWav(samples, sampleRate), speechDetected, snr, samples.size / sampleRate.toDouble(),
            levels.maxOrNull() ?: 0.0, noise)
    }

    private fun rms(a: ShortArray): Double {
        var sum = 0.0
        for (v in a) sum += v.toDouble() * v
        return sqrt(sum / a.size)
    }

    private fun percentile(values: List<Double>, p: Double): Double {
        val s = values.sorted()
        val pos = (s.size - 1) * p / 100.0
        val lo = pos.toInt()
        val hi = min(lo + 1, s.size - 1)
        return s[lo] + (s[hi] - s[lo]) * (pos - lo)
    }

    /** Bring quiet recordings to a consistent level without amplifying pure room noise (same rule as the laptop). */
    private fun normalise(samples: ShortArray) {
        if (samples.isEmpty()) return
        val sorted = samples.map { Math.abs(it.toInt()) }.sorted()
        val loud = sorted[((sorted.size - 1) * 0.995).toInt()].toDouble()
        if (loud < 50) return
        val gain = min(0.8 * 32767.0 / loud, 30.0)
        for (i in samples.indices) samples[i] = (samples[i] * gain).coerceIn(-32768.0, 32767.0).toInt().toShort()
    }

    private fun toWav(samples: ShortArray, rate: Int): ByteArray {
        val out = ByteArrayOutputStream()
        val h = ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN)
        h.put("RIFF".toByteArray()).putInt(36 + samples.size * 2).put("WAVE".toByteArray()).put("fmt ".toByteArray())
        h.putInt(16).putShort(1).putShort(1).putInt(rate).putInt(rate * 2).putShort(2).putShort(16)
        h.put("data".toByteArray()).putInt(samples.size * 2)
        out.write(h.array())
        val body = ByteBuffer.allocate(samples.size * 2).order(ByteOrder.LITTLE_ENDIAN)
        for (s in samples) body.putShort(s)
        out.write(body.array())
        return out.toByteArray()
    }
}
