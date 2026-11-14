package com.example.sipi_ai.ui.projects

import android.view.LayoutInflater
import android.view.ViewGroup
import android.widget.PopupMenu
import androidx.core.view.isVisible
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.example.sipi_ai.R
import com.example.sipi_ai.data.ProjectRepository
import com.example.sipi_ai.data.Task
import com.example.sipi_ai.data.TaskStatus
import com.example.sipi_ai.databinding.ItemBoardCardBinding
import com.example.sipi_ai.ui.common.MemberNames
import com.example.sipi_ai.ui.tasks.style
import com.example.sipi_ai.util.formatDeadline

/** Компактная карточка задачи для колонки доски. */
class BoardCardAdapter(
    private val onOpen: (Task) -> Unit,
    private val onMove: (Task, TaskStatus) -> Unit,
    private val onDelete: (Task) -> Unit,
) : ListAdapter<Task, BoardCardAdapter.ViewHolder>(Diff) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder =
        ViewHolder(ItemBoardCardBinding.inflate(LayoutInflater.from(parent.context), parent, false))

    override fun onBindViewHolder(holder: ViewHolder, position: Int) = holder.bind(getItem(position))

    inner class ViewHolder(private val binding: ItemBoardCardBinding) : RecyclerView.ViewHolder(binding.root) {

        fun bind(task: Task) {
            val context = binding.root.context
            val project = ProjectRepository.get(task.projectId)

            binding.tvCardDirection.text = task.direction
            binding.tvCardTitle.text = task.title
            binding.tvCardDescription.text = task.description
            binding.tvCardDescription.isVisible = task.description.isNotEmpty()
            binding.tvCardCode.text = if (project != null) "${project.key}-${task.number}" else "#${task.number}"
            binding.tvCardDeadline.text =
                task.deadlineMillis?.let { formatDeadline(it) } ?: context.getString(R.string.task_no_deadline)

            val assignee = task.assigneeId
            binding.tvCardAssignee.text = if (assignee == null) "–" else MemberNames(context).initialsOf(assignee)

            binding.root.setOnClickListener { onOpen(task) }
            binding.btnCardMenu.setOnClickListener {
                val popup = PopupMenu(context, binding.btnCardMenu)
                popup.menu.add(0, ID_OPEN, 0, R.string.board_open)
                TaskStatus.entries.filter { it != task.status }.forEachIndexed { index, status ->
                    popup.menu.add(
                        0,
                        ID_MOVE_BASE + status.ordinal,
                        index + 1,
                        context.getString(R.string.board_move_to, context.getString(status.style.label)),
                    )
                }
                popup.menu.add(0, ID_DELETE, 99, R.string.action_delete)
                popup.setOnMenuItemClickListener { item ->
                    when {
                        item.itemId == ID_OPEN -> onOpen(task)
                        item.itemId == ID_DELETE -> onDelete(task)
                        item.itemId >= ID_MOVE_BASE -> onMove(task, TaskStatus.entries[item.itemId - ID_MOVE_BASE])
                    }
                    true
                }
                popup.show()
            }
        }
    }

    private object Diff : DiffUtil.ItemCallback<Task>() {
        override fun areItemsTheSame(oldItem: Task, newItem: Task) = oldItem.id == newItem.id
        override fun areContentsTheSame(oldItem: Task, newItem: Task) = oldItem == newItem
    }

    private companion object {
        const val ID_OPEN = 1
        const val ID_DELETE = 2
        const val ID_MOVE_BASE = 100
    }
}
