package com.example.sipisanzhapov



object TaskRepository {
    val allTasks = mutableListOf(
        Task("Сделать прототип UI", "Разработать дизайн главной страницы в Figma", "layout_v1.png", 0, R.drawable.default_avatar),
        Task("Построить вкусно и точка", "на пряниках нужна вкусно и точка", "penis.png", 1, R.drawable.default_avatar),
        Task("3","3 task", "task3.png", 2, R.drawable.default_avatar),
        Task("4", "4 task","task4.png", 3, R.drawable.default_avatar )

    )
}