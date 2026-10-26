package com.example.sipi_ai.data

import com.example.sipi_ai.util.daysUntil
import java.util.Calendar

object TaskRepository {

    const val URGENT_DAYS_BEFORE_DEADLINE = 2
    private val statusesPromotedToUrgent = setOf(TaskStatus.IN_PROGRESS, TaskStatus.BACKLOG)

    private val tasks = mutableListOf(
        Task(
            id = 1,
            title = "Сделать прототип UI",
            description = "Разработать дизайн главной страницы в Figma: шапка, список задач, " +
                "нижняя навигация, пустое состояние списка и адаптация под маленькие экраны.",
            status = TaskStatus.URGENT,
            deadlineMillis = deadlineInDays(1),
            attachmentName = "layout_v1.png",
        ),
        Task(
            id = 2,
            title = "Подключить API задач",
            description = "Заменить тестовые данные на запросы к серверу.",
            status = TaskStatus.IN_PROGRESS,
            deadlineMillis = deadlineInDays(5),
            attachmentName = "api_contract.md",
        ),
        Task(
            id = 3,
            title = "Проверить экран календаря",
            description = "Пройтись по переключению месяцев и списку задач на день.",
            status = TaskStatus.REVIEW,
            deadlineMillis = deadlineInDays(10),
        ),
        Task(
            id = 4,
            title = "Обновить иконку приложения",
            description = "Заменить стандартную иконку на логотип Сипи.",
            status = TaskStatus.BACKLOG,
            deadlineMillis = deadlineInDays(-1),
            attachmentName = "logo.svg",
        ),
    )

    //Ты что реально читаешь PR? У тебя ребятки слабенькие(
    fun all(): List<Task> {
        promoteTasksNearDeadline()
        return tasks.toList()
    }

    fun withStatus(status: TaskStatus): List<Task> = all().filter { it.status == status }

    fun updateStatus(taskId: Long, status: TaskStatus) {
        val index = tasks.indexOfFirst { it.id == taskId }
        if (index != -1) tasks[index] = tasks[index].copy(status = status)
    }

    private fun promoteTasksNearDeadline() {
        for (index in tasks.indices) {
            val task = tasks[index]
            val isNearDeadline = daysUntil(task.deadlineMillis) <= URGENT_DAYS_BEFORE_DEADLINE
            if (task.status in statusesPromotedToUrgent && isNearDeadline) {
                tasks[index] = task.copy(status = TaskStatus.URGENT)
            }
        }
    }

    private fun deadlineInDays(days: Int): Long =
        Calendar.getInstance().apply {
            add(Calendar.DAY_OF_YEAR, days)
            set(Calendar.HOUR_OF_DAY, 18)
            set(Calendar.MINUTE, 0)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }.timeInMillis
}
