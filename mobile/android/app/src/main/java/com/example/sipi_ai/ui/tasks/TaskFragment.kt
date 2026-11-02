package com.example.sipi_ai.ui.tasks

import android.os.Bundle
import android.view.View
import androidx.core.os.bundleOf
import androidx.core.view.isVisible
import androidx.fragment.app.Fragment
import androidx.recyclerview.widget.LinearLayoutManager
import com.example.sipi_ai.R
import com.example.sipi_ai.data.Task
import com.example.sipi_ai.data.TaskRepository
import com.example.sipi_ai.data.TaskStatus
import com.example.sipi_ai.databinding.FragmentTaskBinding
import com.example.sipi_ai.util.russianPlural
import com.google.android.material.snackbar.Snackbar

class TaskFragment : Fragment(R.layout.fragment_task) {

    private val status by lazy { TaskStatus.entries[requireArguments().getInt(ARG_STATUS)] }
    private val taskAdapter = TaskAdapter { task -> submitForReview(task) }
    private var binding: FragmentTaskBinding? = null

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        binding = FragmentTaskBinding.bind(view).apply {
            tvTabTitle.setText(status.tabTitleRes)
            recyclerViewTasks.layoutManager = LinearLayoutManager(requireContext())
            recyclerViewTasks.adapter = taskAdapter
        }
        showTasks()
    }

    override fun onResume() {
        super.onResume()
        showTasks()
    }

    override fun onDestroyView() {
        binding?.recyclerViewTasks?.adapter = null
        binding = null
        super.onDestroyView()
    }

    private fun showTasks() {
        val binding = binding ?: return
        val tasks = TaskRepository.withStatus(status)
        taskAdapter.submitList(tasks)

        val countPhrase = russianPlural(
            tasks.size,
            one = R.string.tasks_count_one,
            few = R.string.tasks_count_few,
            many = R.string.tasks_count_many,
        )
        binding.tvTaskCount.text = getString(countPhrase, tasks.size)
        binding.tvTaskCount.isVisible = tasks.isNotEmpty()
        binding.emptyState.isVisible = tasks.isEmpty()
        binding.recyclerViewTasks.isVisible = tasks.isNotEmpty()
    }

    private fun submitForReview(task: Task) {
        TaskRepository.updateStatus(task.id, TaskStatus.REVIEW)
        showTasks()

        Snackbar.make(requireView(), R.string.task_submitted, Snackbar.LENGTH_LONG)
            .setAnchorView(requireActivity().findViewById<View>(R.id.bottomNavigationView))
            .setAction(R.string.action_undo) {
                TaskRepository.updateStatus(task.id, task.status)
                showTasks()
            }
            .show()
    }

    companion object {
        private const val ARG_STATUS = "status"

        fun newInstance(status: TaskStatus): TaskFragment = TaskFragment().apply {
            arguments = bundleOf(ARG_STATUS to status.ordinal)
        }
    }
}
