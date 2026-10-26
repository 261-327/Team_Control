package com.example.sipisanzhapov

// Статусы задач: 0 — срочно, 1 — в процессе, 2 — ревью, 3 — бэклог
const val STATUS_REVIEW = 2

data class Task(
    val title: String,
    val description: String,
    val fileName: String? = null,
    var status: Int,
    val deadlineTimestamp: Long,
    val assigneeAvatarRes: Int // Ресурс аватарки (например, R.drawable.default_avatar)
)