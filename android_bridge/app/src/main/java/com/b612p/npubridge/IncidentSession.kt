package com.b612p.npubridge

class SessionSubmittedException : Exception("Incident already submitted.")
class NothingToUndoException : Exception("Nothing to undo.")
class NotReadyToSubmitException(val missing: List<String>) : Exception("Missing mandatory fields: $missing")

data class ChatMessage(val role: String, val text: String, val timeMillis: Long)

/** The result of one action: the new state, what the user said (if anything) and what to say back. */
data class Turn(val state: IncidentState, val userText: String?, val speech: String?)

/**
 * One incident report in progress, entirely on the device: conversation, the brain, undo history, submit.
 * The on-board equivalent of the laptop orchestrator's Orchestrator class (backend/server.py).
 * [llm] takes a prompt and returns the model's raw text (the NPU LLM on the board).
 */
class IncidentSession(private val llm: (String) -> String) {
    private var state: IncidentState = IncidentBrain.blankState()
    private val messages = ArrayList<ChatMessage>()
    private val history = ArrayList<Pair<IncidentState, Int>>()   // state and conversation length before each turn

    @Synchronized fun state(): IncidentState = state
    @Synchronized fun transcript(): List<ChatMessage> = messages.toList()

    private fun log(role: String, text: String) {
        messages.add(ChatMessage(role, text, System.currentTimeMillis()))
    }

    private fun ensureOpen() {
        if (state.status == "submitted") throw SessionSubmittedException()
    }

    /** A spoken or typed report. The model call can take seconds; run this off the UI thread. */
    @Synchronized fun textTurn(text: String): Turn {
        ensureOpen()
        history.add(state to messages.size)
        while (history.size > 10) history.removeAt(0)
        val result = try {
            IncidentBrain.processTurn(text, state, llm)
        } catch (e: Exception) {
            history.removeAt(history.size - 1)
            throw e
        }
        state = result
        log("user", text)
        val speech = state.speech()
        if (speech != null) log("assistant", speech)
        return Turn(state, text, speech)
    }

    /** The recogniser heard nothing usable: ask again without touching the report. */
    @Synchronized fun nothingHeard(): Turn {
        ensureOpen()
        log("assistant", IncidentBrain.RETRY_PROMPT)
        return Turn(state, "", IncidentBrain.RETRY_PROMPT)
    }

    /** Discard the last turn (e.g. it was misheard) and restore the state before it. */
    @Synchronized fun undo(): Turn {
        ensureOpen()
        if (history.isEmpty()) throw NothingToUndoException()
        val (previous, length) = history.removeAt(history.size - 1)
        state = previous
        while (messages.size > length) messages.removeAt(messages.size - 1)
        val speech = "Okay, I discarded that. Please say it again."
        log("assistant", speech)
        return Turn(state, null, speech)
    }

    /** Submit the report, optionally with manual edits to the fields. Needs the 4 mandatory fields. */
    @Synchronized fun submit(edits: Map<String, String?>? = null): Turn {
        ensureOpen()
        val fields = LinkedHashMap(state.fields)
        if (edits != null) {
            val cleaned = IncidentBrain.sanitize(edits)
            for (key in edits.keys) if (key in IncidentBrain.ALL_FIELDS) fields[key] = cleaned[key]
        }
        val missing = IncidentBrain.identifyMissing(fields)
        if (missing.isNotEmpty()) throw NotReadyToSubmitException(missing)
        state = IncidentState(state.sessionId, "submitted", emptyList(), null, fields,
            state.toolCall?.copy(arguments = fields))
        return Turn(state, null, null)
    }

    @Synchronized fun reset(): Turn {
        history.clear()
        messages.clear()
        state = IncidentBrain.blankState()
        return Turn(state, null, state.nextPrompt)
    }
}
