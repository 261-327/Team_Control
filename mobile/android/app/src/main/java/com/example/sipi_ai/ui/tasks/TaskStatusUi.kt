package com.example.sipi_ai.ui.tasks

import androidx.annotation.ColorRes
import androidx.annotation.StringRes
import com.example.sipi_ai.R
import com.example.sipi_ai.data.Task
import com.example.sipi_ai.data.TaskRepository
import com.example.sipi_ai.data.TaskStatus
import com.example.sipi_ai.data.TaskTab

data class StatusStyle(
    @StringRes val label: Int,
    @ColorRes val color: Int,
    @ColorRes val background: Int,
)

private val URGENT_STYLE = StatusStyle(R.string.status_urgent, R.color.status_urgent, R.color.status_urgent_bg)
private val OVERDUE_STYLE = StatusStyle(R.string.task_overdue_label, R.color.status_urgent, R.color.status_urgent_bg)

val TaskStatus.style: StatusStyle
    get() = when (this) {
        TaskStatus.TODO -> StatusStyle(R.string.status_todo, R.color.status_backlog, R.color.status_backlog_bg)
        TaskStatus.IN_PROGRESS -> StatusStyle(R.string.status_in_progress, R.color.status_in_progress, R.color.status_in_progress_bg)
        TaskStatus.REVIEW -> StatusStyle(R.string.status_review, R.color.status_review, R.color.status_review_bg)
        TaskStatus.DONE -> StatusStyle(R.string.status_done, R.color.status_done, R.color.status_done_bg)
    }

/** Статусы «На проверке» и «Готово» важнее срочности; у остальных задач показываем срок. */
val Task.displayStyle: StatusStyle
    get() = when (status) {
        TaskStatus.REVIEW, TaskStatus.DONE -> status.style
        else -> when {
            TaskRepository.isOverdue(this) -> OVERDUE_STYLE
            TaskRepository.isUrgent(this) -> URGENT_STYLE
            else -> status.style
        }
    }

val TaskTab.tabTitleRes: Int
    get() = when (this) {
        TaskTab.URGENT -> R.string.tab_urgent
        TaskTab.TODO -> R.string.tab_todo
        TaskTab.IN_PROGRESS -> R.string.tab_in_progress
        TaskTab.REVIEW -> R.string.tab_review
        TaskTab.DONE -> R.string.tab_done
    }
