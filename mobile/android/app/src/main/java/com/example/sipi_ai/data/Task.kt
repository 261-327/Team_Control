package com.example.sipi_ai.data

/** Статусы, как на доске веба: К выполнению → В работе → На проверке → Готово. */
enum class TaskStatus { TODO, IN_PROGRESS, REVIEW, DONE }

/**
 * Вкладки главного экрана. «Срочно» не хранится в задаче, а вычисляется по сроку
 * (см. [TaskRepository.isUrgent]).
 */
enum class TaskTab { URGENT, TODO, IN_PROGRESS, REVIEW, DONE }

object Members {
    /** Текущий пользователь (тот, кто зарегистрировался в приложении). */
    const val ME_ID = 0L
}

object Directions {
    const val TEAM = "Команда"
    val all = listOf(TEAM, "Разработка", "Дизайн", "Тестирование", "Документация")
}

data class Comment(
    val authorId: Long,
    val text: String,
    val createdMillis: Long,
)

data class HistoryEntry(
    val text: String,
    val createdMillis: Long,
)

data class Task(
    val id: Long,
    val projectId: Long,
    /** Порядковый номер в проекте: вместе с ключом проекта даёт код вида SIP-6. */
    val number: Int,
    val title: String,
    val description: String,
    val status: TaskStatus,
    /** null — «Без срока». */
    val deadlineMillis: Long?,
    val direction: String = Directions.TEAM,
    /** null — «Нужно назначить». */
    val assigneeId: Long? = null,
    val authorId: Long = Members.ME_ID,
    val createdMillis: Long = System.currentTimeMillis(),
    val attachmentName: String? = null,
    val comments: List<Comment> = emptyList(),
    val history: List<HistoryEntry> = emptyList(),
)

fun TaskStatus.historyName(): String = when (this) {
    TaskStatus.TODO -> "К выполнению"
    TaskStatus.IN_PROGRESS -> "В работе"
    TaskStatus.REVIEW -> "На проверке"
    TaskStatus.DONE -> "Готово"
}
