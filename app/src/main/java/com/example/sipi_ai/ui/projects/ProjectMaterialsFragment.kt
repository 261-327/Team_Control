package com.example.sipi_ai.ui.projects

import android.net.Uri
import android.os.Bundle
import android.provider.OpenableColumns
import android.view.View
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.os.bundleOf
import androidx.core.view.isVisible
import androidx.fragment.app.Fragment
import androidx.recyclerview.widget.LinearLayoutManager
import com.example.sipi_ai.R
import com.example.sipi_ai.data.ProjectRepository
import com.example.sipi_ai.data.TaskRepository
import com.example.sipi_ai.databinding.FragmentProjectMaterialsBinding
import com.google.android.material.dialog.MaterialAlertDialogBuilder

/** Вкладка «Материалы»: файлы, добавленные вручную, и вложения задач проекта. */
class ProjectMaterialsFragment : Fragment(R.layout.fragment_project_materials) {

    private var binding: FragmentProjectMaterialsBinding? = null
    private val projectId by lazy { requireArguments().getLong(ARG_PROJECT_ID) }
    private val adapter = RowAdapter { row -> confirmRemove(row.title) }

    private val pickFile = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) {
            ProjectRepository.addMaterial(projectId, displayName(uri))
            render()
        }
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        val b = FragmentProjectMaterialsBinding.bind(view)
        binding = b
        b.rvMaterials.layoutManager = LinearLayoutManager(requireContext())
        b.rvMaterials.adapter = adapter
        b.btnAddMaterial.setOnClickListener { pickFile.launch(arrayOf("*/*")) }
        render()
    }

    override fun onResume() {
        super.onResume()
        render()
    }

    override fun onDestroyView() {
        binding?.rvMaterials?.adapter = null
        binding = null
        super.onDestroyView()
    }

    private fun render() {
        val b = binding ?: return
        val project = ProjectRepository.get(projectId) ?: return

        val manual = project.materials.map { name ->
            Row("manual-$name", extension(name), name, getString(R.string.materials_added))
        }
        val fromTasks = TaskRepository.forProject(projectId).mapNotNull { task ->
            val name = task.attachmentName ?: return@mapNotNull null
            Row(
                key = "task-${task.id}",
                badge = extension(name),
                title = name,
                subtitle = getString(R.string.materials_from_task, "${project.key}-${task.number}"),
                clickable = false,
            )
        }
        val rows = manual + fromTasks
        adapter.submitList(rows)
        b.materialsEmpty.isVisible = rows.isEmpty()
        b.rvMaterials.isVisible = rows.isNotEmpty()
    }

    private fun confirmRemove(name: String) {
        MaterialAlertDialogBuilder(requireContext())
            .setTitle(R.string.action_delete)
            .setMessage(name)
            .setNegativeButton(R.string.action_cancel, null)
            .setPositiveButton(R.string.action_delete) { _, _ ->
                ProjectRepository.removeMaterial(projectId, name)
                render()
            }
            .show()
    }

    private fun displayName(uri: Uri): String {
        val fromProvider = requireContext().contentResolver.query(uri, null, null, null, null)?.use { cursor ->
            val index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
            if (index >= 0 && cursor.moveToFirst()) cursor.getString(index) else null
        }
        return fromProvider ?: uri.lastPathSegment ?: "file"
    }

    private fun extension(name: String): String {
        val ext = name.substringAfterLast('.', "")
        return if (ext.isEmpty() || ext.length > 4) "FILE" else ext.uppercase()
    }

    companion object {
        private const val ARG_PROJECT_ID = "project_id"

        fun newInstance(projectId: Long) = ProjectMaterialsFragment().apply {
            arguments = bundleOf(ARG_PROJECT_ID to projectId)
        }
    }
}
