package com.example.sipi_ai.ui.team

import android.content.res.ColorStateList
import android.os.Bundle
import android.view.LayoutInflater
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.isVisible
import com.example.sipi_ai.R
import com.example.sipi_ai.data.Members
import com.example.sipi_ai.data.ProjectRepository
import com.example.sipi_ai.data.TaskRepository
import com.example.sipi_ai.data.TaskStatus
import com.example.sipi_ai.databinding.ActivityTeamOverviewBinding
import com.example.sipi_ai.databinding.ItemMemberBinding
import com.example.sipi_ai.databinding.ItemOverviewRowBinding
import com.example.sipi_ai.databinding.ItemSearchResultBinding
import com.example.sipi_ai.ui.common.MemberNames
import com.example.sipi_ai.ui.common.openProject
import com.example.sipi_ai.ui.common.openTask
import com.example.sipi_ai.ui.common.projectColorRes
import com.example.sipi_ai.ui.common.projectSoftColorRes
import com.example.sipi_ai.ui.common.showStats
import com.example.sipi_ai.util.formatDeadline
import com.example.sipi_ai.util.formatShortDate

/** «Обзор команд»: сводка по проектам, которые ведёт пользователь. */
class TeamOverviewActivity : AppCompatActivity() {

    private lateinit var binding: ActivityTeamOverviewBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityTeamOverviewBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setSupportActionBar(binding.toolbarOverview)
        supportActionBar?.setDisplayHomeAsUpEnabled(true)
    }

    override fun onResume() {
        super.onResume()
        render()
    }

    override fun onSupportNavigateUp(): Boolean {
        finish()
        return true
    }

    private fun render() {
        val inflater = LayoutInflater.from(this)
        val projects = ProjectRepository.all().filter { it.ownerId == Members.ME_ID }
        val tasks = projects.flatMap { TaskRepository.forProject(it.id) }

        binding.statsRowTop.showStats(
            listOf(
                R.string.stat_in_progress_and_plans to tasks.count {
                    it.status == TaskStatus.TODO || it.status == TaskStatus.IN_PROGRESS
                },
                R.string.stat_review to tasks.count { it.status == TaskStatus.REVIEW },
            ),
        )
        binding.statsRowBottom.showStats(
            listOf(
                R.string.stat_overdue to tasks.count { TaskRepository.isOverdue(it) },
                R.string.stat_done_total to tasks.count { it.status == TaskStatus.DONE },
            ),
        )

        // Состояние проектов
        binding.projectStateList.removeAllViews()
        for (project in projects) {
            val projectTasks = TaskRepository.forProject(project.id)
            val done = projectTasks.count { it.status == TaskStatus.DONE }
            val open = projectTasks.filter { it.status != TaskStatus.DONE }
            val percent = if (projectTasks.isEmpty()) 0 else done * 100 / projectTasks.size

            val row = ItemOverviewRowBinding.inflate(inflater, binding.projectStateList, false)
            row.ivRowIcon.setBackgroundResource(R.drawable.bg_avatar)
            row.ivRowIcon.backgroundTintList = ColorStateList.valueOf(getColor(projectSoftColorRes(project.colorIndex)))
            row.ivRowIcon.imageTintList = ColorStateList.valueOf(getColor(projectColorRes(project.colorIndex)))
            row.tvRowTitle.text = project.name
            row.tvRowSubtitle.text = getString(R.string.overview_project_line, open.size, done)
            row.progressRow.setProgressCompat(percent, false)
            row.tvRowValue.text = "$percent%"
            row.tvRowHint.text = when {
                open.isEmpty() -> getString(R.string.overview_no_open_tasks)
                else -> {
                    val next = open.mapNotNull { it.deadlineMillis }.minOrNull()
                    getString(
                        R.string.overview_next_deadline,
                        if (next == null) getString(R.string.task_no_deadline) else formatShortDate(next),
                    )
                }
            }
            row.root.setOnClickListener { openProject(project.id) }
            binding.projectStateList.addView(row.root)
        }

        // Задачи участников
        binding.memberTasksList.removeAllViews()
        val names = MemberNames(this)
        val byMember = tasks
            .filter { it.status != TaskStatus.DONE && it.assigneeId != null }
            .groupBy { it.assigneeId }
        for ((memberId, memberTasks) in byMember) {
            val row = ItemMemberBinding.inflate(inflater, binding.memberTasksList, false)
            row.tvMemberAvatar.text = names.initialsOf(memberId)
            row.tvMemberName.text = names.of(memberId)
            row.tvMemberRole.text = getString(R.string.overview_open_tasks_count, memberTasks.size)
            row.root.isClickable = false
            binding.memberTasksList.addView(row.root)
        }
        binding.tvMembersEmpty.isVisible = byMember.isEmpty()

        // Ближайшие дедлайны
        binding.deadlinesList.removeAllViews()
        val upcoming = tasks
            .filter { it.status != TaskStatus.DONE && it.deadlineMillis != null }
            .sortedBy { it.deadlineMillis }
            .take(5)
        for (task in upcoming) {
            val project = ProjectRepository.get(task.projectId)
            val row = ItemSearchResultBinding.inflate(inflater, binding.deadlinesList, false)
            row.ivResultIcon.setImageResource(R.drawable.ic_schedule)
            row.tvResultTitle.text = task.title
            row.tvResultSubtitle.text = listOfNotNull(
                project?.name,
                task.deadlineMillis?.let { formatDeadline(it) },
            ).joinToString(" · ")
            row.root.setOnClickListener { openTask(task.id) }
            binding.deadlinesList.addView(row.root)
        }
        binding.tvDeadlinesEmpty.isVisible = upcoming.isEmpty()
    }
}
