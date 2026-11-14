package com.example.sipi_ai.ui.projects

import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.core.os.bundleOf
import androidx.fragment.app.Fragment
import com.example.sipi_ai.R
import com.example.sipi_ai.data.ProjectRepository
import com.example.sipi_ai.data.ApiClient
import com.example.sipi_ai.data.UserStore
import com.example.sipi_ai.databinding.FragmentProjectSettingsBinding
import com.google.android.material.dialog.MaterialAlertDialogBuilder

/** Вкладка «Настройки»: название, описание, период и удаление проекта. */
class ProjectSettingsFragment : Fragment(R.layout.fragment_project_settings) {

    private val projectId by lazy { requireArguments().getLong(ARG_PROJECT_ID) }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        val b = FragmentProjectSettingsBinding.bind(view)
        ApiClient.initialize(requireContext())
        val project = ProjectRepository.get(projectId) ?: return

        b.etSettingsName.setText(project.name)
        b.etSettingsDescription.setText(project.description)
        b.btnSaveSettings.setOnClickListener {
            val current = ProjectRepository.get(projectId) ?: return@setOnClickListener
            val name = b.etSettingsName.text.toString().trim()
            if (name.isEmpty()) {
                b.etSettingsName.error = getString(R.string.project_error_name)
                return@setOnClickListener
            }
            b.btnSaveSettings.isEnabled = false
            ApiClient.updateProject(projectId, name, b.etSettingsDescription.text.toString().trim()) { result ->
                b.btnSaveSettings.isEnabled = true
                result.onSuccess {
                    ApiClient.applyMutation(it, UserStore(requireContext()))
                    Toast.makeText(requireContext(), R.string.settings_saved, Toast.LENGTH_SHORT).show()
                    (activity as? ProjectActivity)?.refreshHeader()
                }.onFailure {
                    Toast.makeText(requireContext(), it.message ?: "Не удалось сохранить проект", Toast.LENGTH_LONG).show()
                }
            }
        }

        b.btnDeleteProject.setOnClickListener {
            val current = ProjectRepository.get(projectId) ?: return@setOnClickListener
            MaterialAlertDialogBuilder(requireContext())
                .setTitle(R.string.settings_delete_title)
                .setMessage(getString(R.string.settings_delete_message, current.name))
                .setNegativeButton(R.string.action_cancel, null)
                .setPositiveButton(R.string.action_delete) { _, _ ->
                    ApiClient.deleteProject(projectId) { result ->
                        result.onSuccess {
                            ApiClient.applyMutation(it, UserStore(requireContext()))
                            requireActivity().finish()
                        }.onFailure {
                            Toast.makeText(requireContext(), it.message ?: "Не удалось удалить проект", Toast.LENGTH_LONG).show()
                        }
                    }
                }
                .show()
        }
    }

    companion object {
        private const val ARG_PROJECT_ID = "project_id"

        fun newInstance(projectId: Long) = ProjectSettingsFragment().apply {
            arguments = bundleOf(ARG_PROJECT_ID to projectId)
        }
    }
}
