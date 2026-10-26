package com.example.sipisanzhapov



import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale

object DeadlineUtils {

    private const val DAY_MS = 24L * 60 * 60 * 1000

    // Обнуляем время, чтобы сравнивать именно даты, а не миллисекунды
    private fun startOfDay(millis: Long): Long =
        Calendar.getInstance().apply {
            timeInMillis = millis
            set(Calendar.HOUR_OF_DAY, 0)
            set(Calendar.MINUTE, 0)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }.timeInMillis

    // Календарные дни до дедлайна: 0 — сегодня, отрицательное — просрочено
    fun daysLeft(deadlineMillis: Long, nowMillis: Long = System.currentTimeMillis()): Int {
        val diff = startOfDay(deadlineMillis) - startOfDay(nowMillis)
        // round нужен из-за перехода на летнее время (разница может быть на час меньше суток)
        return Math.round(diff.toDouble() / DAY_MS).toInt()
    }

    // Склонение: 1 день, 2 дня, 5 дней, 21 день, 11 дней
    fun pluralDays(n: Int): String {
        val abs = Math.abs(n)
        val mod10 = abs % 10
        val mod100 = abs % 100
        return when {
            mod100 in 11..14 -> "дней"
            mod10 == 1 -> "день"
            mod10 in 2..4 -> "дня"
            else -> "дней"
        }
    }

    // Текст для карточки
    fun remainingText(deadlineMillis: Long, nowMillis: Long = System.currentTimeMillis()): String {
        if (deadlineMillis < nowMillis) return "Дедлайн истёк"
        val days = daysLeft(deadlineMillis, nowMillis)
        return if (days == 0) "Сегодня последний день"
        else "Осталось $days ${pluralDays(days)}"
    }

    // "30.10.2026 18:00"
    fun formatDeadline(deadlineMillis: Long): String =
        SimpleDateFormat("dd.MM.yyyy HH:mm", Locale.getDefault()).format(Date(deadlineMillis))
}