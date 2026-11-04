package com.example.sipi_ai.ui.assistant

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.Menu
import android.view.MenuItem
import android.view.View
import android.widget.AdapterView
import android.widget.ArrayAdapter
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.isVisible
import androidx.core.widget.doAfterTextChanged
import androidx.recyclerview.widget.LinearLayoutManager
import com.example.sipi_ai.R
import com.example.sipi_ai.data.Project
import com.example.sipi_ai.data.ProjectRepository
import com.example.sipi_ai.databinding.ActivityAssistantBinding
import com.google.android.material.dialog.MaterialAlertDialogBuilder

/** «Сипи AI»: чат-помощник по проектам (контекст, режимы «Помощник» и «Черновик задач»). */
class AssistantActivity : AppCompatActivity() {

    private lateinit var binding: ActivityAssistantBinding
    private val messages = mutableListOf<ChatMessage>()
    private var nextMessageId = 1L

    private var mode = AssistantMode.ASSISTANT
    private var contextProjectId: Long? = null
    private var projects: List<Project> = emptyList()

    private val adapter = MessageAdapter { message -> addDrafts(message) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityAssistantBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setSupportActionBar(binding.toolbarAssistant)
        supportActionBar?.setDisplayHomeAsUpEnabled(true)

        contextProjectId = intent.getLongExtra(EXTRA_PROJECT_ID, -1L).takeIf { it != -1L }

        binding.rvMessages.layoutManager = LinearLayoutManager(this).also { it.stackFromEnd = true }
        binding.rvMessages.adapter = adapter

        loadContexts()
        binding.spinnerContext.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                contextProjectId = if (position == 0) null else projects.getOrNull(position - 1)?.id
            }

            override fun onNothingSelected(parent: AdapterView<*>?) = Unit
        }

        binding.toggleAssistantMode.addOnButtonCheckedListener { _, checkedId, isChecked ->
            if (!isChecked) return@addOnButtonCheckedListener
            mode = if (checkedId == R.id.btnModeDrafts) AssistantMode.DRAFTS else AssistantMode.ASSISTANT
            binding.etMessage.setHint(
                if (mode == AssistantMode.DRAFTS) R.string.assistant_input_hint_drafts
                else R.string.assistant_input_hint_assistant,
            )
        }

        binding.etMessage.doAfterTextChanged {
            binding.tvMessageCounter.text = getString(R.string.assistant_counter, it?.length ?: 0)
        }
        binding.tvMessageCounter.text = getString(R.string.assistant_counter, 0)

        binding.btnSendMessage.setOnClickListener { send(binding.etMessage.text.toString()) }
        binding.chipDeadlines.setOnClickListener { send(getString(R.string.assistant_suggest_deadlines)) }
        binding.chipCreate.setOnClickListener {
            binding.etMessage.setText(R.string.assistant_suggest_create)
            binding.etMessage.setSelection(binding.etMessage.text.length)
            binding.etMessage.requestFocus()
        }
        renderMessages()
    }

    override fun onCreateOptionsMenu(menu: Menu): Boolean {
        menuInflater.inflate(R.menu.menu_assistant, menu)
        return true
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean = when (item.itemId) {
        R.id.action_clear_chat -> {
            confirmClear()
            true
        }
        else -> super.onOptionsItemSelected(item)
    }

    override fun onSupportNavigateUp(): Boolean {
        finish()
        return true
    }

    private fun loadContexts() {
        projects = ProjectRepository.all()
        val labels = listOf(getString(R.string.calendar_all_projects)) + projects.map { it.name }
        binding.spinnerContext.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_item, labels).also {
            it.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item)
        }
        val index = projects.indexOfFirst { it.id == contextProjectId }
        binding.spinnerContext.setSelection(if (index >= 0) index + 1 else 0)
    }

    private fun send(rawText: String) {
        val text = rawText.trim()
        if (text.isEmpty()) return

        messages += ChatMessage(nextMessageId++, fromUser = true, text = text)
        val reply = AssistantEngine.reply(text, mode, contextProjectId)
        messages += ChatMessage(nextMessageId++, fromUser = false, text = reply.text, drafts = reply.drafts)

        binding.etMessage.text?.clear()
        // Помощник мог создать проект — обновляем список контекстов
        loadContexts()
        renderMessages()
    }

    private fun addDrafts(message: ChatMessage) {
        val added = AssistantEngine.addDrafts(message.drafts, contextProjectId)
        if (added == 0) return
        val index = messages.indexOfFirst { it.id == message.id }
        if (index != -1) messages[index] = messages[index].copy(draftsAdded = true)
        Toast.makeText(this, R.string.assistant_drafts_added, Toast.LENGTH_SHORT).show()
        renderMessages()
    }

    private fun renderMessages() {
        adapter.submitList(messages.toList()) {
            if (messages.isNotEmpty()) binding.rvMessages.scrollToPosition(messages.size - 1)
        }
        binding.welcomeBlock.isVisible = messages.isEmpty()
        binding.rvMessages.isVisible = messages.isNotEmpty()
    }

    private fun confirmClear() {
        if (messages.isEmpty()) return
        MaterialAlertDialogBuilder(this)
            .setTitle(R.string.assistant_clear_title)
            .setNegativeButton(R.string.action_cancel, null)
            .setPositiveButton(R.string.action_clear_chat) { _, _ ->
                messages.clear()
                renderMessages()
            }
            .show()
    }

    companion object {
        private const val EXTRA_PROJECT_ID = "project_id"

        fun intent(context: Context, projectId: Long?): Intent =
            Intent(context, AssistantActivity::class.java).apply {
                if (projectId != null) putExtra(EXTRA_PROJECT_ID, projectId)
            }
    }
}
