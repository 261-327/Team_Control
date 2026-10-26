package com.example.sipisanzhapov

import java.util.Calendar

object TaskRepository {

    // За сколько дней до дедлайна задача становится срочной
    const val URGENT_DAYS = 2

    // Статусы: 0 — срочно, 1 — в процессе, 2 — ревью, 3 — бэклог
    private const val STATUS_URGENT = 0
    private const val STATUS_IN_PROGRESS = 1
    private const val STATUS_BACKLOG = 3

    // Дедлайн на указанное число дней от сегодня, в 18:00
    private fun deadlineIn(days: Int): Long =
        Calendar.getInstance().apply {
            add(Calendar.DAY_OF_YEAR, days)
            set(Calendar.HOUR_OF_DAY, 18)
            set(Calendar.MINUTE, 0)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }.timeInMillis

    val allTasks = mutableListOf(
        Task("Сделать прототип UI", "Разработать дизайн главной страницы в Figma, aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "layout_v1.png", 0, deadlineIn(1), R.drawable.default_avatar),
        Task("Построить вкусно и точка", "на пряниках нужна вкусно и точка", "penis.png", 1, deadlineIn(5), R.drawable.default_avatar),
        Task("3", "3 task", "task3.png", 2, deadlineIn(10), R.drawable.default_avatar),
        Task("4", "4 task", "task4.png", 3, deadlineIn(-1), R.drawable.default_avatar)
    )

    // Переводим в «Срочно» задачи, до дедлайна которых осталось URGENT_DAYS дней или меньше.
    // Задачи на проверке не трогаем, просроченные считаем срочными
    fun refreshUrgency() {
        allTasks.forEach { task ->
            val canBecomeUrgent = task.status == STATUS_IN_PROGRESS || task.status == STATUS_BACKLOG
            if (canBecomeUrgent && DeadlineUtils.daysLeft(task.deadlineTimestamp) <= URGENT_DAYS) {
                task.status = STATUS_URGENT
            }
        }
    }
}