package com.example.sipi_ai.util

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.Calendar

class DatesTest {

    private fun at(year: Int, month: Int, day: Int, hour: Int = 12, minute: Int = 0): Long =
        Calendar.getInstance().apply {
            clear()
            set(year, month, day, hour, minute)
        }.timeInMillis

    @Test
    fun sameDayIsZeroDaysAway() {
        val now = at(2026, Calendar.OCTOBER, 26, 0, 1)
        assertEquals(0, daysUntil(at(2026, Calendar.OCTOBER, 26, 23, 59), now))
    }

    @Test
    fun countsCalendarDaysNotHours() {
        val now = at(2026, Calendar.OCTOBER, 26, 23, 59)
        assertEquals(1, daysUntil(at(2026, Calendar.OCTOBER, 27, 0, 1), now))
    }

    @Test
    fun pastDeadlineIsNegative() {
        assertEquals(-1, daysUntil(at(2026, Calendar.OCTOBER, 25), at(2026, Calendar.OCTOBER, 26)))
    }

    @Test
    fun countsAcrossMonths() {
        assertEquals(6, daysUntil(at(2026, Calendar.NOVEMBER, 1), at(2026, Calendar.OCTOBER, 26)))
    }

    @Test
    fun sameDayIgnoresTime() {
        val morning = startOfDay(at(2026, Calendar.OCTOBER, 26, 8, 0))
        val evening = startOfDay(at(2026, Calendar.OCTOBER, 26, 22, 0))
        val nextDay = startOfDay(at(2026, Calendar.OCTOBER, 27, 8, 0))
        assertTrue(morning.isSameDay(evening))
        assertFalse(morning.isSameDay(nextDay))
    }
}
