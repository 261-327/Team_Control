package com.example.sipi_ai.ui.projects

import android.content.res.ColorStateList
import android.os.Bundle
import android.view.View
import androidx.core.os.bundleOf
import androidx.core.view.isVisible
import androidx.core.widget.ImageViewCompat
import androidx.core.widget.doAfterTextChanged
import androidx.fragment.app.Fragment
import androidx.recyclerview.widget.LinearLayoutManager
import com.example.sipi_ai.R
import com.example.sipi_ai.data.Directions
import com.example.sipi_ai.data.ApiClient
import com.example.sipi_ai.data.Task
import com.example.sipi_ai.data.TaskRepository
import com.example.sipi_ai.data.TaskStatus
import com.example.sipi_ai.data.UserStore
import com.example.sipi_ai.databinding.FragmentProjectTasksBinding
import com.example.sipi_ai.databinding.ViewBoardColumnBinding
import com.example.sipi_ai.ui.common.openTask
import com.example.sipi_ai.ui.tasks.TaskAdapter
import com.example.sipi_ai.ui.tasks.style
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.android.material.snackbar.Snackbar

/** Вкладка «Задачи»: доска из четырёх колонок или обычный список, поиск и фильтр по направлению. */
class ProjectTasksFragment : Fragment(R.layout.fragment_project_tasks) {

    private var binding: FragmentProjectTasksBinding? = null
    private val projectId by lazy { requireArguments().getLong(ARG_PROJECT_ID) }

    private var query = ""
    private var direction: String? = null
    private var listMode = false

    private val listAdapter = TaskAdapter(onClick = { task -> requireContext().openTask(task.id) })
    private val columnAdapters = TaskStatus.entries.associateWith {
        BoardCardAdapter(
            onOpen = { task -> requireContext().openTask(task.id) },
            onMove = { task, status -> move(task, status) },
            onDelete = { task -> confirmDelete(task) },
        )
    }
    private val columns = mutableMapOf<TaskStatus, ViewBoardColumnBinding>()

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        val b = FragmentProjectTasksBinding.bind(view)
        binding = b

        columns.clear()
        for (status in TaskStatus.entries) {
            val column = ViewBoardColumnBinding.inflate(layoutInflater, b.boardColumns, false)
            column.tvColumnTitle.setText(status.style.label)
            column.ivColumnIcon.setImageResource(columnIcon(status))
            ImageViewCompat.setImageTintList(
                column.ivColumnIcon,
                ColorStateList.valueOf(requireContext().getColor(status.style.color)),
            )
            column.rvColumn.layoutManager = LinearLayoutManager(requireContext())
            column.rvColumn.adapter = columnAdapters.getValue(status)
            b.boardColumns.addView(column.root)
            columns[status] = column
        }

        b.rvTaskList.layoutManager = LinearLayoutManager(requireContext())
        b.rvTaskList.adapter = listAdapter

        b.etSearchTask.doAfterTextChanged {
            query = it?.toString().orEmpty().trim()
            render()
        }
        b.btnFilters.setOnClickListener { showFilters() }
        b.toggleMode.addOnButtonCheckedListener { _, checkedId, isChecked ->
            if (isChecked) {
                listMode = checkedId == R.id.btnModeList
                render()
            }
        }
        render()
    }

    override fun onResume() {
        super.onResume()
        render()
    }

    override fun onDestroyView() {
        binding?.rvTaskList?.adapter = null
        for (column in columns.values) column.rvColumn.adapter = null
        columns.clear()
        binding = null
        super.onDestroyView()
    }

    private fun render() {
        val b = binding ?: return
        val tasks = TaskRepository.forProject(projectId)
            .filter { direction == null || it.direction == direction }
            .filter {
                query.isEmpty() ||
                    it.title.contains(query, ignoreCase = true) ||
                    it.description.contains(query, ignoreCase = true)
            }
            .sortedBy { it.deadlineMillis ?: Long.MAX_VALUE }

        for (status in TaskStatus.entries) {
            val inColumn = tasks.filter { it.status == status }
            val column = columns[status] ?: continue
            columnAdapters.getValue(status).submitList(inColumn)
            column.tvColumnCount.text = inColumn.size.toString()
            column.tvColumnEmpty.isVisible = inColumn.isEmpty()
        }
        listAdapter.submitList(tasks.sortedBy { it.status.ordinal })

        b.boardScroll.isVisible = !listMode
        b.rvTaskList.isVisible = listMode
        b.btnFilters.setText(if (direction == null) R.string.board_filters else R.string.board_filters_active)
        (activity as? ProjectActivity)?.refreshHeader()
    }

    private fun showFilters() {
        val labels = (listOf(getString(R.string.board_filter_all)) + Directions.all).toTypedArray()
        val checked = direction?.let { Directions.all.indexOf(it) + 1 } ?: 0
        MaterialAlertDialogBuilder(requireContext())
            .setTitle(R.string.board_filter_title)
            .setSingleChoiceItems(labels, checked) { dialog, which ->
                direction = if (which == 0) null else Directions.all[which - 1]
                dialog.dismiss()
                render()
            }
            .setNegativeButton(R.string.action_cancel, null)
            .show()
    }

    private fun move(task: Task, status: TaskStatus) {
        val previous = task.status
        val wire = status.toWireStatus()
        val reason = if (previous == TaskStatus.REVIEW && status == TaskStatus.IN_PROGRESS)
            "Исправления отмечены в приложении" else null
        ApiClient.moveTask(task.id, wire, { response ->
            response.onSuccess {
                ApiClient.applyMutation(it, UserStore(requireContext()))
                render()
                Snackbar.make(requireView(), getString(R.string.task_moved, getString(status.style.label)), Snackbar.LENGTH_LONG)
                    .setAction(R.string.action_undo) {
                        val undoReason = if (status == TaskStatus.REVIEW && previous == TaskStatus.IN_PROGRESS)
                            "Возврат статуса" else null
                        ApiClient.moveTask(task.id, previous.toWireStatus(), { undo ->
                            undo.onSuccess {
                                ApiClient.applyMutation(it, UserStore(requireContext()))
                                render()
                            }.onFailure { Snackbar.make(requireView(), it.message ?: "Не удалось отменить перенос", Snackbar.LENGTH_LONG).show() }
                        }, undoReason)
                    }.show()
            }.onFailure { Snackbar.make(requireView(), it.message ?: "Не удалось переместить задачу", Snackbar.LENGTH_LONG).show() }
        }, reason)
    }

    private fun confirmDelete(task: Task) {
        MaterialAlertDialogBuilder(requireContext())
            .setTitle(R.string.task_delete_title)
            .setMessage(getString(R.string.task_delete_message, task.title))
            .setNegativeButton(R.string.action_cancel, null)
            .setPositiveButton(R.string.action_delete) { _, _ ->
                ApiClient.deleteTask(task.id) { result ->
                    result.onSuccess {
                        ApiClient.applyMutation(it, UserStore(requireContext()))
                        render()
                    }.onFailure { Snackbar.make(requireView(), it.message ?: "Не удалось удалить задачу", Snackbar.LENGTH_LONG).show() }
                }
            }
            .show()
    }

    private fun columnIcon(status: TaskStatus): Int = when (status) {
        TaskStatus.TODO -> R.drawable.ic_todo
        TaskStatus.IN_PROGRESS -> R.drawable.ic_autorenew
        TaskStatus.REVIEW -> R.drawable.ic_assignment
        TaskStatus.DONE -> R.drawable.ic_check_circle
    }

    private fun TaskStatus.toWireStatus(): String = when (this) {
        TaskStatus.TODO -> "todo"
        TaskStatus.IN_PROGRESS -> "in_progress"
        TaskStatus.REVIEW -> "in_review"
        TaskStatus.DONE -> "done"
    }

    companion object {
        private const val ARG_PROJECT_ID = "project_id"

        fun newInstance(projectId: Long) = ProjectTasksFragment().apply {
            arguments = bundleOf(ARG_PROJECT_ID to projectId)
        }
    }
}
