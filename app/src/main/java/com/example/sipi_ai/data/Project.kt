package com.example.sipi_ai.data

data class Member(val id: Long, val name: String)

data class Project(
    val id: Long,
    /** Короткий ключ для кодов задач: SIP-1, SIP-2… */
    val key: String,
    val name: String,
    val description: String,
    val season: String,
    val colorIndex: Int,
    /** Участники проекта. Текущий пользователь всегда [Members.ME_ID]. */
    val memberIds: List<Long> = listOf(Members.ME_ID),
    val ownerId: Long = Members.ME_ID,
    /** Имена файлов, добавленных во вкладку «Материалы». */
    val materials: List<String> = emptyList(),
)
