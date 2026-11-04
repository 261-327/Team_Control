package com.example.sipi_ai.util

import com.example.sipi_ai.data.Task
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

private const val HOUR_MILLIS = 60L * 60 * 1000

/** Календарь в формате iCalendar: открывается в любом календарном приложении. */
fun buildIcs(tasks: List<Task>, nowMillis: Long = System.currentTimeMillis()): String {
    val format = SimpleDateFormat("yyyyMMdd'T'HHmmss'Z'", Locale.US).apply {
        timeZone = TimeZone.getTimeZone("UTC")
    }
    val lines = mutableListOf("BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//SIPI//RU", "CALSCALE:GREGORIAN")
    for (task in tasks) {
        val start = task.deadlineMillis ?: continue
        lines += "BEGIN:VEVENT"
        lines += "UID:sipi-task-${task.id}@sipi"
        lines += "DTSTAMP:${format.format(Date(nowMillis))}"
        lines += "DTSTART:${format.format(Date(start))}"
        lines += "DTEND:${format.format(Date(start + HOUR_MILLIS))}"
        lines += "SUMMARY:${escapeIcs(task.title)}"
        lines += "DESCRIPTION:${escapeIcs(task.description)}"
        lines += "END:VEVENT"
    }
    lines += "END:VCALENDAR"
    return lines.joinToString("\r\n", postfix = "\r\n")
}

private fun escapeIcs(text: String): String =
    text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
