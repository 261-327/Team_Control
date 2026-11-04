package com.example.sipi_ai.util

import java.util.Calendar

fun initials(name: String): String {
    val parts = name.trim().split(Regex("\\s+")).filter { it.isNotEmpty() }
    return when {
        parts.isEmpty() -> "?"
        parts.size == 1 -> parts[0].take(1).uppercase()
        else -> (parts[0].take(1) + parts[1].take(1)).uppercase()
    }
}

private const val CYRILLIC = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
private val LATIN = arrayOf(
    "a", "b", "v", "g", "d", "e", "e", "z", "z", "i", "i", "k", "l", "m", "n", "o", "p",
    "r", "s", "t", "u", "f", "h", "c", "c", "s", "s", "", "y", "", "e", "u", "y",
)

/** «Сипи проект» → «SIP»: ключ для кодов задач (SIP-1, SIP-2…). */
fun projectKey(name: String): String {
    val builder = StringBuilder()
    for (ch in name.lowercase()) {
        val index = CYRILLIC.indexOf(ch)
        when {
            index >= 0 -> builder.append(LATIN[index])
            ch in 'a'..'z' -> builder.append(ch)
        }
    }
    val key = builder.toString().uppercase().take(3)
    return if (key.length >= 2) key else "PRJ"
}

fun currentSeason(now: Calendar = Calendar.getInstance()): String {
    val season = when (now.get(Calendar.MONTH)) {
        Calendar.DECEMBER, Calendar.JANUARY, Calendar.FEBRUARY -> "Зима"
        Calendar.MARCH, Calendar.APRIL, Calendar.MAY -> "Весна"
        Calendar.JUNE, Calendar.JULY, Calendar.AUGUST -> "Лето"
        else -> "Осень"
    }
    return "$season ${now.get(Calendar.YEAR)}"
}
