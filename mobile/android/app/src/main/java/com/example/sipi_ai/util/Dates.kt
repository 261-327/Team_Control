package com.example.sipi_ai.util

import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale
import kotlin.math.roundToInt

private const val DAY_MILLIS = 24L * 60 * 60 * 1000

fun startOfDay(millis: Long = System.currentTimeMillis()): Calendar =
    Calendar.getInstance().apply {
        timeInMillis = millis
        set(Calendar.HOUR_OF_DAY, 0)
        set(Calendar.MINUTE, 0)
        set(Calendar.SECOND, 0)
        set(Calendar.MILLISECOND, 0)
    }

fun Calendar.isSameDay(other: Calendar): Boolean =
    get(Calendar.YEAR) == other.get(Calendar.YEAR) &&
        get(Calendar.DAY_OF_YEAR) == other.get(Calendar.DAY_OF_YEAR)

fun Calendar.copy(change: Calendar.() -> Unit = {}): Calendar =
    (clone() as Calendar).apply(change)

fun daysUntil(deadlineMillis: Long, nowMillis: Long = System.currentTimeMillis()): Int {
    val diff = startOfDay(deadlineMillis).timeInMillis - startOfDay(nowMillis).timeInMillis
    // Округление, а не деление нацело: при переходе на летнее время сутки короче на час
    return (diff.toDouble() / DAY_MILLIS).roundToInt()
}

fun formatDeadline(millis: Long): String =
    SimpleDateFormat("dd.MM.yyyy HH:mm", Locale.getDefault()).format(Date(millis))
