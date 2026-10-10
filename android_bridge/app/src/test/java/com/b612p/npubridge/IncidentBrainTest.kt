package com.b612p.npubridge

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** Checks the Kotlin brain against golden data produced by the Python brain (scripts/gen_brain_golden.py). */
class IncidentBrainTest {

    @Suppress("UNCHECKED_CAST")
    private val golden: Map<String, Any?> = MiniJson.parse(
        javaClass.classLoader!!.getResourceAsStream("brain_golden.json")!!.bufferedReader(Charsets.UTF_8).readText(),
    ) as Map<String, Any?>

    @Suppress("UNCHECKED_CAST")
    private fun list(key: String) = golden[key] as List<Map<String, Any?>>

    @Suppress("UNCHECKED_CAST")
    private fun asFields(v: Any?) = (v as Map<String, Any?>).mapValues { it.value as String? }

    @Test
    fun promptsAreByteIdenticalToPython() {
        for (case in list("prompts")) {
            val prompt = IncidentBrain.buildExtractionPrompt(case["transcript"] as String, asFields(case["known"]))
            assertEquals(case["prompt"], prompt)
        }
    }

    @Test
    fun jsonCleaningMatchesPython() {
        for (case in list("clean_and_parse")) {
            assertEquals("raw=${case["raw"]}", case["parsed"], IncidentBrain.cleanAndParseJson(case["raw"] as String))
        }
    }

    @Test
    fun sanitizingMatchesPython() {
        for (case in list("sanitize")) {
            val actual = IncidentBrain.sanitize(IncidentBrain.cleanAndParseJson(case["raw"] as String))
            assertEquals("raw=${case["raw"]}", asFields(case["sanitized"]), actual)
        }
    }

    @Test
    fun blankStateMatchesPython() {
        @Suppress("UNCHECKED_CAST")
        val expected = golden["blank"] as Map<String, Any?>
        val s = IncidentBrain.blankState()
        assertEquals(expected["status"], s.status)
        assertEquals(expected["next_prompt"], s.nextPrompt)
        assertEquals(expected["missing"], s.missing)
        assertEquals(asFields(expected["fields"]), s.fields)
        assertEquals(golden["initial_prompt"], IncidentBrain.INITIAL_PROMPT)
        assertEquals(golden["retry_prompt"], IncidentBrain.RETRY_PROMPT)
    }

    @Test
    fun conversationsMatchPythonTurnByTurn() {
        @Suppress("UNCHECKED_CAST")
        val sequences = golden["sequences"] as Map<String, List<Map<String, Any?>>>
        for ((name, steps) in sequences) {
            var state = IncidentBrain.blankState()
            for ((i, step) in steps.withIndex()) {
                state = IncidentBrain.processTurn(step["user"] as String, state) { step["raw_llm"] as String }
                @Suppress("UNCHECKED_CAST")
                val want = step["result"] as Map<String, Any?>
                val where = "$name turn ${i + 1}"
                assertEquals(where, want["status"], state.status)
                assertEquals(where, want["missing"], state.missing)
                assertEquals(where, want["next_prompt"], state.nextPrompt)
                assertEquals(where, asFields(want["fields"]), state.fields)
                assertEquals(where, want["tool_call_function"], state.toolCall?.function)
                assertEquals(where, want["summary_for_tts"], state.toolCall?.summaryForTts)
            }
        }
    }

    @Test
    fun speechIsTheQuestionOrTheSummary() {
        var state = IncidentBrain.blankState()
        assertEquals(IncidentBrain.INITIAL_PROMPT, state.speech())
        state = IncidentBrain.processTurn("x", state) { """{"incident_type":"Fire"}""" }
        assertEquals("Understood. Where did this Fire occur?", state.speech())
        state = IncidentBrain.processTurn("y", state) {
            """{"incident_location":"Lab","date_time":"noon","immediate_actions_taken":"Evacuated"}"""
        }
        assertNull(state.nextPrompt)
        assertEquals(state.toolCall!!.summaryForTts, state.speech())
    }
}
