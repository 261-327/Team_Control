package com.example.sipisanzhapov

data class Task(
    val title: String,
    val description: String,
    val fileName: String? = null,
    val status: Int,
    val assigneeAvatarRes: Int // Ресурс аватарки (например, R.drawable.default_avatar)
)