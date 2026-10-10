package com.b612p.npubridge

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

class IncidentSessionTest {
    private fun session(vararg replies: String): IncidentSession {
        val queue = ArrayDeque(replies.toList())
        return IncidentSession { queue.removeFirst() }
    }

    @Test
    fun twoTurnConversationCompletes() {
        val s = session(
            """{"incident_type":"Pipe Burst","incident_location":"Building 4"}""",
            """{"date_time":"3 PM","immediate_actions_taken":"turned off the valve"}""",
        )
        val t1 = s.textTurn("A pipe burst in building 4")
        assertEquals("collecting", t1.state.status)
        assertEquals("Got that. At what time or date did this occur?", t1.speech)
        val t2 = s.textTurn("3 PM, we turned off the valve")
        assertEquals("complete", t2.state.status)
        assertEquals("Pipe Burst", t2.state.fields["incident_type"])        // earlier turn kept
        assertEquals("populate_incident_form", t2.state.toolCall!!.function)
        assertEquals(4, s.transcript().size)
    }

    @Test
    fun undoRestoresStateAndConversation() {
        val s = session("""{"incident_type":"Leak","incident_location":"confidence room"}""")
        s.textTurn("misheard")
        val u = s.undo()
        assertNull(u.state.fields["incident_type"])
        assertEquals("Okay, I discarded that. Please say it again.", u.speech)
        assertEquals(listOf("assistant"), s.transcript().map { it.role })
        try { s.undo(); fail("expected NothingToUndo") } catch (_: NothingToUndoException) {}
    }

    @Test
    fun failedModelCallLeavesNoTraceAndIsNotUndoable() {
        val s = IncidentSession { throw IllegalStateException("npu down") }
        try { s.textTurn("hello"); fail("expected failure") } catch (_: IllegalStateException) {}
        assertTrue(s.transcript().isEmpty())
        try { s.undo(); fail("expected NothingToUndo") } catch (_: NothingToUndoException) {}
    }

    @Test
    fun submitNeedsMandatoryFieldsAndAcceptsEdits() {
        val s = session("""{"incident_type":"Fire"}""")
        s.textTurn("fire")
        try { s.submit(); fail("expected NotReady") } catch (e: NotReadyToSubmitException) {
            assertEquals(listOf("incident_location", "date_time", "immediate_actions_taken"), e.missing)
        }
        val done = s.submit(mapOf("incident_location" to "Lab", "date_time" to "noon", "immediate_actions_taken" to "Evacuated"))
        assertEquals("submitted", done.state.status)
        assertEquals("Lab", done.state.fields["incident_location"])
        try { s.textTurn("more"); fail("expected Submitted") } catch (_: SessionSubmittedException) {}
        try { s.undo(); fail("expected Submitted") } catch (_: SessionSubmittedException) {}
    }

    @Test
    fun resetStartsOver() {
        val s = session("""{"incident_type":"Fire"}""")
        s.textTurn("fire")
        val r = s.reset()
        assertEquals("collecting", r.state.status)
        assertEquals(IncidentBrain.INITIAL_PROMPT, r.speech)
        assertTrue(s.transcript().isEmpty())
        try { s.undo(); fail("expected NothingToUndo") } catch (_: NothingToUndoException) {}
    }

    @Test
    fun nothingHeardAsksAgainWithoutChangingTheReport() {
        val s = session()
        val before = s.state()
        val t = s.nothingHeard()
        assertEquals(IncidentBrain.RETRY_PROMPT, t.speech)
        assertEquals(before, s.state())
    }
}
