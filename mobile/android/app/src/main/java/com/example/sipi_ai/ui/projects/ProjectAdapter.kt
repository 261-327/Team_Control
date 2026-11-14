package com.example.sipi_ai.ui.projects

import android.content.res.ColorStateList
import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.core.view.isVisible
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.example.sipi_ai.R
import com.example.sipi_ai.data.Members
import com.example.sipi_ai.data.Project
import com.example.sipi_ai.data.TaskRepository
import com.example.sipi_ai.data.TaskStatus
import com.example.sipi_ai.databinding.ItemProjectBinding
import com.example.sipi_ai.ui.common.projectColorRes
import com.example.sipi_ai.ui.common.projectSoftColorRes
import com.example.sipi_ai.util.russianPlural

class ProjectAdapter(
    private val onClick: (Project) -> Unit,
) : ListAdapter<Project, ProjectAdapter.ViewHolder>(Diff) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder =
        ViewHolder(ItemProjectBinding.inflate(LayoutInflater.from(parent.context), parent, false))

    override fun onBindViewHolder(holder: ViewHolder, position: Int) = holder.bind(getItem(position))

    inner class ViewHolder(private val binding: ItemProjectBinding) : RecyclerView.ViewHolder(binding.root) {

        fun bind(project: Project) {
            val context = binding.root.context
            val tasks = TaskRepository.forProject(project.id)
            val done = tasks.count { it.status == TaskStatus.DONE }
            val percent = if (tasks.isEmpty()) 0 else done * 100 / tasks.size

            binding.ivProjectIcon.setBackgroundResource(R.drawable.bg_avatar)
            binding.ivProjectIcon.backgroundTintList =
                ColorStateList.valueOf(context.getColor(projectSoftColorRes(project.colorIndex)))
            binding.ivProjectIcon.imageTintList =
                ColorStateList.valueOf(context.getColor(projectColorRes(project.colorIndex)))

            binding.tvProjectName.text = project.name
            val tasksText = context.getString(
                russianPlural(
                    tasks.size,
                    R.string.project_tasks_count_one,
                    R.string.project_tasks_count_few,
                    R.string.project_tasks_count_many,
                ),
                tasks.size,
            )
            val membersText = context.getString(
                russianPlural(
                    project.memberIds.size,
                    R.string.project_members_count_one,
                    R.string.project_members_count_few,
                    R.string.project_members_count_many,
                ),
                project.memberIds.size,
            )
            binding.tvProjectStats.text = "$tasksText · $membersText"
            binding.progressProject.setProgressCompat(percent, false)
            binding.tvProjectPercent.text = "$percent%"
            binding.tvProjectDone.text = context.getString(R.string.project_done_of, done, tasks.size)
            binding.tvProjectDescription.text = project.description
            binding.tvProjectDescription.isVisible = project.description.isNotEmpty()
            binding.tvProjectRole.setText(
                if (project.ownerId == Members.ME_ID) R.string.project_role_owner else R.string.project_role_member,
            )
            binding.root.setOnClickListener { onClick(project) }
        }
    }

    private object Diff : DiffUtil.ItemCallback<Project>() {
        override fun areItemsTheSame(oldItem: Project, newItem: Project) = oldItem.id == newItem.id
        override fun areContentsTheSame(oldItem: Project, newItem: Project) = oldItem == newItem
    }
}
