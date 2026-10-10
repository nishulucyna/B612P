package com.b612p.npubridge

import org.json.JSONException
import org.json.JSONObject

/**
 * Helpers for the incident-extraction prompt used by backend/agent_brain.py.
 *
 * The brain treats any non-empty string as "this field is filled". Small models like to write
 * "Unknown" or "N/A" for things the speaker did not say, which would stop the assistant from ever
 * asking the follow-up question. The grammar below forces valid JSON that only uses the 10 form
 * fields, and [nullPlaceholders] turns placeholder strings back into null.
 */
object IncidentJson {

    /**
     * GBNF grammar (llama.cpp): a JSON object whose keys are only the 10 form fields (any subset, any
     * order); values are strings (severity: an enum). Unspoken fields are simply left out, which makes
     * the answer much shorter than writing ten "null"s, and the brain ignores missing keys.
     */
    val GRAMMAR: String = """
root ::= "{" ws (pair (ws "," ws pair)*)? ws "}"
pair ::= "\"incident_type\"" ws ":" ws str | "\"severity_level\"" ws ":" ws sev | "\"incident_location\"" ws ":" ws str | "\"date_time\"" ws ":" ws str | "\"persons_involved\"" ws ":" ws str | "\"equipment_asset_involved\"" ws ":" ws str | "\"incident_description\"" ws ":" ws str | "\"immediate_actions_taken\"" ws ":" ws str | "\"witness_information\"" ws ":" ws str | "\"recommended_follow_up_action\"" ws ":" ws str
sev ::= "\"Low\"" | "\"Medium\"" | "\"High\"" | "\"Critical\""
str ::= "\"" ([^"\\\x7F\x00-\x1F] | "\\" ["\\/bfnrt])* "\""
ws ::= [ \n]{0,10}
""".trimStart()

    private val PLACEHOLDER = Regex(
        """^\s*(unknown|n/?a|none|null|nil|not\s+(specified|mentioned|provided|stated|available|known)|unspecified|undefined|-+)?\s*[.]?\s*$""",
        RegexOption.IGNORE_CASE,
    )

    /** True if the prompt is the brain's incident-field extraction prompt. */
    fun isExtractionPrompt(prompt: String): Boolean =
        prompt.contains("\"incident_type\"") && prompt.contains("JSON")

    /** Drops placeholder strings ("Unknown", "N/A", ...) so they read as missing. Returns the input if it is not a JSON object. */
    fun nullPlaceholders(text: String): String {
        return try {
            val obj = JSONObject(text)
            val keys = obj.keys().asSequence().toList()
            for (k in keys) {
                val v = obj.opt(k)
                if (v is String && PLACEHOLDER.matches(v)) {
                    obj.remove(k)
                }
            }
            obj.toString()
        } catch (e: JSONException) {
            text
        }
    }
}
