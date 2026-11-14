package com.example.sipi_ai.ui.search

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.isVisible
import androidx.core.widget.doAfterTextChanged
import androidx.recyclerview.widget.LinearLayoutManager
import com.example.sipi_ai.R
import com.example.sipi_ai.data.ProjectRepository
import com.example.sipi_ai.data.TaskRepository
import com.example.sipi_ai.databinding.ActivitySearchBinding
import com.example.sipi_ai.ui.common.openProject
import com.example.sipi_ai.ui.common.openTask

/** «Поиск по пространству»: задачи и проекты по названию и описанию. */
class SearchActivity : AppCompatActivity() {

    private lateinit var binding: ActivitySearchBinding
    private val adapter = ResultAdapter()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivitySearchBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setSupportActionBar(binding.toolbarSearch)
        supportActionBar?.setDisplayHomeAsUpEnabled(true)

        binding.rvResults.layoutManager = LinearLayoutManager(this)
        binding.rvResults.adapter = adapter
        binding.etSearch.doAfterTextChanged { search(it?.toString().orEmpty()) }
        binding.etSearch.requestFocus()
        search("")
    }

    override fun onSupportNavigateUp(): Boolean {
        finish()
        return true
    }

    private fun search(query: String) {
        val q = query.trim()
        if (q.isEmpty()) {
            adapter.submitList(emptyList())
            binding.tvSearchEmpty.setText(R.string.search_prompt)
            binding.tvSearchEmpty.isVisible = true
            return
        }

        val projects = ProjectRepository.all()
            .filter { it.name.contains(q, ignoreCase = true) || it.description.contains(q, ignoreCase = true) }
            .map { project ->
                ResultRow(
                    key = "project-${project.id}",
                    title = project.name,
                    subtitle = getString(R.string.search_section_projects),
                    iconRes = R.drawable.ic_dashboard,
                    onClick = { openProject(project.id) },
                )
            }
        val tasks = TaskRepository.search(q).map { task ->
            val project = ProjectRepository.get(task.projectId)
            val code = if (project != null) "${project.key}-${task.number}" else "#${task.number}"
            ResultRow(
                key = "task-${task.id}",
                title = task.title,
                subtitle = listOfNotNull(code, project?.name).joinToString(" · "),
                iconRes = R.drawable.ic_assignment,
                onClick = { openTask(task.id) },
            )
        }

        val rows = projects + tasks
        adapter.submitList(rows)
        binding.tvSearchEmpty.setText(R.string.search_empty)
        binding.tvSearchEmpty.isVisible = rows.isEmpty()
    }
}
