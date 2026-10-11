package com.b612p.npubridge

import android.content.Context
import android.util.Log
import com.geniex.sdk.GenieXSdk
import com.geniex.sdk.LlmWrapper
import com.geniex.sdk.bean.ChatMessage
import com.geniex.sdk.bean.ComputeUnitValue
import com.geniex.sdk.bean.GenerationConfig
import com.geniex.sdk.bean.LlmCreateInput
import com.geniex.sdk.bean.LlmStreamResult
import com.geniex.sdk.bean.ModelConfig
import com.geniex.sdk.bean.ProfilingData
import com.geniex.sdk.bean.RuntimeIdValue
import com.geniex.sdk.bean.SamplerConfig
import kotlinx.coroutines.runBlocking
import java.io.File
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * LLM on the Hexagon NPU through GenieX (llama.cpp runtime, Q4_0 GGUF).
 *
 * The model is a local .gguf pushed with adb, e.g.
 *   adb push model.gguf /data/local/tmp/npu_models/llm/model.gguf
 * (any *.gguf in that folder works; model.gguf is preferred if several are present).
 * Nothing is downloaded: the model is opened by path.
 *
 * GenieX has no API that says which processor ran the model, and asking for the NPU does not
 * guarantee it: the runtime silently keeps weights it cannot place on the Hexagon device in CPU
 * buffers. So after loading we read GenieX's own placement log (this process, via logcat) and
 * only report onNpu when the weights really went to HTP0. By default a model that mostly stays
 * on the CPU is refused (not ready). [allowCpuFallback] is a dev-only switch that still serves
 * it, flagged.
 */
class GenieEngine @JvmOverloads constructor(
    private val context: Context,
    private val allowCpuFallback: Boolean = false,
    private val modelDir: File = File(ModelLoader.DEFAULT_ROOT, "llm"),
    /** Dev only, for the NPU-vs-CPU benchmark (scripts/npu_proof.py). Always NPU in the real app. */
    private val computeUnit: ComputeUnitValue = ComputeUnitValue.NPU,
    /** Dev only: pick a specific .gguf in the model folder (model comparison). Null = model.gguf, else the first .gguf. */
    private val modelFile: String? = null,
    /** CPU threads for the parts of the model that run on the CPU (0 = SDK default of 8, pinned and busy-polling). */
    private val threads: Int = 0,
) : LlmEngine {

    @Volatile private var llm: LlmWrapper? = null

    // The UI polls the state above many times a second. Only generation and model switching take this lock.
    private val lock = Any()

    /** Model file in use. Starts as the constructor's choice (default: Gemma, model.gguf) and changes only through [switchModel]. */
    @Volatile private var activeFile: String? = modelFile

    /** Quick mode = the smaller Qwen model plus [IncidentGuard]. Off at every launch: the app always starts on the accurate model. */
    @Volatile private var quickMode = false
    @Volatile private var ready = false
    @Volatile private var onNpu = false
    @Volatile private var warning: String? = null
    @Volatile private var status = "llm: not loaded yet"

    /** Loads the SDK and the model, checks where it was placed, then runs a short warm-up. Slow; call off the main thread. */
    fun load() {
        status = "llm: loading..."
        try {
            val gguf = findModel()
                ?: throw IllegalStateException("no .gguf model in ${modelDir.path} - adb push one there")
            Log.i(TAG, "LLM model file: ${gguf.absolutePath} (${gguf.length() / (1024 * 1024)} MB)")

            initSdk()

            val input = LlmCreateInput(
                model_name = gguf.nameWithoutExtension,
                model_path = gguf.absolutePath,
                config = if (threads > 0) ModelConfig(nCtx = N_CTX, nThreads = threads, nThreadsBatch = threads, enable_thinking = false)
                         else ModelConfig(nCtx = N_CTX, enable_thinking = false),
                runtime_id = RuntimeIdValue.LLAMA_CPP.value,
                compute_unit = computeUnit.value,
            )
            val wrapper = runBlocking { LlmWrapper.builder().llmCreateInput(input).build() }.getOrThrow()
            llm = wrapper

            // Where did the runtime actually put the weights?
            val verdict = judge(readPlacement())

            // Warm-up doubles as a smoke test and gives a decode speed to show the operator.
            val warm = complete(wrapper, "Reply with the single word OK.", 8)
            val speedText = warm.second?.decodingSpeed?.let { String.format("%.1f tok/s", it) } ?: "n/a"

            onNpu = verdict.onNpu
            warning = verdict.problem
            ready = verdict.onNpu || allowCpuFallback
            status = when {
                verdict.onNpu -> "llm: ready on the NPU (${gguf.name}; ${verdict.detail}); warm-up decode $speedText"
                allowCpuFallback -> "llm: READY BUT NOT ON THE NPU (${gguf.name}; ${verdict.detail}); decode $speedText"
                else -> "llm: refused, not on the NPU (${gguf.name}; ${verdict.detail})"
            }
            if (verdict.problem != null) {
                Log.e(TAG, "NPU_ALERT: $status")
            } else {
                Log.i(TAG, status)
            }
        } catch (t: Throwable) {
            ready = false
            onNpu = false
            warning = t.message ?: t.toString()
            status = "llm: load failed: $warning"
            Log.e(TAG, "NPU_ALERT: $status", t)
        }
    }

    override fun isReady(): Boolean = ready

    override fun status(): String = status

    override fun onNpu(): Boolean = onNpu

    override fun warning(): String? = warning

    override fun generate(prompt: String): String = synchronized(lock) {
        val model = llm
        if (!ready || model == null) {
            throw IllegalStateException(status)
        }
        val isIncidentExtraction = IncidentJson.isExtractionPrompt(prompt)
        val grammar = if (isIncidentExtraction) IncidentJson.GRAMMAR else null
        val (text, profile) = try {
            complete(model, prompt, MAX_NEW_TOKENS, grammar)
        } catch (t: Throwable) {
            // One automatic retry from a clean context (complete() resets it first).
            Log.w(TAG, "LLM call failed (${t.message}); retrying once from a clean context")
            complete(model, prompt, MAX_NEW_TOKENS, grammar)
        }
        if (profile != null) {
            Log.i(
                TAG,
                "LLM: ${profile.generatedTokens} tokens, decode %.1f tok/s, prefill %.1f tok/s"
                    .format(profile.decodingSpeed, profile.prefillSpeed),
            )
        }
        if (!isIncidentExtraction) {
            text
        } else {
            val cleaned = IncidentJson.nullPlaceholders(text)
            if (quickMode) IncidentGuard.apply(prompt, cleaned) else cleaned      // Gemma's path is unchanged
        }
    }

    /** True while the quick (Qwen) model is the active one. */
    fun isQuickMode(): Boolean = quickMode

    /** The quick model file is on the device (pushed next to the main one). */
    fun isQuickAvailable(): Boolean = File(modelDir, QUICK_MODEL_FILE).isFile

    /**
     * Swap the language model in place: free the current one, load the other, check its placement on the NPU like at start-up.
     * Slow (tens of seconds); call off the main thread. If the new model cannot be loaded the previous one is restored and this throws.
     * Whisper is not touched. The report in progress is kept.
     */
    fun switchModel(quick: Boolean) {
        synchronized(lock) {
            if (quick == quickMode) return
            if (quick && !isQuickAvailable()) throw IllegalStateException("The quick model ($QUICK_MODEL_FILE) is not installed on this device.")
            val previousFile = activeFile
            val previousQuick = quickMode
            ready = false
            onNpu = false
            status = "llm: switching model..."
            closeCurrent()
            activeFile = if (quick) QUICK_MODEL_FILE else modelFile
            quickMode = quick
            load()
            if (!ready) {
                val why = warning ?: status
                Log.e(TAG, "NPU_ALERT: model switch failed ($why); restoring the previous model")
                closeCurrent()
                activeFile = previousFile
                quickMode = previousQuick
                load()
                throw IllegalStateException("Could not switch the model: $why")
            }
        }
    }

    private fun closeCurrent() {
        try {
            llm?.close()
        } catch (t: Throwable) {
            Log.w(TAG, "closing the previous model failed: $t")
        }
        llm = null
    }

    private fun complete(
        model: LlmWrapper,
        prompt: String,
        maxTokens: Int,
        grammar: String? = null,
    ): Pair<String, ProfilingData?> =
        runBlocking {
            // Every prompt is self-contained. GenieX otherwise keeps the KV cache of earlier calls and
            // eventually fails with "context window exhausted" (seen after a few turns on the board).
            resetContext(model)
            val templated = model
                .applyChatTemplate(arrayOf(ChatMessage("user", prompt)), null, false)
                .getOrThrow()

            val out = StringBuilder()
            var profile: ProfilingData? = null
            var failure: Throwable? = null
            // Greedy decoding: extraction should be repeatable. For the incident-extraction prompt the
            // output is constrained to exactly the 10 form fields (string or null), so a small model
            // cannot ramble, think aloud, or invent extra keys.
            // topK = 1 makes it truly greedy: temperature 0 alone still left the SDK's default top-k/top-p sampling on, and
            // the same prompt gave different extractions from run to run.
            val sampler = SamplerConfig(temperature = 0f, topP = 1f, topK = 1, minP = 0f, seed = 42)
            if (grammar != null) {
                sampler.grammarString = grammar
            }
            val config = GenerationConfig(maxTokens = maxTokens, samplerConfig = sampler)
            model.generateStreamFlow(templated.formattedText, config).collect { r ->
                when (r) {
                    is LlmStreamResult.Token -> out.append(r.text)
                    is LlmStreamResult.Completed -> profile = r.profile
                    is LlmStreamResult.Error -> failure = r.throwable
                }
            }
            failure?.let { throw it }
            Pair(out.toString().trim(), profile)
        }

    private suspend fun resetContext(model: LlmWrapper) {
        try {
            model.reset()
        } catch (t: Throwable) {
            Log.w(TAG, "LLM context reset failed: $t")
        }
    }

    private class Placement(val usesHtpDevice: Boolean, val htpMiB: Double, val cpuMiB: Double)

    private class Verdict(val onNpu: Boolean, val problem: String?, val detail: String)

    /**
     * Parses GenieX's own load log (this process only) for where the model weights were placed:
     *   "load_tensors:  HTP0-REPACK model buffer size =   758.25 MiB"
     *   "load_tensors:          CPU model buffer size =   243.43 MiB"
     * The embedding tables stay on the CPU in every llama.cpp setup; the quantized transformer
     * matrices are what should be in the HTP0 buffers.
     */
    private fun readPlacement(): Placement? {
        return try {
            val pid = android.os.Process.myPid()
            val proc = Runtime.getRuntime().exec(
                arrayOf("logcat", "-d", "--pid=$pid", "-v", "raw", "-s", "GenieXSdk:V"),
            )
            val all = proc.inputStream.bufferedReader().readText()
            proc.waitFor()
            // The log keeps every model loaded in this process; after a model switch only the newest load counts.
            val start = all.lastIndexOf("LlmCreateInput(")
            val text = if (start >= 0) all.substring(start) else all

            val usesHtp = Regex("""Using \d+ device\(s\): HTP""").containsMatchIn(text) ||
                Regex("""using device HTP""").containsMatchIn(text)
            var htp = 0.0
            var cpu = 0.0
            Regex("""(\S+) model buffer size =\s+([\d.]+) MiB""").findAll(text).forEach { m ->
                val name = m.groupValues[1]
                val mib = m.groupValues[2].toDouble()
                if (name.startsWith("HTP")) htp += mib else if (name.startsWith("CPU")) cpu += mib
            }
            Log.i(TAG, "LLM placement: HTP device=$usesHtp, weights HTP=%.0f MiB, CPU=%.0f MiB".format(htp, cpu))
            Placement(usesHtp, htp, cpu)
        } catch (t: Throwable) {
            Log.w(TAG, "could not read GenieX placement log: $t")
            null
        }
    }

    private fun judge(p: Placement?): Verdict {
        if (p == null) {
            return Verdict(false, "cannot verify NPU use (placement log unreadable)", "placement unverified")
        }
        if (!p.usesHtpDevice) {
            return Verdict(false, "GenieX did not select the Hexagon (HTP) device", "no HTP device")
        }
        val total = p.htpMiB + p.cpuMiB
        val detail = String.format("weights: %.0f MiB on HTP0, %.0f MiB on CPU", p.htpMiB, p.cpuMiB)
        if (total <= 0.0 || p.htpMiB * 100.0 < total * MIN_HTP_WEIGHT_PERCENT) {
            return Verdict(
                false,
                "most of this model's weights are not on the Hexagon device ($detail). " +
                    "Use a model the HTP backend supports (e.g. a plain Llama or Qwen Q4_0).",
                detail,
            )
        }
        return Verdict(true, null, detail)
    }

    private fun initSdk() {
        val latch = CountDownLatch(1)
        var failure: String? = null
        GenieXSdk.getInstance().init(context, object : GenieXSdk.InitCallback {
            override fun onSuccess() {
                latch.countDown()
            }

            override fun onFailure(message: String) {
                failure = message
                latch.countDown()
            }
        })
        if (!latch.await(60, TimeUnit.SECONDS)) {
            throw IllegalStateException("GenieX SDK init timed out")
        }
        failure?.let { throw IllegalStateException("GenieX SDK init failed: $it") }
    }

    private fun findModel(): File? {
        val preferred = File(modelDir, activeFile ?: "model.gguf")
        if (preferred.isFile) {
            return preferred
        }
        return modelDir.listFiles { f -> f.isFile && f.extension.equals("gguf", ignoreCase = true) }
            ?.minByOrNull { it.name }
    }

    companion object {
        /**
         * Measured on the board (scripts/llm_thread_sweep.py, identical output at every setting), per extraction:
         * 8 threads 13.6 s / 98 CPU-s, 4 threads 13.9 s / 52 CPU-s, 2 threads 15.3 s / 29 CPU-s. The SDK's 8 pinned busy-polling
         * threads mostly spin while the NPU works, so 4 is the same speed for half the CPU. This is not a slowdown.
         */
        const val DEFAULT_THREADS = 4

        /** The quick model, an all-Q4_0 Qwen3-1.7B (see docs/demo_runbook.md): the Hexagon backend can run every layer of it. */
        const val QUICK_MODEL_FILE = "qwen3-1.7b-pureq4_0.gguf"

        private const val TAG = "NpuBridge"
        private const val N_CTX = 2048       // prompt (~600 tokens) + JSON answer fit comfortably
        private const val MAX_NEW_TOKENS = 512
        private const val MIN_HTP_WEIGHT_PERCENT = 30

    }
}
