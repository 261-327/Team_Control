package com.example.sipi_ai.data

enum class TaskStatus {
    URGENT,
    IN_PROGRESS,
    REVIEW,
    BACKLOG,
}

data class Task(
    val id: Long,
    val title: String,
    val description: String,
    val status: TaskStatus,
    val deadlineMillis: Long,
    val attachmentName: String? = null,
)
