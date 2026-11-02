package com.example.sipi_ai.ui.calendar

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.Calendar

class MonthGridTest {

    private fun month(year: Int, month: Int): Calendar =
        Calendar.getInstance().apply {
            clear()
            set(year, month, 1)
        }

    @Test
    fun octoberStartsOnThursdayAfterThreeBlanks() {
        val cells = monthCells(month(2026, Calendar.OCTOBER)) { false }

        assertEquals(3 + 31, cells.size)
        assertTrue(cells.take(3).all { it.day == null })
        assertEquals(1, cells[3].day?.get(Calendar.DAY_OF_MONTH))
        assertEquals(31, cells.last().day?.get(Calendar.DAY_OF_MONTH))
    }

    @Test
    fun monthStartingOnMondayHasNoBlanks() {
        val cells = monthCells(month(2026, Calendar.JUNE)) { false }

        assertEquals(30, cells.size)
        assertEquals(1, cells.first().day?.get(Calendar.DAY_OF_MONTH))
    }

    @Test
    fun monthStartingOnSundayHasSixBlanks() {
        val cells = monthCells(month(2026, Calendar.FEBRUARY)) { false }

        assertEquals(6 + 28, cells.size)
        assertTrue(cells.take(6).all { it.day == null })
    }

    @Test
    fun marksOnlyDaysWithTasks() {
        val cells = monthCells(month(2026, Calendar.OCTOBER)) { it.get(Calendar.DAY_OF_MONTH) == 15 }

        assertEquals(listOf(15), cells.filter { it.hasTasks }.map { it.day?.get(Calendar.DAY_OF_MONTH) })
    }
}
