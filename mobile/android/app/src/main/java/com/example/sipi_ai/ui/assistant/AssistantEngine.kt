package com.example.sipi_ai.ui.assistant

import com.example.sipi_ai.data.Directions
import com.example.sipi_ai.data.Members
import com.example.sipi_ai.data.ProjectRepository
import com.example.sipi_ai.data.Task
import com.example.sipi_ai.data.TaskRepository
import com.example.sipi_ai.data.TaskStatus
import com.example.sipi_ai.util.formatDeadline
import com.example.sipi_ai.util.russianPlural

enum class AssistantMode { ASSISTANT, DRAFTS }

data class AssistantReply(
    val text: String,
    /** Черновики задач, которые можно добавить на доску кнопкой в сообщении. */
    val drafts: List<String> = emptyList(),
)

/**
 * Локальный помощник без сервера: понимает несколько команд из подсказок сайта
 * («Что осталось до сдачи?», «Создай проект «Название» — идея. Добавь 5 задач…»)
 * и умеет превращать текст в черновики задач.
 */
object AssistantEngine {

    private const val MAX_TASKS = 10

    private val starterTasks = listOf(
        "Сформулировать цель и задачи проекта",
        "Распределить роли в команде",
        "Составить план работ по неделям",
        "Подготовить первую версию результата",
        "Провести тестирование и собрать обратную связь",
        "Подготовить презентацию и защиту",
        "Оформить итоговую документацию",
    )

    private val createProjectRegex =
        Regex("""созда\p{L}*\s+проект\s*[«"“]([^»"”]+)[»"”]?\s*(?:[—–-]\s*(.*))?""", setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL))
    private val addTasksRegex = Regex("""добав\p{L}*\s+(\d+)\s+задач""", RegexOption.IGNORE_CASE)
    private val trailingAddTasksRegex =
        Regex("""\s*добав\p{L}*\s+\d+\s+задач.*$""", setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL))

    fun reply(input: String, mode: AssistantMode, projectId: Long?): AssistantReply =
        when (mode) {
            AssistantMode.DRAFTS -> draftsReply(input)
            AssistantMode.ASSISTANT -> assistantReply(input, projectId)
        }

    /** Добавляет черновики на доску проекта. Возвращает число созданных задач. */
    fun addDrafts(drafts: List<String>, projectId: Long?): Int {
        val project = (projectId?.let { ProjectRepository.get(it) } ?: ProjectRepository.all().firstOrNull())
            ?: return 0
        drafts.forEach { createTask(project.id, it) }
        return drafts.size
    }

    private fun assistantReply(input: String, projectId: Long?): AssistantReply {
        val text = input.trim()

        val create = createProjectRegex.find(text)
        if (create != null) {
            val name = create.groupValues[1].trim()
            if (name.isEmpty()) return AssistantReply("Напиши название проекта в кавычках: Создай проект «Название».")
            val rawIdea = create.groupValues.getOrNull(2).orEmpty()
            val idea = rawIdea.replace(trailingAddTasksRegex, "").trim()
            val project = ProjectRepository.create(name, idea)
            val count = addTasksRegex.find(text)?.groupValues?.get(1)?.toIntOrNull()?.coerceIn(0, MAX_TASKS) ?: 0
            val created = (0 until count).map { starterTasks[it % starterTasks.size] }
            created.forEach { createTask(project.id, it) }

            val tasksPart = if (created.isEmpty()) "" else
                "\nДобавил на доску ${tasksWord(created.size)}:\n" + created.joinToString("\n") { "• $it" }
            return AssistantReply("Создал проект «${project.name}» (${project.key}).$tasksPart")
        }

        val add = addTasksRegex.find(text)
        if (add != null) {
            val project = projectId?.let { ProjectRepository.get(it) }
                ?: return AssistantReply("Чтобы добавить задачи, выбери проект в поле «Контекст».")
            val count = (add.groupValues[1].toIntOrNull() ?: 0).coerceIn(1, MAX_TASKS)
            val created = (0 until count).map { starterTasks[it % starterTasks.size] }
            created.forEach { createTask(project.id, it) }
            return AssistantReply(
                "Добавил в «${project.name}» ${tasksWord(count)}:\n" + created.joinToString("\n") { "• $it" },
            )
        }

        val lower = text.lowercase()
        if (listOf("осталось", "сдач", "дедлайн", "срок").any { it in lower }) {
            return AssistantReply(deadlinesSummary(projectId))
        }

        return AssistantReply(
            "Я могу:\n" +
                "• рассказать, что осталось до сдачи;\n" +
                "• создать проект: «Создай проект «Название» — идея. Добавь 5 задач»;\n" +
                "• добавить задачи в выбранный проект: «Добавь 3 задачи»;\n" +
                "• в режиме «Черновик задач» превратить текст в список задач.",
        )
    }

    private fun draftsReply(input: String): AssistantReply {
        var items = input.lines()
            .map { it.trim().trimStart('-', '•', '*', '–', '—').replace(Regex("""^\d+[.)]\s*"""), "").trim() }
            .filter { it.isNotEmpty() }
        if (items.size == 1) {
            items = items[0].split(Regex("""(?<=[.!?])\s+""")).map { it.trim().trimEnd('.') }.filter { it.isNotEmpty() }
        }
        items = items.take(15).map { it.take(120) }
        if (items.isEmpty()) return AssistantReply("Опиши работу — каждая строка станет отдельной задачей.")
        return AssistantReply(
            "Подготовил ${draftsWord(items.size)}:\n" + items.mapIndexed { i, t -> "${i + 1}. $t" }.joinToString("\n"),
            drafts = items,
        )
    }

    private fun deadlinesSummary(projectId: Long?): String {
        val scope = projectId?.let { TaskRepository.forProject(it) } ?: TaskRepository.all()
        val open = scope.filter { it.status != TaskStatus.DONE }
        if (open.isEmpty()) return "Все задачи выполнены — до сдачи ничего не осталось."

        val overdue = open.count { TaskRepository.isOverdue(it) }
        val builder = StringBuilder()
        builder.append("До сдачи осталось ${tasksWord(open.size)} из ${scope.size}.")
        builder.append("\nК выполнению: ${open.count { it.status == TaskStatus.TODO }}, ")
        builder.append("в работе: ${open.count { it.status == TaskStatus.IN_PROGRESS }}, ")
        builder.append("на проверке: ${open.count { it.status == TaskStatus.REVIEW }}.")
        if (overdue > 0) builder.append("\nПросрочено: $overdue.")

        val nearest = open.filter { it.deadlineMillis != null }.sortedBy { it.deadlineMillis }.take(5)
        if (nearest.isNotEmpty()) {
            builder.append("\n\nБлижайшие сроки:")
            nearest.forEach { builder.append("\n• ${it.title} — ${formatDeadline(it.deadlineMillis!!)}") }
        } else {
            builder.append("\n\nУ открытых задач пока нет сроков.")
        }
        return builder.toString()
    }

    private fun createTask(projectId: Long, title: String): Task =
        TaskRepository.create(
            projectId = projectId,
            title = title,
            description = "",
            assigneeId = Members.ME_ID,
            deadlineMillis = null,
            direction = Directions.TEAM,
        )

    private fun tasksWord(count: Int): String =
        "$count " + russianPlural(count, "задачу", "задачи", "задач")

    private fun draftsWord(count: Int): String =
        "$count " + russianPlural(count, "черновик задачи", "черновика задач", "черновиков задач")
}
