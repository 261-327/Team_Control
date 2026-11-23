package com.example.sipi_ai.ui.calendar

import com.example.sipi_ai.R
import com.example.sipi_ai.util.copy
import java.util.Calendar

enum class CalendarMarker(val colorRes: Int, val backgroundRes: Int) {
    URGENT(R.color.calendar_deadline_urgent, R.color.calendar_deadline_urgent_bg),
    SOON(R.color.calendar_deadline_soon, R.color.calendar_deadline_soon_bg),
    LATER(R.color.calendar_deadline_later, R.color.calendar_deadline_later_bg),
    COMPLETED(R.color.calendar_deadline_completed, R.color.calendar_deadline_completed_bg),
}

data class DayCell(val day: Calendar?, val marker: CalendarMarker?)

fun monthCells(month: Calendar, markerOn: (Calendar) -> CalendarMarker?): List<DayCell> {
    val firstDay = month.copy { set(Calendar.DAY_OF_MONTH, 1) }
    // Неделя в сетке начинается с понедельника, а Calendar нумерует дни с воскресенья (1)
    val leadingBlanks = (firstDay.get(Calendar.DAY_OF_WEEK) + 5) % 7

    val days = (1..firstDay.getActualMaximum(Calendar.DAY_OF_MONTH)).map { dayOfMonth ->
        val day = firstDay.copy { set(Calendar.DAY_OF_MONTH, dayOfMonth) }
        DayCell(day, markerOn(day))
    }
    return List(leadingBlanks) { DayCell(null, null) } + days
}
