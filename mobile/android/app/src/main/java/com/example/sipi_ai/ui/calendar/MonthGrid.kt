package com.example.sipi_ai.ui.calendar

import com.example.sipi_ai.util.copy
import java.util.Calendar

data class DayCell(val day: Calendar?, val hasTasks: Boolean)

fun monthCells(month: Calendar, hasTasksOn: (Calendar) -> Boolean): List<DayCell> {
    val firstDay = month.copy { set(Calendar.DAY_OF_MONTH, 1) }
    // Неделя в сетке начинается с понедельника, а Calendar нумерует дни с воскресенья (1)
    val leadingBlanks = (firstDay.get(Calendar.DAY_OF_WEEK) + 5) % 7

    val days = (1..firstDay.getActualMaximum(Calendar.DAY_OF_MONTH)).map { dayOfMonth ->
        val day = firstDay.copy { set(Calendar.DAY_OF_MONTH, dayOfMonth) }
        DayCell(day, hasTasksOn(day))
    }
    return List(leadingBlanks) { DayCell(null, false) } + days
}
