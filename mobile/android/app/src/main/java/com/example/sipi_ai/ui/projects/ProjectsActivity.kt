package com.example.sipi_ai.ui.projects

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.isVisible
import androidx.core.widget.doAfterTextChanged
import androidx.recyclerview.widget.LinearLayoutManager
import com.example.sipi_ai.R
import com.example.sipi_ai.data.ProjectRepository
import com.example.sipi_ai.databinding.ActivityProjectsBinding
import com.example.sipi_ai.ui.common.openAssistant
import com.example.sipi_ai.ui.common.openProject
import com.example.sipi_ai.ui.common.showCreateProjectDialog
import com.example.sipi_ai.util.russianPlural

class ProjectsActivity : AppCompatActivity() {

    private lateinit var binding: ActivityProjectsBinding
    private val adapter = ProjectAdapter { project -> openProject(project.id) }
    private var query = ""

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityProjectsBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setSupportActionBar(binding.toolbarProjects)
        supportActionBar?.setDisplayHomeAsUpEnabled(true)

        binding.rvProjects.layoutManager = LinearLayoutManager(this)
        binding.rvProjects.adapter = adapter

        binding.etSearchProject.doAfterTextChanged {
            query = it?.toString().orEmpty().trim()
            render()
        }
        binding.cardNewProject.setOnClickListener { createProject() }
        binding.btnCreateWithAssistant.setOnClickListener { openAssistant() }
        binding.fabAssistant.setOnClickListener { openAssistant() }
    }

    override fun onResume() {
        super.onResume()
        render()
    }

    override fun onSupportNavigateUp(): Boolean {
        finish()
        return true
    }

    private fun createProject() {
        showCreateProjectDialog { project -> openProject(project.id) }
    }

    private fun render() {
        val all = ProjectRepository.all()
        val shown = all.filter { query.isEmpty() || it.name.contains(query, ignoreCase = true) }
        adapter.submitList(shown)
        binding.tvProjectsEmpty.isVisible = shown.isEmpty()
        binding.tvProjectsCount.text = getString(
            russianPlural(
                all.size,
                R.string.projects_count_one,
                R.string.projects_count_few,
                R.string.projects_count_many,
            ),
            all.size,
        )
    }
}
