package com.example.sipi_ai.data

import com.example.sipi_ai.util.daysUntil
import com.example.sipi_ai.util.isSameDay
import com.example.sipi_ai.util.startOfDay
import java.util.Calendar

object TaskRepository {

    const val URGENT_DAYS_BEFORE_DEADLINE = 2

    private val tasks = mutableListOf<Task>()
    private val counters = mutableMapOf<Long, Int>()
    private var nextId = 1L

    init {
        create(
            projectId = 1, title = "Сделать прототип UI",
            description = "Разработать дизайн главной страницы в Figma: шапка, список задач, " +
                "нижняя навигация, пустое состояние списка и адаптация под маленькие экраны.",
            assigneeId = Members.ME_ID, deadlineMillis = deadlineInDays(1), direction = "Дизайн",
            status = TaskStatus.IN_PROGRESS, attachmentName = "layout_v1.png",
        )
        create(
            projectId = 1, title = "Подключить API задач",
            description = "Заменить тестовые данные на запросы к серверу.",
            assigneeId = Members.ME_ID, deadlineMillis = deadlineInDays(5), direction = "Разработка",
            status = TaskStatus.IN_PROGRESS, attachmentName = "api_contract.md",
        )
        create(
            projectId = 1, title = "Проверить экран календаря",
            description = "Пройтись по переключению месяцев и списку задач на день.",
            assigneeId = Members.ME_ID, deadlineMillis = deadlineInDays(10), direction = "Тестирование",
            status = TaskStatus.REVIEW,
        )
        create(
            projectId = 1, title = "Обновить иконку приложения",
            description = "Заменить стандартную иконку на логотип Сипи.",
            assigneeId = Members.ME_ID, deadlineMillis = deadlineInDays(-1), direction = "Дизайн",
            status = TaskStatus.TODO, attachmentName = "logo.svg",
        )
        create(
            projectId = 1, title = "Создать Android-приложение для трекера",
            description = "Разработать мобильное приложение на Android с функционалом учета задач, " +
                "включая локальное хранение данных и интеграция с веб-сайтом",
            assigneeId = null, deadlineMillis = null, direction = "Разработка",
            status = TaskStatus.TODO,
        )
        create(
            projectId = 1, title = "Создать веб-сайт для трекера",
            description = "Разработать веб-интерфейс с функционалом учета задач, проектов и команд.",
            assigneeId = null, deadlineMillis = null, direction = "Разработка",
            status = TaskStatus.REVIEW,
        )
        create(
            projectId = 1, title = "Создать iOS-приложение для трекера",
            description = "Разработать мобильное приложение на iOS с функционалом учета задач.",
            assigneeId = null, deadlineMillis = null, direction = "Разработка",
            status = TaskStatus.DONE,
        )
    }

    fun all(): List<Task> = tasks.toList()

    fun get(id: Long): Task? = tasks.firstOrNull { it.id == id }

    fun forProject(projectId: Long): List<Task> = tasks.filter { it.projectId == projectId }

    /** «Мои задачи» — те, где исполнитель текущий пользователь. */
    fun mine(): List<Task> = tasks.filter { it.assigneeId == Members.ME_ID }

    fun isUrgent(task: Task): Boolean {
        val deadline = task.deadlineMillis ?: return false
        val active = task.status == TaskStatus.TODO || task.status == TaskStatus.IN_PROGRESS
        return active && daysUntil(deadline) <= URGENT_DAYS_BEFORE_DEADLINE
    }

    fun isOverdue(task: Task, nowMillis: Long = System.currentTimeMillis()): Boolean {
        val deadline = task.deadlineMillis ?: return false
        return task.status != TaskStatus.DONE && deadline < nowMillis
    }

    fun isDueToday(task: Task): Boolean {
        val deadline = task.deadlineMillis ?: return false
        return task.status != TaskStatus.DONE && startOfDay(deadline).isSameDay(startOfDay())
    }

    fun belongsTo(task: Task, tab: TaskTab): Boolean = when (tab) {
        TaskTab.URGENT -> isUrgent(task)
        TaskTab.TODO -> task.status == TaskStatus.TODO && !isUrgent(task)
        TaskTab.IN_PROGRESS -> task.status == TaskStatus.IN_PROGRESS && !isUrgent(task)
        TaskTab.REVIEW -> task.status == TaskStatus.REVIEW
        TaskTab.DONE -> task.status == TaskStatus.DONE
    }

    fun mineIn(tab: TaskTab): List<Task> =
        mine().filter { belongsTo(it, tab) }.sortedBy { it.deadlineMillis ?: Long.MAX_VALUE }

    fun search(query: String): List<Task> {
        val q = query.trim()
        if (q.isEmpty()) return emptyList()
        return tasks.filter {
            it.title.contains(q, ignoreCase = true) || it.description.contains(q, ignoreCase = true)
        }
    }

    fun create(
        projectId: Long,
        title: String,
        description: String,
        assigneeId: Long?,
        deadlineMillis: Long?,
        direction: String,
        status: TaskStatus = TaskStatus.TODO,
        attachmentName: String? = null,
        authorId: Long = Members.ME_ID,
    ): Task {
        val now = System.currentTimeMillis()
        val task = Task(
            id = nextId++,
            projectId = projectId,
            number = nextNumber(projectId),
            title = title.trim(),
            description = description.trim(),
            status = status,
            deadlineMillis = deadlineMillis,
            direction = direction,
            assigneeId = assigneeId,
            authorId = authorId,
            createdMillis = now,
            attachmentName = attachmentName,
            history = listOf(HistoryEntry("Задача создана", now)),
        )
        tasks.add(task)
        return task
    }

    fun update(
        taskId: Long,
        projectId: Long,
        title: String,
        description: String,
        assigneeId: Long?,
        deadlineMillis: Long?,
        direction: String,
    ) {
        val index = tasks.indexOfFirst { it.id == taskId }
        if (index == -1) return
        val old = tasks[index]
        val now = System.currentTimeMillis()
        val log = mutableListOf<HistoryEntry>()
        if (old.title != title.trim()) log += HistoryEntry("Изменено название", now)
        if (old.description != description.trim()) log += HistoryEntry("Изменено описание", now)
        if (old.assigneeId != assigneeId) log += HistoryEntry("Изменён исполнитель", now)
        if (old.deadlineMillis != deadlineMillis) log += HistoryEntry("Изменён срок выполнения", now)
        if (old.direction != direction) log += HistoryEntry("Изменено направление", now)

        var number = old.number
        if (old.projectId != projectId) {
            number = nextNumber(projectId)
            log += HistoryEntry("Задача перенесена в другой проект", now)
        }

        tasks[index] = old.copy(
            projectId = projectId,
            number = number,
            title = title.trim(),
            description = description.trim(),
            assigneeId = assigneeId,
            deadlineMillis = deadlineMillis,
            direction = direction,
            history = old.history + log,
        )
    }

    fun updateStatus(taskId: Long, status: TaskStatus) {
        val index = tasks.indexOfFirst { it.id == taskId }
        if (index == -1) return
        val old = tasks[index]
        if (old.status == status) return
        val entry = HistoryEntry(
            "Статус: ${old.status.historyName()} → ${status.historyName()}",
            System.currentTimeMillis(),
        )
        tasks[index] = old.copy(status = status, history = old.history + entry)
    }

    fun addComment(taskId: Long, authorId: Long, text: String) {
        val index = tasks.indexOfFirst { it.id == taskId }
        if (index == -1 || text.isBlank()) return
        val old = tasks[index]
        val comment = Comment(authorId, text.trim(), System.currentTimeMillis())
        tasks[index] = old.copy(comments = old.comments + comment)
    }

    fun delete(taskId: Long) {
        tasks.removeAll { it.id == taskId }
    }

    fun deleteByProject(projectId: Long) {
        tasks.removeAll { it.projectId == projectId }
        counters.remove(projectId)
    }

    private fun nextNumber(projectId: Long): Int {
        val number = (counters[projectId] ?: 0) + 1
        counters[projectId] = number
        return number
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
