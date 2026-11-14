package com.example.sipi_ai.ui.projects

import android.os.Bundle
import android.view.View
import androidx.core.os.bundleOf
import androidx.fragment.app.Fragment
import androidx.recyclerview.widget.LinearLayoutManager
import com.example.sipi_ai.R
import com.example.sipi_ai.data.ProjectRepository
import com.example.sipi_ai.data.ApiClient
import com.example.sipi_ai.data.Members
import com.example.sipi_ai.data.UserStore
import com.example.sipi_ai.databinding.FragmentProjectTeamBinding
import com.example.sipi_ai.ui.common.MemberNames
import com.example.sipi_ai.ui.common.showInputDialog
import com.example.sipi_ai.util.initials
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import android.content.Intent
import android.widget.Toast

/** Вкладка «Команда»: список участников, приглашение и удаление. */
class ProjectTeamFragment : Fragment(R.layout.fragment_project_team) {

    private var binding: FragmentProjectTeamBinding? = null
    private val projectId by lazy { requireArguments().getLong(ARG_PROJECT_ID) }
    private val adapter = RowAdapter { row -> row.payload?.let { confirmRemove(it, row.title) } }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        val b = FragmentProjectTeamBinding.bind(view)
        binding = b
        ApiClient.initialize(requireContext())
        b.rvMembers.layoutManager = LinearLayoutManager(requireContext())
        b.rvMembers.adapter = adapter
        b.btnInvite.setOnClickListener {
            requireActivity().showInputDialog(
                title = R.string.team_invite,
                hint = R.string.team_invite_hint,
                error = R.string.team_invite_error,
                positive = R.string.action_add,
            ) { email ->
                ApiClient.invite(projectId, email) { result ->
                    result.onSuccess { response ->
                        ApiClient.applyMutation(response, UserStore(requireContext()))
                        render()
                        val id = response.optJSONObject("invitation")?.optString("id")
                        if (!id.isNullOrBlank()) {
                            val link = "${ApiClient.siteBaseUrl}invitations/$id"
                            startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).apply {
                                type = "text/plain"
                                putExtra(Intent.EXTRA_TEXT, link)
                            }, getString(R.string.team_invite)))
                        }
                    }.onFailure {
                        Toast.makeText(requireContext(), it.message ?: "Не удалось создать приглашение", Toast.LENGTH_LONG).show()
                    }
                }
            }
        }
        render()
    }

    override fun onResume() {
        super.onResume()
        render()
    }

    override fun onDestroyView() {
        binding?.rvMembers?.adapter = null
        binding = null
        super.onDestroyView()
    }

    private fun render() {
        if (binding == null) return
        val project = ProjectRepository.get(projectId) ?: return
        val names = MemberNames(requireContext())
        val rows = project.memberIds.map { id ->
            val isOwner = id == project.ownerId
            val name = names.of(id)
            Row(
                key = "member-$id",
                badge = initials(name),
                title = name,
                subtitle = getString(if (isOwner) R.string.team_leader else R.string.team_member),
                payload = id,
                clickable = !isOwner,
            )
        }
        adapter.submitList(rows)
        (activity as? ProjectActivity)?.refreshHeader()
    }

    private fun confirmRemove(memberId: Long, name: String) {
        MaterialAlertDialogBuilder(requireContext())
            .setTitle(if (memberId == Members.ME_ID) R.string.project_leave_title else R.string.team_remove_title)
            .setMessage(if (memberId == Members.ME_ID) getString(R.string.project_leave_message) else getString(R.string.team_remove_message, name))
            .setNegativeButton(R.string.action_cancel, null)
            .setPositiveButton(if (memberId == Members.ME_ID) R.string.project_leave else R.string.team_remove) { _, _ ->
                val done: (Result<org.json.JSONObject>) -> Unit = { result ->
                    result.onSuccess {
                        ApiClient.applyMutation(it, UserStore(requireContext()))
                        if (memberId == Members.ME_ID) requireActivity().finish() else render()
                    }.onFailure {
                        Toast.makeText(requireContext(), it.message ?: "Не удалось изменить участников", Toast.LENGTH_LONG).show()
                    }
                }
                if (memberId == Members.ME_ID) ApiClient.leaveProject(projectId, done)
                else ApiClient.removeMember(projectId, memberId, done)
            }
            .show()
    }

    companion object {
        private const val ARG_PROJECT_ID = "project_id"

        fun newInstance(projectId: Long) = ProjectTeamFragment().apply {
            arguments = bundleOf(ARG_PROJECT_ID to projectId)
        }
    }
}
