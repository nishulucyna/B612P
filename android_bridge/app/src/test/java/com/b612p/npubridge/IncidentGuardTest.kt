package com.b612p.npubridge

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class IncidentGuardTest {
    private fun prompt(text: String) = "x\n\nLATEST USER TRANSCRIPT:\n\"$text\"\n\nJSON OUTPUT:"

    @Suppress("UNCHECKED_CAST")
    private fun run(text: String, json: String): Map<String, String> = MiniJson.parse(IncidentGuard.apply(prompt(text), json)) as Map<String, String>

    @Test
    fun placeholderDatesAreDropped() {
        assertFalse(run("gas smell in the basement", """{"incident_type":"gas","date_time":"current time"}""").containsKey("date_time"))
        assertFalse(run("gas smell", """{"date_time":"current time (not specified)"}""").containsKey("date_time"))
        assertFalse(run("gas smell", """{"date_time":"Date not specified"}""").containsKey("date_time"))
        assertEquals("gas", run("gas smell", """{"incident_type":"gas","date_time":"unknown"}""")["incident_type"])
    }

    @Test
    fun realValuesSurvive() {
        assertEquals("yesterday at 3 PM", run("a leak yesterday at 3 PM", """{"date_time":"yesterday at 3 PM"}""")["date_time"])
        assertEquals("just now", run("someone fainted just now", """{"date_time":"just now"}""")["date_time"])
        assertEquals("Unknown man near gate 2", run("an unknown man was near gate 2", """{"persons_involved":"Unknown man near gate 2"}""")["persons_involved"])
        assertTrue(run("cause is not known yet", """{"incident_description":"The cause is not known yet and we are checking everything"}""").containsKey("incident_description"))
    }

    @Test
    fun inventedFollowUpIsDroppedButGroundedOneSurvives() {
        val a = run("water leak near conference room 2, maintenance isolated the area",
            """{"incident_type":"water leak","recommended_follow_up_action":"Inspect the area for further issues and ensure proper drainage"}""")
        assertFalse(a.containsKey("recommended_follow_up_action"))
        assertEquals("water leak", a["incident_type"])
        val b = run("the pipe burst, someone should replace the pipe and check the valves",
            """{"recommended_follow_up_action":"Replace the pipe and check the valves"}""")
        assertTrue(b.containsKey("recommended_follow_up_action"))
    }

    @Test
    fun otherFieldsAndNonJsonAreLeftAlone() {
        assertEquals("High", run("something happened", """{"severity_level":"High"}""")["severity_level"])
        assertEquals("Maintenance", run("maintenance isolated it", """{"persons_involved":"Maintenance"}""")["persons_involved"])
        assertEquals("not json", IncidentGuard.apply("p", "not json"))
    }
}
