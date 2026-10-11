package com.b612p.npubridge

import android.os.SystemClock
import java.io.File

/**
 * Live NPU activity for the UI, read from the phone itself (no network, nothing simulated):
 *  - the interrupt counter of the CPU<->cDSP message channel (`glink-native-cdsp` in /proc/interrupts). It only moves while the
 *    Hexagon NPU/DSP is being given work (the audio DSP has its own counter);
 *  - the temperature of the NPU's matrix/vector units (thermal zones named nsp*).
 * If the kernel does not let the app read these (some builds restrict /proc), [available] stays false and the UI says so.
 */
object NpuMonitor {
    const val SAMPLES = 48

    @Volatile var available = false
        private set
    @Volatile var rate = 0f          // cDSP interrupts per second
        private set
    @Volatile var tempC = 0f
        private set

    private val history = FloatArray(SAMPLES)
    private var thread: Thread? = null
    @Volatile private var running = false
    private var tempFiles: List<File> = emptyList()

    /** Newest sample last. */
    @Synchronized fun snapshot(): FloatArray = history.copyOf()

    @Synchronized private fun push(v: Float) {
        System.arraycopy(history, 1, history, 0, SAMPLES - 1)
        history[SAMPLES - 1] = v
    }

    @Synchronized fun start() {
        if (running) return
        running = true
        tempFiles = (File("/sys/class/thermal").listFiles { f -> f.name.startsWith("thermal_zone") } ?: emptyArray())
            .filter { z -> runCatching { File(z, "type").readText().trim().startsWith("nsp") }.getOrDefault(false) }
            .map { File(it, "temp") }
        thread = Thread({
            var last = readIrq()
            var lastT = SystemClock.elapsedRealtime()
            while (running) {
                try { Thread.sleep(400) } catch (_: InterruptedException) { break }
                val now = readIrq()
                val t = SystemClock.elapsedRealtime()
                if (now != null && last != null && t > lastT) {
                    available = true
                    rate = ((now - last).coerceAtLeast(0)) * 1000f / (t - lastT)
                    push(rate)
                } else if (now == null) {
                    available = false
                }
                last = now
                lastT = t
                tempC = tempFiles.maxOfOrNull { runCatching { it.readText().trim().toFloat() / 1000f }.getOrDefault(0f) } ?: 0f
            }
        }, "npu-monitor").apply { isDaemon = true; start() }
    }

    @Synchronized fun stop() {
        running = false
        thread?.interrupt()
        thread = null
    }

    /** Sum over all CPUs of the cDSP glink interrupt counter, or null if unreadable. */
    private fun readIrq(): Long? = try {
        File("/proc/interrupts").useLines { lines ->
            lines.firstOrNull { it.contains("glink-native-cdsp") }?.trim()?.split(Regex("\\s+"))
                ?.drop(1)?.takeWhile { it.all(Char::isDigit) }?.sumOf { it.toLong() }
        }
    } catch (_: Exception) {
        null
    }
}
