package com.b612p.npubridge

import org.json.JSONException
import org.json.JSONObject

/**
 * Helpers for the incident-extraction prompt used by backend/agent_brain.py.
 *
 * The brain treats any non-empty string as "this field is filled". Small models like to write
 * "Unknown" or "N/A" for things the speaker did not say, which would stop the assistant from ever
 * asking the follow-up question. The grammar below forces valid JSON with exactly the 10 form
 * fields, and [nullPlaceholders] turns placeholder strings back into null.
 */
object IncidentJson {

    /** GBNF grammar (llama.cpp): the 10 fields in order, each a string or null; severity is an enum. */
    val GRAMMAR: String = """
root ::= "{" ws "\"incident_type\"" ws ":" ws val "," ws "\"severity_level\"" ws ":" ws sev "," ws "\"incident_location\"" ws ":" ws val "," ws "\"date_time\"" ws ":" ws val "," ws "\"persons_involved\"" ws ":" ws val "," ws "\"equipment_asset_involved\"" ws ":" ws val "," ws "\"incident_description\"" ws ":" ws val "," ws "\"immediate_actions_taken\"" ws ":" ws val "," ws "\"witness_information\"" ws ":" ws val "," ws "\"recommended_follow_up_action\"" ws ":" ws val ws "}"
sev ::= "null" | "\"Low\"" | "\"Medium\"" | "\"High\"" | "\"Critical\""
val ::= "null" | str
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

    /** Replaces placeholder strings ("Unknown", "N/A", ...) with JSON null. Returns the input if it is not a JSON object. */
    fun nullPlaceholders(text: String): String {
        return try {
            val obj = JSONObject(text)
            val keys = obj.keys().asSequence().toList()
            for (k in keys) {
                val v = obj.opt(k)
                if (v is String && PLACEHOLDER.matches(v)) {
                    obj.put(k, JSONObject.NULL)
                }
            }
            obj.toString()
        } catch (e: JSONException) {
            text
        }
    }
}
