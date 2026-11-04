package com.example.sipi_ai.ui.taskdetail

import android.content.Context
import android.content.Intent
import android.content.res.ColorStateList
import android.os.Bundle
import android.view.Menu
import android.view.MenuItem
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.isVisible
import androidx.core.widget.doAfterTextChanged
import androidx.recyclerview.widget.LinearLayoutManager
import com.example.sipi_ai.R
import com.example.sipi_ai.data.Members
import com.example.sipi_ai.data.ProjectRepository
import com.example.sipi_ai.data.TaskRepository
import com.example.sipi_ai.data.TaskStatus
import com.example.sipi_ai.databinding.ActivityTaskDetailBinding
import com.example.sipi_ai.ui.common.MemberNames
import com.example.sipi_ai.ui.taskedit.TaskEditActivity
import com.example.sipi_ai.ui.tasks.style
import com.example.sipi_ai.util.formatDeadline
import com.example.sipi_ai.util.formatShortDate
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.android.material.tabs.TabLayout

class TaskDetailActivity : AppCompatActivity() {

    private lateinit var binding: ActivityTaskDetailBinding
    private var taskId = -1L
    private var showHistory = false

    private val commentAdapter = CommentAdapter()
    private val historyAdapter = HistoryAdapter()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityTaskDetailBinding.inflate(layoutInflater)
        setContentView(binding.root)
        taskId = intent.getLongExtra(EXTRA_TASK_ID, -1L)

        setSupportActionBar(binding.toolbarTask)
        supportActionBar?.setDisplayHomeAsUpEnabled(true)

        binding.rvDiscussion.layoutManager = LinearLayoutManager(this)

        binding.tabDiscussion.addTab(binding.tabDiscussion.newTab())
        binding.tabDiscussion.addTab(binding.tabDiscussion.newTab())
        binding.tabDiscussion.addOnTabSelectedListener(object : TabLayout.OnTabSelectedListener {
            override fun onTabSelected(tab: TabLayout.Tab) {
                showHistory = tab.position == 1
                renderDiscussion()
            }

            override fun onTabUnselected(tab: TabLayout.Tab) = Unit
            override fun onTabReselected(tab: TabLayout.Tab) = Unit
        })

        binding.etComment.doAfterTextChanged {
            val length = it?.length ?: 0
            binding.tvCommentCounter.text = getString(R.string.task_comment_counter, length)
            binding.btnSendComment.isEnabled = it?.isNotBlank() == true
        }
        binding.tvCommentCounter.text = getString(R.string.task_comment_counter, 0)
        binding.btnSendComment.isEnabled = false
        binding.btnSendComment.setOnClickListener { sendComment() }

        binding.tvStatus.setOnClickListener { showStatusDialog() }
        binding.btnChangeStatus.setOnClickListener { showStatusDialog() }
    }

    override fun onResume() {
        super.onResume()
        render()
    }

    override fun onCreateOptionsMenu(menu: Menu): Boolean {
        menuInflater.inflate(R.menu.menu_task_detail, menu)
        return true
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean = when (item.itemId) {
        R.id.action_edit -> {
            startActivity(TaskEditActivity.intent(this, taskId, null))
            true
        }
        R.id.action_delete -> {
            confirmDelete()
            true
        }
        else -> super.onOptionsItemSelected(item)
    }

    override fun onSupportNavigateUp(): Boolean {
        finish()
        return true
    }

    private fun render() {
        val task = TaskRepository.get(taskId)
        if (task == null) {
            Toast.makeText(this, R.string.task_not_found, Toast.LENGTH_SHORT).show()
            finish()
            return
        }
        val project = ProjectRepository.get(task.projectId)
        val names = MemberNames(this)
        val code = if (project != null) "${project.key}-${task.number}" else "#${task.number}"

        binding.tvTaskCode.text = "${getString(R.string.task_screen_title)} · $code".uppercase()
        binding.tvTaskTitle.text = task.title

        val style = task.status.style
        binding.tvStatus.setText(style.label)
        binding.tvStatus.setTextColor(getColor(style.color))
        binding.tvStatus.backgroundTintList = ColorStateList.valueOf(getColor(style.background))
        binding.tvDirectionChip.text = task.direction
        binding.tvCreated.text = getString(R.string.task_created, formatShortDate(task.createdMillis))

        binding.tvDescription.text = task.description.ifEmpty { getString(R.string.task_no_description) }
        binding.tvAssignee.text = names.of(task.assigneeId)
        binding.tvDue.text = task.deadlineMillis?.let { formatDeadline(it) } ?: getString(R.string.task_no_deadline)
        binding.tvProject.text = project?.name ?: "—"
        binding.tvAuthor.text = names.of(task.authorId)
        binding.tvDirection.text = task.direction

        binding.tabDiscussion.getTabAt(0)?.text = "${getString(R.string.task_discussion)}  ${task.comments.size}"
        binding.tabDiscussion.getTabAt(1)?.text = "${getString(R.string.task_history)}  ${task.history.size}"
        renderDiscussion()
    }

    private fun renderDiscussion() {
        val task = TaskRepository.get(taskId) ?: return
        if (showHistory) {
            binding.rvDiscussion.adapter = historyAdapter
            historyAdapter.submitList(task.history.reversed())
            binding.tvEmptyDiscussion.isVisible = false
            binding.commentForm.isVisible = false
        } else {
            binding.rvDiscussion.adapter = commentAdapter
            commentAdapter.submitList(task.comments)
            binding.tvEmptyDiscussion.isVisible = task.comments.isEmpty()
            binding.commentForm.isVisible = true
        }
        binding.rvDiscussion.isVisible = showHistory || task.comments.isNotEmpty()
    }

    private fun sendComment() {
        val text = binding.etComment.text.toString()
        if (text.isBlank()) return
        TaskRepository.addComment(taskId, Members.ME_ID, text)
        binding.etComment.text?.clear()
        render()
    }

    private fun showStatusDialog() {
        val task = TaskRepository.get(taskId) ?: return
        val statuses = TaskStatus.entries
        val labels = statuses.map { getString(it.style.label) }.toTypedArray()
        MaterialAlertDialogBuilder(this)
            .setTitle(R.string.task_change_status)
            .setSingleChoiceItems(labels, statuses.indexOf(task.status)) { dialog, which ->
                TaskRepository.updateStatus(taskId, statuses[which])
                dialog.dismiss()
                render()
            }
            .setNegativeButton(R.string.action_cancel, null)
            .show()
    }

    private fun confirmDelete() {
        val task = TaskRepository.get(taskId) ?: return
        MaterialAlertDialogBuilder(this)
            .setTitle(R.string.task_delete_title)
            .setMessage(getString(R.string.task_delete_message, task.title))
            .setNegativeButton(R.string.action_cancel, null)
            .setPositiveButton(R.string.action_delete) { _, _ ->
                TaskRepository.delete(taskId)
                Toast.makeText(this, R.string.task_deleted, Toast.LENGTH_SHORT).show()
                finish()
            }
            .show()
    }

    companion object {
        private const val EXTRA_TASK_ID = "task_id"

        fun intent(context: Context, taskId: Long): Intent =
            Intent(context, TaskDetailActivity::class.java).putExtra(EXTRA_TASK_ID, taskId)
    }
}
