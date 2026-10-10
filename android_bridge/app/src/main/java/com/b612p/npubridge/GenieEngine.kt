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
 *   adb push gemma-4-E4B_q4_0-it.gguf /data/local/tmp/npu_models/llm/model.gguf
 * (any *.gguf in that folder works; model.gguf is preferred if several are present).
 * Nothing is downloaded: the model is opened by path.
 *
 * Honesty note: GenieX does not report which processor ran the model. We request the NPU and
 * surface decode speed; confirm NPU use with logcat (hexagon / htp / ggml-hex lines).
 */
class GenieEngine @JvmOverloads constructor(
    private val context: Context,
    private val modelDir: File = File(ModelLoader.DEFAULT_ROOT, "llm"),
) : LlmEngine {

    @Volatile private var llm: LlmWrapper? = null
    @Volatile private var ready = false
    @Volatile private var onNpu = false
    @Volatile private var warning: String? = null
    @Volatile private var status = "llm: not loaded yet"

    /** Loads the SDK and the model, then runs a short warm-up. Slow; call off the main thread. */
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
                config = ModelConfig(nCtx = N_CTX, enable_thinking = false),
                runtime_id = RuntimeIdValue.LLAMA_CPP.value,
                compute_unit = ComputeUnitValue.NPU.value,
            )
            val wrapper = runBlocking { LlmWrapper.builder().llmCreateInput(input).build() }.getOrThrow()
            llm = wrapper

            // Warm-up doubles as a smoke test and gives a decode speed to show the operator.
            val warm = complete(wrapper, "Reply with the single word OK.", 8)
            val speed = warm.second?.decodingSpeed
            onNpu = true // NPU was requested and the model loaded; see the honesty note above
            ready = true
            status = "llm: ready, NPU requested (llama.cpp, ${gguf.name}); warm-up decode " +
                (speed?.let { String.format("%.1f tok/s", it) } ?: "n/a") +
                " - confirm NPU use in logcat"
            Log.i(TAG, status)
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

    override fun generate(prompt: String): String {
        val model = llm
        if (!ready || model == null) {
            throw IllegalStateException(status)
        }
        val (text, profile) = complete(model, prompt, MAX_NEW_TOKENS)
        if (profile != null) {
            Log.i(TAG, "LLM: ${profile.generatedTokens} tokens, decode %.1f tok/s, prefill %.1f tok/s"
                .format(profile.decodingSpeed, profile.prefillSpeed))
        }
        return text
    }

    private fun complete(model: LlmWrapper, prompt: String, maxTokens: Int): Pair<String, ProfilingData?> =
        runBlocking {
            val templated = model
                .applyChatTemplate(arrayOf(ChatMessage("user", prompt)), null, false)
                .getOrThrow()

            val out = StringBuilder()
            var profile: ProfilingData? = null
            var failure: Throwable? = null
            // Greedy decoding: extraction should be repeatable.
            val config = GenerationConfig(
                maxTokens = maxTokens,
                samplerConfig = SamplerConfig(temperature = 0f),
            )
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
        val preferred = File(modelDir, "model.gguf")
        if (preferred.isFile) {
            return preferred
        }
        return modelDir.listFiles { f -> f.isFile && f.extension.equals("gguf", ignoreCase = true) }
            ?.minByOrNull { it.name }
    }

    companion object {
        private const val TAG = "NpuBridge"
        private const val N_CTX = 2048       // prompt (~600 tokens) + JSON answer fit comfortably
        private const val MAX_NEW_TOKENS = 512
    }
}
