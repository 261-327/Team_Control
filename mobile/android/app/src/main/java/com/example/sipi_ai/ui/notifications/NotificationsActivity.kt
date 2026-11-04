package com.example.sipi_ai.ui.notifications

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.isVisible
import androidx.recyclerview.widget.LinearLayoutManager
import com.example.sipi_ai.R
import com.example.sipi_ai.data.Task
import com.example.sipi_ai.data.TaskRepository
import com.example.sipi_ai.data.TaskStatus
import com.example.sipi_ai.databinding.ActivityNotificationsBinding
import com.example.sipi_ai.ui.common.openTask
import com.example.sipi_ai.ui.search.ResultAdapter
import com.example.sipi_ai.ui.search.ResultRow
import com.example.sipi_ai.data.ProjectRepository
import com.example.sipi_ai.util.daysUntil
import com.example.sipi_ai.util.formatDeadline

/** Уведомления выводятся из состояния задач: просрочено, срок сегодня/завтра, ждёт проверки. */
class NotificationsActivity : AppCompatActivity() {

    private lateinit var binding: ActivityNotificationsBinding
    private val adapter = ResultAdapter()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityNotificationsBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setSupportActionBar(binding.toolbarNotifications)
        supportActionBar?.setDisplayHomeAsUpEnabled(true)

        binding.rvNotifications.layoutManager = LinearLayoutManager(this)
        binding.rvNotifications.adapter = adapter
    }

    override fun onResume() {
        super.onResume()
        val rows = TaskRepository.mine().mapNotNull { toRow(it) }
        adapter.submitList(rows)
        binding.tvNotificationsEmpty.isVisible = rows.isEmpty()
    }

    override fun onSupportNavigateUp(): Boolean {
        finish()
        return true
    }

    private fun toRow(task: Task): ResultRow? {
        val deadline = task.deadlineMillis
        val textRes = when {
            task.status == TaskStatus.DONE -> return null
            task.status == TaskStatus.REVIEW -> R.string.notification_review
            TaskRepository.isOverdue(task) -> R.string.notification_overdue
            deadline != null && daysUntil(deadline) == 0 -> R.string.notification_today
            deadline != null && daysUntil(deadline) == 1 -> R.string.notification_tomorrow
            else -> return null
        }
        val project = ProjectRepository.get(task.projectId)
        val subtitle = listOfNotNull(
            project?.name,
            deadline?.let { formatDeadline(it) },
        ).joinToString(" · ")
        return ResultRow(
            key = "notification-${task.id}",
            title = getString(textRes, task.title),
            subtitle = subtitle,
            iconRes = R.drawable.ic_notifications,
            onClick = { openTask(task.id) },
        )
    }
}
