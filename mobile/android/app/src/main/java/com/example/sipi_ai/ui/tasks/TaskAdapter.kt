package com.example.sipi_ai.ui.tasks

import android.content.Context
import android.content.res.ColorStateList
import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.core.view.isVisible
import androidx.core.widget.ImageViewCompat
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.example.sipi_ai.R
import com.example.sipi_ai.data.Task
import com.example.sipi_ai.data.TaskRepository
import com.example.sipi_ai.data.TaskStatus
import com.example.sipi_ai.databinding.ItemTaskBinding
import com.example.sipi_ai.util.daysUntil
import com.example.sipi_ai.util.formatDeadline
import com.example.sipi_ai.util.russianPlural

private const val COLLAPSED_DESCRIPTION_LINES = 3

class TaskAdapter(
    private val onSubmitForReview: ((Task) -> Unit)? = null,
) : ListAdapter<Task, TaskAdapter.TaskViewHolder>(TaskDiff) {

    private val expandedTaskIds = mutableSetOf<Long>()

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): TaskViewHolder =
        TaskViewHolder(ItemTaskBinding.inflate(LayoutInflater.from(parent.context), parent, false))

    override fun onBindViewHolder(holder: TaskViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    inner class TaskViewHolder(
        private val binding: ItemTaskBinding,
    ) : RecyclerView.ViewHolder(binding.root) {

        private var boundTaskId: Long? = null

        fun bind(task: Task) {
            boundTaskId = task.id
            val context = binding.root.context

            binding.tvStatus.setText(task.status.labelRes)
            binding.tvStatus.setTextColor(context.getColor(task.status.colorRes))
            binding.tvStatus.backgroundTintList =
                ColorStateList.valueOf(context.getColor(task.status.backgroundColorRes))

            binding.tvTaskTitle.text = task.title
            binding.tvTaskDescription.text = task.description
            bindDeadline(task, context)

            val attachment = task.attachmentName.orEmpty()
            binding.tvFilesInfo.isVisible = attachment.isNotEmpty()
            binding.tvFilesInfo.text = attachment

            binding.btnSubmitReview.isVisible = onSubmitForReview != null && task.status != TaskStatus.REVIEW
            binding.btnSubmitReview.setOnClickListener { onSubmitForReview?.invoke(task) }
            binding.rowActions.isVisible = binding.tvFilesInfo.isVisible || binding.btnSubmitReview.isVisible

            binding.tvShowMore.setOnClickListener {
                if (task.id in expandedTaskIds) expandedTaskIds.remove(task.id) else expandedTaskIds.add(task.id)
                bindDescriptionState(task)
            }
            bindDescriptionState(task)
        }

        private fun bindDeadline(task: Task, context: Context) {
            if (task.status == TaskStatus.REVIEW) {
                val reviewColor = context.getColor(R.color.status_review)
                binding.ivDeadlineIcon.setImageResource(R.drawable.ic_check_circle)
                ImageViewCompat.setImageTintList(binding.ivDeadlineIcon, ColorStateList.valueOf(reviewColor))
                binding.tvDeadlineDate.setText(R.string.task_sent_for_review)
                binding.tvDeadlineDate.setTextColor(reviewColor)
                binding.tvTimeRemaining.isVisible = false
                return
            }

            val secondaryColor = context.getColor(R.color.text_secondary)
            binding.ivDeadlineIcon.setImageResource(R.drawable.ic_schedule)
            ImageViewCompat.setImageTintList(binding.ivDeadlineIcon, ColorStateList.valueOf(secondaryColor))
            binding.tvDeadlineDate.text =
                context.getString(R.string.task_deadline, formatDeadline(task.deadlineMillis))
            binding.tvDeadlineDate.setTextColor(secondaryColor)

            val now = System.currentTimeMillis()
            binding.tvTimeRemaining.text = context.remainingTimeText(task.deadlineMillis, now)
            binding.tvTimeRemaining.setTextColor(context.getColor(remainingTimeColorRes(task.deadlineMillis, now)))
            binding.tvTimeRemaining.isVisible = true
        }

        private fun bindDescriptionState(task: Task) {
            val expanded = task.id in expandedTaskIds
            binding.tvTaskDescription.maxLines = if (expanded) Int.MAX_VALUE else COLLAPSED_DESCRIPTION_LINES
            binding.tvShowMore.setText(if (expanded) R.string.task_show_less else R.string.task_show_more)
            binding.tvShowMore.isVisible = expanded
            if (expanded) return

            // Обрезан ли текст, известно только после разметки, а карточку к этому моменту
            // могли переиспользовать под другую задачу
            binding.tvTaskDescription.post {
                if (boundTaskId != task.id || task.id in expandedTaskIds) return@post
                val layout = binding.tvTaskDescription.layout ?: return@post
                val lastLine = layout.lineCount - 1
                binding.tvShowMore.isVisible = lastLine >= 0 && layout.getEllipsisCount(lastLine) > 0
            }
        }
    }
}

//Ты что реально читаешь PR? У тебя ребятки слабенькие(
private object TaskDiff : DiffUtil.ItemCallback<Task>() {
    override fun areItemsTheSame(oldItem: Task, newItem: Task): Boolean = oldItem.id == newItem.id

    override fun areContentsTheSame(oldItem: Task, newItem: Task): Boolean = oldItem == newItem
}

private fun Context.remainingTimeText(deadlineMillis: Long, nowMillis: Long): String {
    if (deadlineMillis < nowMillis) return getString(R.string.deadline_expired)

    val days = daysUntil(deadlineMillis, nowMillis)
    if (days == 0) return getString(R.string.deadline_last_day)

    val phrase = russianPlural(
        days,
        one = R.string.deadline_days_left_one,
        few = R.string.deadline_days_left_few,
        many = R.string.deadline_days_left_many,
    )
    return getString(phrase, days)
}

private fun remainingTimeColorRes(deadlineMillis: Long, nowMillis: Long): Int = when {
    deadlineMillis < nowMillis -> R.color.status_urgent
    daysUntil(deadlineMillis, nowMillis) <= TaskRepository.URGENT_DAYS_BEFORE_DEADLINE -> R.color.mustard_dark
    else -> R.color.text_secondary
}
