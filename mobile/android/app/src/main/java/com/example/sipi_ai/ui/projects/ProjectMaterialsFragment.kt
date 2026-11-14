package com.example.sipi_ai.ui.projects

import android.os.Bundle
import android.text.InputType
import android.view.View
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.Toast
import androidx.core.os.bundleOf
import androidx.core.view.isVisible
import androidx.fragment.app.Fragment
import androidx.recyclerview.widget.LinearLayoutManager
import com.example.sipi_ai.R
import com.example.sipi_ai.data.ApiClient
import com.example.sipi_ai.data.ProjectMaterial
import com.example.sipi_ai.data.ProjectRepository
import com.example.sipi_ai.data.TaskRepository
import com.example.sipi_ai.data.UserStore
import com.example.sipi_ai.databinding.FragmentProjectMaterialsBinding
import com.google.android.material.dialog.MaterialAlertDialogBuilder

/** Materials registered on the server plus task attachment names. */
class ProjectMaterialsFragment : Fragment(R.layout.fragment_project_materials) {

    private var binding: FragmentProjectMaterialsBinding? = null
    private val projectId by lazy { requireArguments().getLong(ARG_PROJECT_ID) }
    private val adapter = RowAdapter { row ->
        val material = ProjectRepository.get(projectId)?.materials?.firstOrNull { it.id == row.payload }
        if (material != null) confirmRemove(material)
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        val b = FragmentProjectMaterialsBinding.bind(view)
        binding = b
        ApiClient.initialize(requireContext())
        b.rvMaterials.layoutManager = LinearLayoutManager(requireContext())
        b.rvMaterials.adapter = adapter
        b.btnAddMaterial.setOnClickListener { showAddDialog() }
        render()
    }

    override fun onResume() { super.onResume(); render() }

    override fun onDestroyView() {
        binding?.rvMaterials?.adapter = null
        binding = null
        super.onDestroyView()
    }

    private fun render() {
        val b = binding ?: return
        val project = ProjectRepository.get(projectId) ?: return
        val manual = project.materials.map { material ->
            Row("material-${material.id}", extension(material.title), material.title, material.url, material.id)
        }
        val fromTasks = TaskRepository.forProject(projectId).mapNotNull { task ->
            val name = task.attachmentName ?: return@mapNotNull null
            Row("task-${task.id}", extension(name), name,
                getString(R.string.materials_from_task, "${project.key}-${task.number}"), clickable = false)
        }
        val rows = manual + fromTasks
        adapter.submitList(rows)
        b.materialsEmpty.isVisible = rows.isEmpty()
        b.rvMaterials.isVisible = rows.isNotEmpty()
    }

    private fun showAddDialog() {
        val content = LinearLayout(requireContext()).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(24, 8, 24, 0)
        }
        val title = EditText(requireContext()).apply {
            hint = getString(R.string.material_title_hint)
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
        }
        val url = EditText(requireContext()).apply {
            hint = getString(R.string.material_url_hint)
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
        }
        content.addView(title)
        content.addView(url)
        val dialog = MaterialAlertDialogBuilder(requireContext())
            .setTitle(R.string.materials_add)
            .setView(content)
            .setNegativeButton(R.string.action_cancel, null)
            .setPositiveButton(R.string.action_add, null)
            .create()
        dialog.setOnShowListener {
            dialog.getButton(androidx.appcompat.app.AlertDialog.BUTTON_POSITIVE).setOnClickListener {
                val materialTitle = title.text.toString().trim()
                val materialUrl = url.text.toString().trim()
                if (materialTitle.isBlank()) { title.error = getString(R.string.project_error_name); return@setOnClickListener }
                if (materialUrl.isBlank()) { url.error = getString(R.string.material_url_hint); return@setOnClickListener }
                ApiClient.addMaterial(projectId, materialTitle, materialUrl) { result ->
                    result.onSuccess {
                        ApiClient.applyMutation(it, UserStore(requireContext()))
                        render()
                        dialog.dismiss()
                    }.onFailure {
                        Toast.makeText(requireContext(), it.message ?: "Не удалось добавить материал", Toast.LENGTH_LONG).show()
                    }
                }
            }
        }
        dialog.show()
    }

    private fun confirmRemove(material: ProjectMaterial) {
        MaterialAlertDialogBuilder(requireContext())
            .setTitle(R.string.action_delete)
            .setMessage(material.title)
            .setNegativeButton(R.string.action_cancel, null)
            .setPositiveButton(R.string.action_delete) { _, _ ->
                ApiClient.deleteMaterial(material.id) { result ->
                    result.onSuccess {
                        ApiClient.applyMutation(it, UserStore(requireContext()))
                        render()
                    }.onFailure {
                        Toast.makeText(requireContext(), it.message ?: "Не удалось удалить материал", Toast.LENGTH_LONG).show()
                    }
                }
            }
            .show()
    }

    private fun extension(name: String): String {
        val ext = name.substringAfterLast('.', "")
        return if (ext.isEmpty() || ext.length > 4) "LINK" else ext.uppercase()
    }

    companion object {
        private const val ARG_PROJECT_ID = "project_id"
        fun newInstance(projectId: Long) = ProjectMaterialsFragment().apply {
            arguments = bundleOf(ARG_PROJECT_ID to projectId)
        }
    }
}
