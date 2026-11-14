package com.example.sipi_ai.ui.common

import android.app.Activity
import android.content.Context
import android.view.LayoutInflater
import android.widget.Toast
import android.widget.AdapterView
import androidx.annotation.StringRes
import androidx.appcompat.app.AlertDialog
import com.example.sipi_ai.R
import com.example.sipi_ai.data.Project
import com.example.sipi_ai.data.ProjectRepository
import com.example.sipi_ai.data.ApiClient
import com.example.sipi_ai.data.UserStore
import com.example.sipi_ai.databinding.DialogInputBinding
import com.example.sipi_ai.databinding.DialogProjectBinding
import com.example.sipi_ai.ui.assistant.AssistantActivity
import com.example.sipi_ai.ui.projects.ProjectActivity
import com.example.sipi_ai.ui.taskdetail.TaskDetailActivity
import com.example.sipi_ai.ui.taskedit.TaskEditActivity
import com.google.android.material.dialog.MaterialAlertDialogBuilder

private val COLORS = intArrayOf(
    R.color.project_yellow, R.color.project_purple, R.color.project_green,
    R.color.project_blue, R.color.project_red, R.color.project_gray,
)
private val SOFT_COLORS = intArrayOf(
    R.color.project_yellow_soft, R.color.project_purple_soft, R.color.project_green_soft,
    R.color.project_blue_soft, R.color.project_red_soft, R.color.project_gray_soft,
)

fun projectColorRes(index: Int): Int = COLORS[index.mod(COLORS.size)]
fun projectSoftColorRes(index: Int): Int = SOFT_COLORS[index.mod(SOFT_COLORS.size)]

fun Context.openTask(taskId: Long) = startActivity(TaskDetailActivity.intent(this, taskId))

fun Context.openProject(projectId: Long) = startActivity(ProjectActivity.intent(this, projectId))

fun Context.openNewTask(projectId: Long? = null) = startActivity(TaskEditActivity.intent(this, null, projectId))

fun Context.openAssistant(projectId: Long? = null) = startActivity(AssistantActivity.intent(this, projectId))

/** Диалог создания проекта. Не закрывается, пока не введено название. */
fun Activity.showCreateProjectDialog(onCreated: (Project) -> Unit) {
    val binding = DialogProjectBinding.inflate(LayoutInflater.from(this))
    val roleValues = resources.getStringArray(R.array.project_role_values)
    val specializationValues = resources.getStringArray(R.array.project_specialization_values)
    binding.spProjectSpecialization.setSelection(specializationValues.indexOf("android").coerceAtLeast(0))
    binding.tvProjectSpecializationLabel.visibility = android.view.View.VISIBLE
    binding.spProjectSpecialization.visibility = android.view.View.VISIBLE
    binding.spProjectRole.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
        override fun onNothingSelected(parent: AdapterView<*>?) = Unit
        override fun onItemSelected(parent: AdapterView<*>?, view: android.view.View?, position: Int, id: Long) {
            val showSpecialization = roleValues.getOrNull(position) == "developer"
            binding.tvProjectSpecializationLabel.visibility = if (showSpecialization) android.view.View.VISIBLE else android.view.View.GONE
            binding.spProjectSpecialization.visibility = if (showSpecialization) android.view.View.VISIBLE else android.view.View.GONE
        }
    }
    val dialog = MaterialAlertDialogBuilder(this)
        .setTitle(R.string.project_dialog_title)
        .setView(binding.root)
        .setNegativeButton(R.string.action_cancel, null)
        .setPositiveButton(R.string.action_create, null)
        .create()
    dialog.setOnShowListener {
        dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener {
            val name = binding.etProjectName.text.toString().trim()
            if (name.isEmpty()) {
                binding.etProjectName.error = getString(R.string.project_error_name)
                return@setOnClickListener
            }
            val positive = dialog.getButton(AlertDialog.BUTTON_POSITIVE)
            positive.isEnabled = false
            ApiClient.initialize(this)
            val role = roleValues[binding.spProjectRole.selectedItemPosition]
            val specialization = specializationValues[binding.spProjectSpecialization.selectedItemPosition]
            ApiClient.createProject(name, binding.etProjectDescription.text.toString(), role, specialization) { result ->
                positive.isEnabled = true
                result.onSuccess { response ->
                    ApiClient.applyMutation(response, UserStore(this))
                    val id = response.optJSONObject("project")?.optString("id")?.toLongOrNull()
                    val project = id?.let { ProjectRepository.get(it) }
                    if (project == null) {
                        Toast.makeText(this, "Проект сохранён, но не найден в обновлённом списке", Toast.LENGTH_LONG).show()
                    } else {
                        dialog.dismiss()
                        Toast.makeText(this, R.string.project_created, Toast.LENGTH_SHORT).show()
                        onCreated(project)
                    }
                }.onFailure {
                    Toast.makeText(this, it.message ?: "Не удалось создать проект", Toast.LENGTH_LONG).show()
                }
            }
        }
    }
    dialog.show()
}

fun Activity.showInputDialog(
    @StringRes title: Int,
    @StringRes hint: Int,
    @StringRes error: Int,
    @StringRes positive: Int,
    onOk: (String) -> Unit,
) {
    val binding = DialogInputBinding.inflate(LayoutInflater.from(this))
    binding.etInput.setHint(hint)
    val dialog = MaterialAlertDialogBuilder(this)
        .setTitle(title)
        .setView(binding.root)
        .setNegativeButton(R.string.action_cancel, null)
        .setPositiveButton(positive, null)
        .create()
    dialog.setOnShowListener {
        dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener {
            val text = binding.etInput.text.toString().trim()
            if (text.isEmpty()) {
                binding.etInput.error = getString(error)
                return@setOnClickListener
            }
            dialog.dismiss()
            onOk(text)
        }
    }
    dialog.show()
}
