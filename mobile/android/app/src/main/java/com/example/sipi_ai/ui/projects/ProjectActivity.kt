package com.example.sipi_ai.ui.projects

import android.content.Context
import android.content.Intent
import android.content.res.ColorStateList
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import androidx.fragment.app.Fragment
import androidx.fragment.app.FragmentActivity
import androidx.viewpager2.adapter.FragmentStateAdapter
import com.example.sipi_ai.R
import com.example.sipi_ai.data.Members
import com.example.sipi_ai.data.ProjectRepository
import com.example.sipi_ai.data.TaskRepository
import com.example.sipi_ai.databinding.ActivityProjectBinding
import com.example.sipi_ai.ui.common.openNewTask
import com.example.sipi_ai.ui.common.projectColorRes
import com.example.sipi_ai.ui.common.projectSoftColorRes
import com.google.android.material.tabs.TabLayoutMediator

class ProjectActivity : AppCompatActivity() {

    private lateinit var binding: ActivityProjectBinding
    private var projectId = -1L

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        projectId = intent.getLongExtra(EXTRA_PROJECT_ID, -1L)
        if (ProjectRepository.get(projectId) == null) {
            finish()
            return
        }
        binding = ActivityProjectBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setSupportActionBar(binding.toolbarProject)
        supportActionBar?.setDisplayHomeAsUpEnabled(true)
        supportActionBar?.setDisplayShowTitleEnabled(false)

        binding.pagerProject.adapter = ProjectPagerAdapter(this, projectId)
        TabLayoutMediator(binding.tabProject, binding.pagerProject) { tab, position ->
            tab.text = tabTitle(position)
        }.attach()

        binding.btnNewTask.setOnClickListener { openNewTask(projectId) }
    }

    override fun onResume() {
        super.onResume()
        if (ProjectRepository.get(projectId) != null) refreshHeader()
    }

    override fun onSupportNavigateUp(): Boolean {
        finish()
        return true
    }

    /** Вызывается вкладками, когда в проекте что-то изменилось. */
    fun refreshHeader() {
        val project = ProjectRepository.get(projectId) ?: run {
            finish()
            return
        }
        binding.tvProjectName.text = project.name
        binding.tvProjectDescription.text = project.description
        binding.tvSeason.text = project.season
        binding.ivProjectIcon.setBackgroundResource(R.drawable.bg_avatar)
        binding.ivProjectIcon.backgroundTintList =
            ColorStateList.valueOf(getColor(projectSoftColorRes(project.colorIndex)))
        binding.ivProjectIcon.imageTintList =
            ColorStateList.valueOf(getColor(projectColorRes(project.colorIndex)))

        val team = getString(R.string.project_team_count, project.memberIds.size)
        binding.tvProjectMeta.text =
            if (project.ownerId == Members.ME_ID) "$team  ·  ${getString(R.string.project_you_lead)}" else team

        val tasksCount = TaskRepository.forProject(projectId).size
        binding.tabProject.getTabAt(0)?.text = "${getString(R.string.project_tab_tasks)} $tasksCount"
        binding.tabProject.getTabAt(1)?.text =
            "${getString(R.string.project_tab_team)} ${project.memberIds.size}"
    }

    private fun tabTitle(position: Int): String = getString(
        when (position) {
            0 -> R.string.project_tab_tasks
            1 -> R.string.project_tab_team
            2 -> R.string.project_tab_materials
            else -> R.string.project_tab_settings
        },
    )

    private class ProjectPagerAdapter(
        activity: FragmentActivity,
        private val projectId: Long,
    ) : FragmentStateAdapter(activity) {
        override fun getItemCount(): Int = 4

        override fun createFragment(position: Int): Fragment = when (position) {
            0 -> ProjectTasksFragment.newInstance(projectId)
            1 -> ProjectTeamFragment.newInstance(projectId)
            2 -> ProjectMaterialsFragment.newInstance(projectId)
            else -> ProjectSettingsFragment.newInstance(projectId)
        }
    }

    companion object {
        private const val EXTRA_PROJECT_ID = "project_id"

        fun intent(context: Context, projectId: Long): Intent =
            Intent(context, ProjectActivity::class.java).putExtra(EXTRA_PROJECT_ID, projectId)
    }
}
