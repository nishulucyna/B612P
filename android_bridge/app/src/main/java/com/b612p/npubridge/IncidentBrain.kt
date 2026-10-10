package com.b612p.npubridge

import java.util.UUID

/**
 * On-device port of backend/agent_brain.py plus the field hygiene from backend/server.py, so the incident assistant
 * can run entirely on the board. Every function mirrors its Python original; IncidentBrainTest checks the results
 * against golden data generated from the Python code (scripts/gen_brain_golden.py).
 */
data class ToolCall(
    val function: String,
    val arguments: Map<String, String?>,
    val summaryForTts: String,
)

data class IncidentState(
    val sessionId: String,
    val status: String,                       // collecting | complete | submitted
    val missing: List<String>,
    val nextPrompt: String?,
    val fields: Map<String, String?>,
    val toolCall: ToolCall?,
) {
    /** What to say out loud for this state: the follow-up question, or the final summary. */
    fun speech(): String? = if (status == "complete") toolCall?.summaryForTts else nextPrompt
}

object IncidentBrain {
    val MANDATORY_FIELDS = listOf("incident_type", "incident_location", "date_time", "immediate_actions_taken")
    val ALL_FIELDS = listOf(
        "incident_type", "severity_level", "incident_location", "date_time", "persons_involved",
        "equipment_asset_involved", "incident_description", "immediate_actions_taken", "witness_information",
        "recommended_follow_up_action",
    )
    val SEVERITIES = listOf("Low", "Medium", "High", "Critical")

    const val INITIAL_PROMPT = "Please describe what happened, where, and when."
    const val RETRY_PROMPT = "Sorry, I didn't catch that. Could you say it again?"

    private const val SYSTEM_PROMPT = """You are an on-device AI Incident Report Assistant for Qualcomm Snapdragon devices.
Your task is to extract structured incident data from natural spoken user reports.

Extract only what the user mentioned or clearly implied into this JSON schema:
{
  "incident_type": string or null,
  "severity_level": "Low" | "Medium" | "High" | "Critical" | null,
  "incident_location": string or null,
  "date_time": string or null,
  "persons_involved": string or null,
  "equipment_asset_involved": string or null,
  "incident_description": string or null,
  "immediate_actions_taken": string or null,
  "witness_information": string or null,
  "recommended_follow_up_action": string or null
}

Rules:
1. Return ONLY a valid JSON object. No preamble, no markdown backticks, no explanations.
2. If an item was not mentioned, set its value to null.
3. If partial existing fields are provided, preserve them unless the user explicitly updates or corrects them.
4. Estimate severity_level if strongly implied (e.g., "burst pipe flooded room" -> "High", "minor drip" -> "Low").
"""

    fun blankState(): IncidentState = IncidentState(
        sessionId = "session-" + UUID.randomUUID().toString().replace("-", "").take(8),
        status = "collecting",
        missing = MANDATORY_FIELDS,
        nextPrompt = INITIAL_PROMPT,
        fields = ALL_FIELDS.associateWith { null },
        toolCall = null,
    )

    fun buildExtractionPrompt(transcript: String, current: Map<String, String?>): String {
        val known = LinkedHashMap<String, String?>()
        for ((k, v) in current) if (v != null) known[k] = v
        return "$SYSTEM_PROMPT\n\nCURRENT KNOWN INFORMATION:\n${MiniJson.dumpsFlat(known)}\n\n" +
            "LATEST USER TRANSCRIPT:\n\"$transcript\"\n\nJSON OUTPUT:"
    }

    /** Strips code fences and prose around the JSON object, tolerates a missing closing brace. {} if unusable. */
    fun cleanAndParseJson(raw: String): Map<String, Any?> {
        var text = raw.trim()
        if (text.startsWith("```")) {
            text = text.replace(Regex("^```(?:json)?\\s*", RegexOption.IGNORE_CASE), "")
            text = text.replace(Regex("\\s*```$"), "")
            text = text.trim()
        }
        Regex("(\\{.*\\})", RegexOption.DOT_MATCHES_ALL).find(text)?.let { text = it.groupValues[1] }
        for (candidate in listOf(text, "$text}")) {
            try {
                val parsed = MiniJson.parse(candidate)
                @Suppress("UNCHECKED_CAST")
                return if (parsed is Map<*, *>) parsed as Map<String, Any?> else emptyMap()
            } catch (_: JsonException) {
                // try the next candidate
            }
        }
        return emptyMap()
    }

    /** Coerces whatever the LLM returned into {all 10 contract keys: String?}; an invalid severity becomes null. */
    fun sanitize(data: Map<String, Any?>?): Map<String, String?> {
        val out = LinkedHashMap<String, String?>()
        for (key in ALL_FIELDS) {
            var value: String? = when (val v = data?.get(key)) {
                null -> null
                is List<*> -> v.filter { it != null && MiniJson.pyStr(it).trim().isNotEmpty() }
                    .joinToString(", ") { MiniJson.pyStr(it).trim() }
                is Map<*, *> -> null
                is String -> v
                else -> MiniJson.pyStr(v)
            }
            if (value != null) {
                value = value.trim()
                if (value.isEmpty() || value.lowercase() == "null") value = null
            }
            if (key == "severity_level" && value != null) {
                value = SEVERITIES.firstOrNull { it.equals(value, ignoreCase = true) }
            }
            out[key] = value
        }
        return out
    }

    private fun isEmpty(v: String?) = v == null || v.trim().isEmpty() || v.lowercase() == "null"

    fun mergeFields(current: Map<String, String?>, extracted: Map<String, String?>): Map<String, String?> {
        val merged = LinkedHashMap(current)
        for (field in ALL_FIELDS) {
            val v = extracted[field]
            if (!isEmpty(v)) merged[field] = v
        }
        return merged
    }

    fun identifyMissing(fields: Map<String, String?>): List<String> = MANDATORY_FIELDS.filter { isEmpty(fields[it]) }

    fun clarificationQuestion(missingField: String, fields: Map<String, String?>): String {
        val type = fields["incident_type"]
        return when (missingField) {
            "incident_location" -> "Understood. Where did this ${if (type.isNullOrEmpty()) "incident" else type} occur?"
            "date_time" -> "Got that. At what time or date did this occur?"
            "immediate_actions_taken" -> "Understood. Has any immediate action or containment been taken yet?"
            "incident_type" -> "Could you clarify what kind of incident took place?"
            else -> "Could you provide details regarding ${missingField.replace('_', ' ')}?"
        }
    }

    fun summaryFor(fields: Map<String, String?>): String =
        "Incident report ready. ${fields["incident_type"] ?: "Incident"} " +
            "at ${fields["incident_location"] ?: "specified location"}, " +
            "recorded at ${fields["date_time"] ?: "time specified"}. " +
            "Action taken: ${fields["immediate_actions_taken"] ?: "noted"}. " +
            "Please review on screen and confirm submission."

    /**
     * One conversational turn: extract with the LLM, merge into the known fields, then the Diamond Gate.
     * [llm] takes the prompt and returns the model's raw text.
     */
    fun processTurn(transcript: String, state: IncidentState, llm: (String) -> String): IncidentState {
        val extracted = sanitize(cleanAndParseJson(llm(buildExtractionPrompt(transcript, state.fields))))
        val fields = mergeFields(state.fields, extracted)
        val missing = identifyMissing(fields)
        if (missing.isNotEmpty()) {
            return IncidentState(state.sessionId, "collecting", missing, clarificationQuestion(missing[0], fields), fields, null)
        }
        val call = ToolCall("populate_incident_form", fields, summaryFor(fields))
        return IncidentState(state.sessionId, "complete", emptyList(), null, fields, call)
    }
}
