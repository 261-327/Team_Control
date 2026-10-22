package com.example.sipisanzhapov
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageView
import android.widget.TextView
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.RecyclerView

class TaskAdapter(private val taskList: List<Task>) :
    RecyclerView.Adapter<TaskAdapter.TaskViewHolder>() {

    // ViewHolder удерживает ссылки на элементы внутри item_task.xml, чтобы быстро их заполнять
    class TaskViewHolder(itemView: View) : RecyclerView.ViewHolder(itemView) {
        val tvTitle: TextView = itemView.findViewById(R.id.tvTaskTitle)
        val tvDescription: TextView = itemView.findViewById(R.id.tvTaskDescription)
        val tvFilesInfo: TextView = itemView.findViewById(R.id.tvFilesInfo)
        val ivAssignee: ImageView = itemView.findViewById(R.id.ivAssignee)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): TaskViewHolder {
        // Создаем раздувание макета нашей карточки item_task.xml
        val view = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_task, parent, false)
        return TaskViewHolder(view)
    }

    override fun onBindViewHolder(holder: TaskViewHolder, position: Int) {
        val task = taskList[position]
        when (task.status) {
            0 -> {
                // Срочно — меняем цвет через tint, сохраняя форму и скругления
                androidx.core.view.ViewCompat.setBackgroundTintList(
                    holder.itemView,
                    android.content.res.ColorStateList.valueOf(
                        ContextCompat.getColor(holder.itemView.context, R.color.task_urgent)
                    )
                )
            }
            1 -> {

                androidx.core.view.ViewCompat.setBackgroundTintList(
                    holder.itemView,
                    android.content.res.ColorStateList.valueOf(
                        ContextCompat.getColor(holder.itemView.context, R.color.task_in_progress)
                    )
                )
            }
            3 -> {
                // Срочно — меняем цвет через tint, сохраняя форму и скругления
                androidx.core.view.ViewCompat.setBackgroundTintList(
                    holder.itemView,
                    android.content.res.ColorStateList.valueOf(
                        ContextCompat.getColor(holder.itemView.context, R.color.task_unimportant)
                    )
                )
            }
        }
            // И так далее для остальных статусов...


        holder.tvTitle.text = task.title
        holder.tvDescription.text = task.description

        if (!task.fileName.isNullOrEmpty()) {
            holder.tvFilesInfo.visibility = View.VISIBLE
            holder.tvFilesInfo.text = "📎 ${task.fileName}"
        } else {
            holder.tvFilesInfo.visibility = View.GONE
        }

        holder.ivAssignee.setImageResource(task.assigneeAvatarRes)
    }

    override fun getItemCount(): Int {
        return taskList.size
    }
}