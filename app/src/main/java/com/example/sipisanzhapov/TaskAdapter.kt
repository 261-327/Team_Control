package com.example.sipisanzhapov

import android.content.res.ColorStateList
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.ImageView
import android.widget.TextView
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.recyclerview.widget.RecyclerView
import java.util.Collections
import java.util.IdentityHashMap

class TaskAdapter(
    private val taskList: List<Task>,
    // Вызывается при нажатии «На проверку». Если не передан, кнопка скрыта
    private val onSubmitForReview: ((Task) -> Unit)? = null
) : RecyclerView.Adapter<TaskAdapter.TaskViewHolder>() {

    // Какие задачи раскрыты. Сравниваем по ссылке, а не по значению,
    // потому что у Task поле status меняется и хэш data class может поплыть
    private val expandedTasks: MutableSet<Task> =
        Collections.newSetFromMap(IdentityHashMap())

    private val collapsedLines = 3

    class TaskViewHolder(itemView: View) : RecyclerView.ViewHolder(itemView) {
        val tvTitle: TextView = itemView.findViewById(R.id.tvTaskTitle)
        val tvDescription: TextView = itemView.findViewById(R.id.tvTaskDescription)
        val tvShowMore: TextView = itemView.findViewById(R.id.tvShowMore)
        val tvFilesInfo: TextView = itemView.findViewById(R.id.tvFilesInfo)
        val ivAssignee: ImageView = itemView.findViewById(R.id.ivAssignee)
        val tvDeadlineDate: TextView = itemView.findViewById(R.id.tvDeadlineDate)
        val tvTimeRemaining: TextView = itemView.findViewById(R.id.tvTimeRemaining)
        val btnSubmitReview: Button = itemView.findViewById(R.id.btnSubmitReview)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): TaskViewHolder {
        val view = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_task, parent, false)
        return TaskViewHolder(view)
    }

    override fun onBindViewHolder(holder: TaskViewHolder, position: Int) {
        val task = taskList[position]
        val context = holder.itemView.context

        // Название и описание задачи
        holder.tvTitle.text = task.title
        holder.tvDescription.text = task.description

        // Цвет фона карточки по статусу задачи
        val tintRes = when (task.status) {
            0 -> R.color.task_urgent
            1 -> R.color.task_in_progress
            2 -> R.color.task_review
            3 -> R.color.task_unimportant
            else -> null
        }
        tintRes?.let {
            ViewCompat.setBackgroundTintList(
                holder.itemView,
                ColorStateList.valueOf(ContextCompat.getColor(context, it))
            )
        }

        // Кнопка «На проверку» видна, если есть обработчик и задача ещё не на проверке
        val showSubmit = onSubmitForReview != null && task.status != STATUS_REVIEW
        holder.btnSubmitReview.visibility = if (showSubmit) View.VISIBLE else View.GONE
        holder.btnSubmitReview.setOnClickListener { onSubmitForReview?.invoke(task) }

        // Дедлайн или надпись для задач на проверке
        if (task.status == STATUS_REVIEW) {
            holder.tvDeadlineDate.text = "Отправлено на проверку"
            holder.tvTimeRemaining.visibility = View.GONE
        } else {
            holder.tvDeadlineDate.text = "Сдать до: ${DeadlineUtils.formatDeadline(task.deadlineTimestamp)}"
            holder.tvTimeRemaining.text = DeadlineUtils.remainingText(task.deadlineTimestamp)
            holder.tvTimeRemaining.visibility = View.VISIBLE
        }

        // Раскрытие и сворачивание описания прямо в карточке
        holder.tvShowMore.setOnClickListener {
            if (expandedTasks.contains(task)) {
                expandedTasks.remove(task)
            } else {
                expandedTasks.add(task)
            }
            applyDescriptionState(holder, task)
        }
        applyDescriptionState(holder, task)

        // Файл во вложении
        if (!task.fileName.isNullOrEmpty()) {
            holder.tvFilesInfo.visibility = View.VISIBLE
            holder.tvFilesInfo.text = "📎 ${task.fileName}"
        } else {
            holder.tvFilesInfo.visibility = View.GONE
        }

        holder.ivAssignee.setImageResource(task.assigneeAvatarRes)
    }

    override fun getItemCount(): Int = taskList.size

    // Настраиваем описание и кнопку в зависимости от того, раскрыта ли задача
    private fun applyDescriptionState(holder: TaskViewHolder, task: Task) {
        val expanded = expandedTasks.contains(task)

        holder.tvDescription.maxLines = if (expanded) Int.MAX_VALUE else collapsedLines

        if (expanded) {
            // Раскрыто: показываем кнопку «Свернуть», текст виден целиком
            holder.tvShowMore.text = "Свернуть"
            holder.tvShowMore.visibility = View.VISIBLE
            return
        }

        // Свёрнуто: кнопку показываем, только если текст реально обрезан
        holder.tvShowMore.text = "Подробнее"
        holder.tvShowMore.visibility = View.GONE
        holder.tvDescription.post {
            // Карточку могли переиспользовать для другой задачи, тогда ничего не делаем
            if (holder.tvDescription.text.toString() != task.description) return@post
            if (expandedTasks.contains(task)) return@post

            val layout = holder.tvDescription.layout ?: return@post
            val lastLine = layout.lineCount - 1
            val truncated = lastLine >= 0 && layout.getEllipsisCount(lastLine) > 0

            holder.tvShowMore.visibility = if (truncated) View.VISIBLE else View.GONE
        }
    }
}