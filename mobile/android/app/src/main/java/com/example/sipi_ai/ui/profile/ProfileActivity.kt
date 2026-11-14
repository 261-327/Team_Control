package com.example.sipi_ai.ui.profile

import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.isVisible
import androidx.core.widget.doAfterTextChanged
import com.example.sipi_ai.R
import com.example.sipi_ai.data.Members
import com.example.sipi_ai.data.ApiClient
import com.example.sipi_ai.data.ProjectRepository
import com.example.sipi_ai.data.TaskRepository
import com.example.sipi_ai.data.UserStore
import com.example.sipi_ai.databinding.ActivityProfileBinding
import com.example.sipi_ai.databinding.ItemMemberBinding
import com.example.sipi_ai.ui.common.MemberNames
import com.example.sipi_ai.ui.register.LoginActivity
import com.example.sipi_ai.util.initials
import com.google.android.material.dialog.MaterialAlertDialogBuilder

class ProfileActivity : AppCompatActivity() {

    private lateinit var binding: ActivityProfileBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityProfileBinding.inflate(layoutInflater)
        setContentView(binding.root)
        ApiClient.initialize(this)

        setSupportActionBar(binding.toolbarProfile)
        supportActionBar?.setDisplayHomeAsUpEnabled(true)

        val user = UserStore(this)
        binding.etProfileName.setText(user.fullName.orEmpty())
        binding.etProfileEmail.setText(user.email ?: getString(R.string.profile_email_missing))
        binding.etProfileAbout.setText(user.about)
        binding.etProfileAbout.doAfterTextChanged { updateAboutCounter() }
        updateAboutCounter()

        binding.btnSaveProfile.setOnClickListener { save() }
        binding.btnLogout.setOnClickListener { confirmLogout() }

        renderHeader()
        renderColleagues()
    }

    override fun onSupportNavigateUp(): Boolean {
        finish()
        return true
    }

    private fun renderHeader() {
        val user = UserStore(this)
        val name = user.fullName
        binding.tvProfileName.text = name ?: getString(R.string.profile_name_missing)
        binding.tvProfileEmail.text = user.email ?: getString(R.string.profile_email_missing)
        binding.tvProfileAvatar.text = if (name.isNullOrBlank()) "?" else initials(name)
        binding.tvStatProjects.text = ProjectRepository.all().size.toString()
        binding.tvStatProjectsLabel.setText(R.string.profile_stat_projects)
        binding.tvStatTasks.text = TaskRepository.mine().size.toString()
        binding.tvStatTasksLabel.setText(R.string.profile_stat_tasks)
    }

    private fun renderColleagues() {
        val names = MemberNames(this)
        val colleagueIds = ProjectRepository.all()
            .flatMap { it.memberIds }
            .filter { it != Members.ME_ID }
            .distinct()

        binding.colleaguesList.removeAllViews()
        val inflater = LayoutInflater.from(this)
        for (id in colleagueIds) {
            val row = ItemMemberBinding.inflate(inflater, binding.colleaguesList, false)
            row.tvMemberAvatar.text = names.initialsOf(id)
            row.tvMemberName.text = names.of(id)
            row.tvMemberRole.text = getString(R.string.team_member)
            row.root.isClickable = false
            binding.colleaguesList.addView(row.root)
        }
        binding.tvNoColleagues.isVisible = colleagueIds.isEmpty()
    }

    private fun updateAboutCounter() {
        binding.tvAboutCounter.text =
            getString(R.string.profile_about_counter, binding.etProfileAbout.text?.length ?: 0)
    }

    private fun save() {
        val name = binding.etProfileName.text.toString().trim()
        if (name.isEmpty()) {
            binding.etProfileName.error = getString(R.string.profile_name_error)
            return
        }
        binding.btnSaveProfile.isEnabled = false
        ApiClient.updateProfile(name, binding.etProfileAbout.text.toString().trim()) { result ->
            binding.btnSaveProfile.isEnabled = true
            result.onSuccess {
                ApiClient.applyMutation(it, UserStore(this))
                UserStore(this).saveProfile(name, binding.etProfileAbout.text.toString().trim())
                Toast.makeText(this, R.string.profile_saved, Toast.LENGTH_SHORT).show()
                renderHeader()
            }.onFailure { Toast.makeText(this, it.message ?: "Не удалось сохранить профиль", Toast.LENGTH_LONG).show() }
        }
    }

    private fun confirmLogout() {
        MaterialAlertDialogBuilder(this)
            .setTitle(R.string.profile_logout_title)
            .setMessage(R.string.profile_logout_message)
            .setNegativeButton(R.string.action_cancel, null)
            .setPositiveButton(R.string.profile_logout) { _, _ ->
                ApiClient.logout { result ->
                    result.onSuccess {
                        ApiClient.clearSession()
                        UserStore(this).clear()
                        startActivity(Intent(this, LoginActivity::class.java)
                            .putExtra(LoginActivity.EXTRA_SKIP_SESSION_RESTORE, true)
                            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK))
                    }.onFailure { Toast.makeText(this, it.message ?: "Не удалось выйти", Toast.LENGTH_LONG).show() }
                }
            }
            .show()
    }
}
