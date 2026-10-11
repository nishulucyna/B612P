package com.b612p.npubridge

/**
 * Output guard for the quick (Qwen) model. Port of scripts/llm_guard.py, which was measured on 22 narrations against the board:
 * with it the quick model made the same correct-gate decisions as Gemma (12/12 and 10/10) instead of 10/12.
 *
 * Small models sometimes write a placeholder inside a value ("current time", "date not specified") instead of leaving the field out.
 * The Diamond gate then believes the field is filled and completes the report instead of asking. Two rules:
 *  1. a short value that only says "not specified" / "unknown" / "current time" is removed (the field counts as missing);
 *  2. recommended follow-up advice, the field small models invent, must share most of its content words with what the person said.
 * Severity and everything else are left alone. Gemma never goes through this: it is only applied in quick mode.
 */
object IncidentGuard {
    private val PHRASE = Regex(
        """(\bnot\s+(specified|mentioned|provided|stated|available|known|given|reported|applicable)\b|\bunspecified\b|""" +
            """\bno\s+(information|details?|data)\b|\bnone\s+(given|mentioned|specified)\b|\bto be determined\b|""" +
            """^\s*(the\s+)?(current|present|local)\s+(date|time)\b|^\s*(date|time)\s+(not|unknown)\b)""",
        RegexOption.IGNORE_CASE,
    )
    private val WHOLE = Regex("""^\s*(unknown|n/?a|none|nil|tbd|-+)\W*$""", RegexOption.IGNORE_CASE)
    private val GROUNDED_FIELDS = setOf("recommended_follow_up_action")
    private val STOP = ("the a an and or of in on at to for with from by is are was were be been has have had it its this that these those " +
        "there then than as into onto over under about after before during while who whom which what when where some any all not no yes " +
        "also very more most only just").split(" ").toSet()
    private val TRANSCRIPT = Regex("""LATEST USER TRANSCRIPT:\s*"(.*)"\s*JSON OUTPUT""", RegexOption.DOT_MATCHES_ALL)
    private val WORD = Regex("""[a-z0-9']+""")

    fun transcriptOf(prompt: String): String = TRANSCRIPT.find(prompt)?.groupValues?.get(1) ?: ""

    private fun isPlaceholder(value: String): Boolean {
        if (WHOLE.matches(value)) return true
        return value.trim().split(Regex("\\s+")).size <= 6 && PHRASE.containsMatchIn(value)
    }

    private fun contentWords(text: String) = WORD.findAll(text.lowercase()).map { it.value }.filter { it.length >= 4 && it !in STOP }.toList()

    private fun grounded(value: String, transcript: String, need: Double = 0.5): Boolean {
        val ws = contentWords(value)
        if (ws.isEmpty()) return true
        val heard = WORD.findAll(transcript.lowercase()).map { it.value.take(5) }.toSet()      // prefix match absorbs plurals and tenses
        return ws.count { it.take(5) in heard }.toDouble() / ws.size >= need
    }

    /** The model's JSON object with placeholder / ungrounded values removed. Anything that is not a JSON object is returned unchanged. */
    fun apply(prompt: String, raw: String): String {
        val obj = try { MiniJson.parse(raw) } catch (e: Exception) { return raw }
        if (obj !is Map<*, *>) return raw
        val said = transcriptOf(prompt)
        val kept = ArrayList<String>()
        for ((k, v) in obj) {
            val key = k as? String ?: continue
            if (v is String) {
                if (isPlaceholder(v)) continue
                if (key in GROUNDED_FIELDS && said.isNotEmpty() && !grounded(v, said)) continue
                kept.add(MiniJson.quote(key) + ":" + MiniJson.quote(v))
            }
        }
        return "{" + kept.joinToString(",") + "}"
    }
}
