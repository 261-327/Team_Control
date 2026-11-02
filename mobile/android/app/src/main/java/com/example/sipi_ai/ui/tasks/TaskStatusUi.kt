package com.example.sipi_ai.ui.tasks

import com.example.sipi_ai.R
import com.example.sipi_ai.data.TaskStatus

val TaskStatus.tabTitleRes: Int
    get() = when (this) {
        TaskStatus.URGENT -> R.string.tab_urgent
        TaskStatus.IN_PROGRESS -> R.string.tab_in_progress
        TaskStatus.REVIEW -> R.string.tab_review
        TaskStatus.BACKLOG -> R.string.tab_backlog
    }

val TaskStatus.labelRes: Int
    get() = when (this) {
        TaskStatus.URGENT -> R.string.status_urgent
        TaskStatus.IN_PROGRESS -> R.string.status_in_progress
        TaskStatus.REVIEW -> R.string.status_review
        TaskStatus.BACKLOG -> R.string.status_backlog
    }

val TaskStatus.colorRes: Int
    get() = when (this) {
        TaskStatus.URGENT -> R.color.status_urgent
        TaskStatus.IN_PROGRESS -> R.color.status_in_progress
        TaskStatus.REVIEW -> R.color.status_review
        TaskStatus.BACKLOG -> R.color.status_backlog
    }

val TaskStatus.backgroundColorRes: Int
    get() = when (this) {
        TaskStatus.URGENT -> R.color.status_urgent_bg
        TaskStatus.IN_PROGRESS -> R.color.status_in_progress_bg
        TaskStatus.REVIEW -> R.color.status_review_bg
        TaskStatus.BACKLOG -> R.color.status_backlog_bg
    }
