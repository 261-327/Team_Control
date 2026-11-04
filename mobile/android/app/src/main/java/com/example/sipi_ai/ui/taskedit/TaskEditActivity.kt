package com.example.sipi_ai.ui.taskedit

import android.app.DatePickerDialog
import android.app.TimePickerDialog
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.AdapterView
import android.widget.ArrayAdapter
import android.widget.Spinner
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.example.sipi_ai.R
import com.example.sipi_ai.data.Directions
import com.example.sipi_ai.data.Members
import com.example.sipi_ai.data.Project
import com.example.sipi_ai.data.ProjectRepository
import com.example.sipi_ai.data.TaskRepository
import com.example.sipi_ai.databinding.ActivityTaskEditBinding
import com.example.sipi_ai.ui.common.MemberNames
import com.example.sipi_ai.util.formatDeadline
import java.util.Calendar

/** Создание и редактирование задачи (поля как в форме «Новая задача» на сайте). */
class TaskEditActivity : AppCompatActivity() {

    private lateinit var binding: ActivityTaskEditBinding
    private lateinit var projects: List<Project>

    private var editingId: Long? = null
    private var deadline: Long? = null
    private var selectedAssignee: Long? = Members.ME_ID
    private var assigneeIds: List<Long?> = listOf(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityTaskEditBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setSupportActionBar(binding.toolbarEdit)
        supportActionBar?.setDisplayHomeAsUpEnabled(true)

        projects = ProjectRepository.all()
        if (projects.isEmpty()) {
            Toast.makeText(this, R.string.task_form_error_no_project, Toast.LENGTH_LONG).show()
            finish()
            return
        }

        editingId = intent.getLongExtra(EXTRA_TASK_ID, -1L).takeIf { it != -1L }
        val task = editingId?.let { TaskRepository.get(it) }
        val presetProject = intent.getLongExtra(EXTRA_PROJECT_ID, -1L)

        supportActionBar?.setTitle(if (task != null) R.string.task_form_edit else R.string.task_form_new)

        setAdapter(binding.spinnerProject, projects.map { it.name })
        setAdapter(binding.spinnerDirection, Directions.all)

        if (task != null) {
            binding.etTitle.setText(task.title)
            binding.etDescription.setText(task.description)
            binding.spinnerProject.setSelection(projects.indexOfFirst { it.id == task.projectId }.coerceAtLeast(0))
            binding.spinnerDirection.setSelection(Directions.all.indexOf(task.direction).coerceAtLeast(0))
            selectedAssignee = task.assigneeId
            deadline = task.deadlineMillis
        } else {
            binding.spinnerProject.setSelection(projects.indexOfFirst { it.id == presetProject }.coerceAtLeast(0))
            deadline = Calendar.getInstance().apply { add(Calendar.DAY_OF_YEAR, 1) }.timeInMillis
        }

        binding.spinnerProject.onItemSelectedListener = onSelected { position ->
            loadAssignees(projects[position])
        }
        binding.spinnerAssignee.onItemSelectedListener = onSelected { position ->
            selectedAssignee = assigneeIds.getOrNull(position)
        }
        loadAssignees(projects[binding.spinnerProject.selectedItemPosition.coerceAtLeast(0)])

        renderDeadline()
        binding.tvDeadlineValue.setOnClickListener { pickDeadline() }
        binding.btnClearDeadline.setOnClickListener {
            deadline = null
            renderDeadline()
        }
        binding.btnSaveTask.setOnClickListener { save() }
    }

    override fun onSupportNavigateUp(): Boolean {
        finish()
        return true
    }

    private fun setAdapter(spinner: Spinner, items: List<String>) {
        spinner.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_item, items).also {
            it.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item)
        }
    }

    private fun onSelected(action: (Int) -> Unit) = object : AdapterView.OnItemSelectedListener {
        override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) = action(position)
        override fun onNothingSelected(parent: AdapterView<*>?) = Unit
    }

    private fun loadAssignees(project: Project) {
        val names = MemberNames(this)
        assigneeIds = listOf<Long?>(null) + project.memberIds
        setAdapter(binding.spinnerAssignee, assigneeIds.map { names.of(it) })
        binding.spinnerAssignee.setSelection(assigneeIds.indexOf(selectedAssignee).coerceAtLeast(0))
    }

    private fun renderDeadline() {
        val value = deadline
        binding.tvDeadlineValue.text = if (value == null) getString(R.string.task_no_deadline) else formatDeadline(value)
    }

    private fun pickDeadline() {
        val current = Calendar.getInstance().apply { timeInMillis = deadline ?: System.currentTimeMillis() }
        DatePickerDialog(
            this,
            { _, year, month, day ->
                TimePickerDialog(
                    this,
                    { _, hour, minute ->
                        deadline = Calendar.getInstance().apply {
                            clear()
                            set(year, month, day, hour, minute, 0)
                        }.timeInMillis
                        renderDeadline()
                    },
                    current.get(Calendar.HOUR_OF_DAY),
                    current.get(Calendar.MINUTE),
                    true,
                ).show()
            },
            current.get(Calendar.YEAR),
            current.get(Calendar.MONTH),
            current.get(Calendar.DAY_OF_MONTH),
        ).show()
    }

    private fun save() {
        val title = binding.etTitle.text.toString().trim()
        if (title.isEmpty()) {
            binding.etTitle.error = getString(R.string.task_form_error_title)
            return
        }
        val project = projects[binding.spinnerProject.selectedItemPosition.coerceAtLeast(0)]
        val description = binding.etDescription.text.toString()
        val direction = Directions.all[binding.spinnerDirection.selectedItemPosition.coerceAtLeast(0)]

        val id = editingId
        if (id == null) {
            TaskRepository.create(project.id, title, description, selectedAssignee, deadline, direction)
        } else {
            TaskRepository.update(id, project.id, title, description, selectedAssignee, deadline, direction)
        }
        Toast.makeText(this, R.string.task_form_saved, Toast.LENGTH_SHORT).show()
        setResult(RESULT_OK)
        finish()
    }

    companion object {
        private const val EXTRA_TASK_ID = "task_id"
        private const val EXTRA_PROJECT_ID = "project_id"

        fun intent(context: Context, taskId: Long?, projectId: Long?): Intent =
            Intent(context, TaskEditActivity::class.java).apply {
                if (taskId != null) putExtra(EXTRA_TASK_ID, taskId)
                if (projectId != null) putExtra(EXTRA_PROJECT_ID, projectId)
            }
    }
}
