package com.example.sipi_ai.ui.assistant

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
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
import com.example.sipi_ai.data.ApiClient
import com.example.sipi_ai.data.Member
import com.example.sipi_ai.data.Members
import com.example.sipi_ai.data.Project
import com.example.sipi_ai.data.ProjectRepository
import com.example.sipi_ai.data.UserStore
import com.example.sipi_ai.databinding.ActivityAssistantBinding
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

/** Android клиент того же серверного помощника, которым пользуется сайт. */
class AssistantActivity : AppCompatActivity() {

    private lateinit var binding: ActivityAssistantBinding
    private val messages = mutableListOf<ChatMessage>()
    private var nextMessageId = 1L
    private val handler = Handler(Looper.getMainLooper())

    private var mode = AssistantMode.CHAT
    private var contextProjectId: Long? = null
    private var projects: List<Project> = emptyList()
    private var chatReady = false
    private var imagesReady = false
    private var loadingHistory = false
    private var busy = false

    private val adapter = MessageAdapter { message -> addDrafts(message) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityAssistantBinding.inflate(layoutInflater)
        setContentView(binding.root)
        ApiClient.initialize(this)

        setSupportActionBar(binding.toolbarAssistant)
        supportActionBar?.setDisplayHomeAsUpEnabled(true)
        contextProjectId = intent.getLongExtra(EXTRA_PROJECT_ID, -1L).takeIf { it != -1L }

        binding.rvMessages.layoutManager = LinearLayoutManager(this).also { it.stackFromEnd = true }
        binding.rvMessages.adapter = adapter
        loadContexts()
        binding.spinnerContext.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                val selected = if (position == 0) null else projects.getOrNull(position - 1)?.id
                if (!loadingHistory && selected != contextProjectId) {
                    contextProjectId = selected
                    messages.clear()
                    renderMessages()
                    loadHistory()
                }
            }
            override fun onNothingSelected(parent: AdapterView<*>?) = Unit
        }

        binding.toggleAssistantMode.addOnButtonCheckedListener { _, checkedId, isChecked ->
            if (!isChecked) return@addOnButtonCheckedListener
            mode = when (checkedId) {
                R.id.btnModeDrafts -> AssistantMode.TASKS
                R.id.btnModeLogo -> AssistantMode.LOGO
                else -> AssistantMode.CHAT
            }
            binding.etMessage.setHint(when (mode) {
                AssistantMode.TASKS -> R.string.assistant_input_hint_drafts
                AssistantMode.LOGO -> R.string.assistant_input_hint_logo
                AssistantMode.CHAT -> R.string.assistant_input_hint_assistant
            })
            updateAvailability()
        }

        binding.etMessage.doAfterTextChanged {
            binding.tvMessageCounter.text = getString(R.string.assistant_counter, it?.length ?: 0)
        }
        binding.tvMessageCounter.text = getString(R.string.assistant_counter, 0)
        binding.btnSendMessage.setOnClickListener { send(binding.etMessage.text.toString()) }
        binding.chipDeadlines.setOnClickListener {
            binding.etMessage.setText("Что осталось сделать по проекту? Покажи ближайшие сроки и задачи, которым нужно внимание.")
            binding.etMessage.setSelection(binding.etMessage.text.length)
        }
        binding.chipCreate.setOnClickListener {
            binding.etMessage.setText(R.string.assistant_suggest_create)
            binding.etMessage.setSelection(binding.etMessage.text.length)
        }
        loadHistory()
    }

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        super.onDestroy()
    }

    override fun onCreateOptionsMenu(menu: Menu): Boolean {
        menuInflater.inflate(R.menu.menu_assistant, menu)
        return true
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean = when (item.itemId) {
        R.id.action_clear_chat -> { confirmClear(); true }
        else -> super.onOptionsItemSelected(item)
    }

    override fun onSupportNavigateUp(): Boolean { finish(); return true }

    private fun loadContexts() {
        projects = ProjectRepository.all()
        val labels = listOf(getString(R.string.calendar_all_projects)) + projects.map { it.name }
        binding.spinnerContext.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_item, labels).also {
            it.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item)
        }
        val index = projects.indexOfFirst { it.id == contextProjectId }
        binding.spinnerContext.setSelection(if (index >= 0) index + 1 else 0)
    }

    private fun loadHistory() {
        loadingHistory = true
        busy = true
        updateAvailability()
        ApiClient.assistantHistory(contextProjectId) { result ->
            loadingHistory = false
            busy = false
            result.onSuccess { response ->
                val capabilities = response.optJSONObject("capabilities")
                chatReady = capabilities?.optBoolean("chatReady") == true
                imagesReady = capabilities?.optBoolean("imagesReady") == true
                messages.clear()
                val turns = response.optJSONArray("turns") ?: JSONArray()
                val pendingIds = mutableListOf<String>()
                for (i in 0 until turns.length()) {
                    val turn = turns.optJSONObject(i) ?: continue
                    val turnId = turn.optString("id")
                    val userId = nextMessageId++
                    messages += ChatMessage(userId, true, turn.optString("message"), turnId = turnId)
                    val status = turn.optString("status")
                    if (status == "queued" || status == "running") {
                        pendingIds += turnId
                        messages += ChatMessage(nextMessageId++, false, getString(R.string.assistant_pending), turnId = turnId, pending = true)
                    } else {
                        appendFinalTurn(turn, null)
                    }
                }
                busy = pendingIds.isNotEmpty()
                updateAvailability()
                renderMessages()
                pendingIds.forEach { pollTurn(it) }
            }.onFailure {
                binding.tvAssistantStatus.text = it.message ?: getString(R.string.assistant_unavailable)
                Toast.makeText(this, it.message ?: "Не удалось загрузить чат", Toast.LENGTH_LONG).show()
            }
        }
    }

    private fun updateAvailability() {
        if (!::binding.isInitialized) return
        binding.tvAssistantStatus.text = when {
            loadingHistory -> getString(R.string.assistant_connecting)
            mode == AssistantMode.LOGO && imagesReady -> getString(R.string.assistant_ready)
            mode == AssistantMode.LOGO -> getString(R.string.assistant_logo_unavailable)
            chatReady -> getString(R.string.assistant_ready)
            else -> getString(R.string.assistant_unavailable)
        }
        binding.btnSendMessage.isEnabled = !busy && !loadingHistory &&
            (if (mode == AssistantMode.LOGO) imagesReady else chatReady) &&
            (mode != AssistantMode.TASKS || contextProjectId != null)
    }

    private fun send(rawText: String) {
        val text = rawText.trim()
        if (text.isEmpty() || busy) return
        if (mode == AssistantMode.TASKS && contextProjectId == null) {
            Toast.makeText(this, R.string.assistant_select_project, Toast.LENGTH_SHORT).show()
            return
        }
        val ready = if (mode == AssistantMode.LOGO) imagesReady else chatReady
        if (!ready) {
            Toast.makeText(this, if (mode == AssistantMode.LOGO) R.string.assistant_logo_unavailable else R.string.assistant_unavailable, Toast.LENGTH_LONG).show()
            return
        }

        val requestId = UUID.randomUUID().toString()
        val userMessageId = nextMessageId++
        val waitingId = nextMessageId++
        messages += ChatMessage(userMessageId, true, text, turnId = requestId)
        messages += ChatMessage(waitingId, false, getString(R.string.assistant_pending), turnId = requestId, pending = true)
        binding.etMessage.text?.clear()
        busy = true
        updateAvailability()
        renderMessages()

        ApiClient.askAssistant(text, mode.apiValue, contextProjectId, requestId) { result ->
            result.onSuccess { response ->
                applySnapshotIfPresent(response)
                val turn = response.optJSONObject("turn")
                if (turn == null) finishWithError(requestId, "Сервер вернул пустой ответ.")
                else if (isInFlight(turn)) pollTurn(requestId)
                else finishTurn(turn, waitingId)
            }.onFailure { finishWithError(requestId, it.message ?: "Не удалось связаться с помощником.") }
        }
    }

    private fun pollTurn(turnId: String) {
        handler.postDelayed({
            if (isFinishing || isDestroyed) return@postDelayed
            ApiClient.assistantTurn(turnId) { result ->
                result.onSuccess { response ->
                    applySnapshotIfPresent(response)
                    val turn = response.optJSONObject("turn")
                    if (turn == null) finishWithError(turnId, "Не удалось получить ответ помощника.")
                    else if (isInFlight(turn)) pollTurn(turnId)
                    else {
                        val waitingId = messages.lastOrNull { it.turnId == turnId && it.pending }?.id
                        finishTurn(turn, waitingId)
                    }
                }.onFailure {
                    // A transient poll failure should not discard a request that is still running.
                    pollTurn(turnId)
                }
            }
        }, 1500)
    }

    private fun finishTurn(turn: JSONObject, waitingId: Long?) {
        busy = false
        val status = turn.optString("status")
        if (status == "succeeded") {
            appendFinalTurn(turn, waitingId)
        } else {
            val error = when (status) {
                "cancelled" -> getString(R.string.assistant_cancelled)
                else -> turn.optString("error").ifBlank { "Не удалось подготовить ответ." }
            }
            replaceWaiting(waitingId, ChatMessage(nextMessageId++, false, error, turnId = turn.optString("id")))
        }
        updateAvailability()
        loadContexts()
        renderMessages()
    }

    private fun appendFinalTurn(turn: JSONObject, waitingId: Long?) {
        val reply = turn.optJSONObject("reply") ?: JSONObject()
        val drafts = mutableListOf<AssistantTaskDraft>()
        val rawDrafts = reply.optJSONArray("drafts") ?: JSONArray()
        for (i in 0 until rawDrafts.length()) {
            val draft = rawDrafts.optJSONObject(i) ?: continue
            drafts += AssistantTaskDraft(
                title = draft.optString("title"),
                description = draft.optString("description"),
                tag = draft.optString("tag"),
                assigneeId = draft.optString("assigneeId"),
                deadlineAt = draft.optString("deadlineAt"),
            )
        }
        val text = buildString {
            append(reply.optString("text").ifBlank { "Готово." })
            if (drafts.isNotEmpty()) {
                append("\n\n")
                drafts.forEachIndexed { index, draft ->
                    append("${index + 1}. ${draft.title}")
                    if (draft.description.isNotBlank()) append("\n${draft.description}")
                    append("\n")
                }
            }
            val sources = reply.optJSONArray("sources") ?: JSONArray()
            if (sources.length() > 0) {
                append("\nИсточники:")
                for (i in 0 until sources.length()) append("\n• ${sources.optJSONObject(i)?.optString("title") ?: "Материал проекта"}")
            }
        }.trim()
        val turnId = turn.optString("id")
        val imageUrl = reply.optString("imageUrl")
        val message = ChatMessage(
            id = waitingId ?: nextMessageId++,
            fromUser = false,
            text = text,
            turnId = turnId,
            drafts = drafts,
            draftsAdded = turn.optString("confirmedAt").isNotBlank(),
            imageLoading = imageUrl.isNotBlank(),
        )
        replaceWaiting(waitingId, message)
        if (imageUrl.isNotBlank()) {
            ApiClient.loadAssistantImage(turnId) { result ->
                result.onSuccess { bitmap ->
                    val index = messages.indexOfFirst { it.turnId == turnId && !it.fromUser }
                    if (index >= 0) messages[index] = messages[index].copy(image = bitmap, imageLoading = false)
                    renderMessages()
                }.onFailure {
                    val index = messages.indexOfFirst { it.turnId == turnId && !it.fromUser }
                    if (index >= 0) messages[index] = messages[index].copy(imageLoading = false, text = messages[index].text + "\n\nНе удалось загрузить файл логотипа: ${it.message.orEmpty()}")
                    renderMessages()
                }
            }
        }
    }

    private fun replaceWaiting(waitingId: Long?, message: ChatMessage) {
        val index = waitingId?.let { id -> messages.indexOfFirst { it.id == id } } ?: -1
        if (index >= 0) messages[index] = message
        else {
            val duplicateIndex = messages.indexOfFirst { it.turnId == message.turnId && !it.fromUser }
            if (duplicateIndex >= 0) messages[duplicateIndex] = message else messages += message
        }
    }

    private fun finishWithError(turnId: String, error: String) {
        busy = false
        val waitingId = messages.lastOrNull { it.turnId == turnId && it.pending }?.id
        replaceWaiting(waitingId, ChatMessage(nextMessageId++, false, error, turnId = turnId))
        updateAvailability()
        renderMessages()
    }

    private fun addDrafts(message: ChatMessage) {
        val turnId = message.turnId ?: return
        val projectId = contextProjectId ?: return
        val project = ProjectRepository.get(projectId) ?: return
        val currentServerId = UserStore(this).serverId
        val members = project.memberIds.mapNotNull { id ->
            when (id) {
                Members.ME_ID -> currentServerId?.let { Member(it, UserStore(this).fullName ?: "Я") }
                else -> ProjectRepository.invitedMember(id)
            }
        }.distinctBy { it.id }
        if (members.isEmpty()) {
            Toast.makeText(this, "Не удалось загрузить участников проекта", Toast.LENGTH_LONG).show()
            return
        }
        chooseDraftAssignees(message, turnId, members, 0, message.drafts.toMutableList())
    }

    private fun chooseDraftAssignees(
        message: ChatMessage,
        turnId: String,
        members: List<Member>,
        index: Int,
        drafts: MutableList<AssistantTaskDraft>,
    ) {
        if (index >= drafts.size) {
            saveDraftTasks(message, turnId, drafts)
            return
        }
        val options = members.map { it.name }.toTypedArray()
        MaterialAlertDialogBuilder(this)
            .setTitle("Выбери исполнителя: ${drafts[index].title}")
            .setItems(options) { _, selected ->
                drafts[index] = drafts[index].copy(assigneeId = members[selected].id.toString())
                chooseDraftAssignees(message, turnId, members, index + 1, drafts)
            }
            .setNegativeButton(R.string.action_cancel, null)
            .show()
    }

    private fun saveDraftTasks(message: ChatMessage, turnId: String, drafts: List<AssistantTaskDraft>) {
        val tasks = JSONArray().apply {
            drafts.forEach { draft ->
                put(JSONObject().put("title", draft.title).put("description", draft.description)
                    .put("tag", draft.tag).put("assigneeId", draft.assigneeId).put("deadlineAt", draft.deadlineAt))
            }
        }
        busy = true
        updateAvailability()
        ApiClient.confirmAssistantTasks(turnId, tasks) { result ->
            busy = false
            result.onSuccess { response ->
                applySnapshotIfPresent(response)
                val index = messages.indexOfFirst { it.id == message.id }
                if (index >= 0) messages[index] = messages[index].copy(draftsAdded = true, drafts = drafts)
                Toast.makeText(this, R.string.assistant_drafts_added, Toast.LENGTH_SHORT).show()
                renderMessages()
            }.onFailure { Toast.makeText(this, it.message ?: "Не удалось создать задачи", Toast.LENGTH_LONG).show() }
            updateAvailability()
        }
    }

    private fun applySnapshotIfPresent(response: JSONObject) {
        if (response.has("snapshot")) ApiClient.applyMutation(response, UserStore(this))
    }

    private fun isInFlight(turn: JSONObject) = turn.optString("status") in listOf("queued", "running")

    private fun renderMessages() {
        adapter.submitList(messages.toList()) {
            if (messages.isNotEmpty()) binding.rvMessages.scrollToPosition(messages.size - 1)
        }
        binding.welcomeBlock.isVisible = messages.isEmpty()
        binding.rvMessages.isVisible = messages.isNotEmpty()
        updateAvailability()
    }

    private fun confirmClear() {
        MaterialAlertDialogBuilder(this)
            .setTitle(R.string.assistant_clear_title)
            .setMessage(R.string.assistant_clear_message)
            .setNegativeButton(R.string.action_cancel, null)
            .setPositiveButton(R.string.action_clear_chat) { _, _ ->
                busy = true
                updateAvailability()
                ApiClient.clearAssistantHistory(contextProjectId) { result ->
                    busy = false
                    result.onSuccess {
                        messages.clear()
                        renderMessages()
                    }.onFailure { Toast.makeText(this, it.message ?: "Не удалось очистить чат", Toast.LENGTH_LONG).show() }
                    updateAvailability()
                }
            }
            .show()
    }

    companion object {
        private const val EXTRA_PROJECT_ID = "project_id"
        fun intent(context: Context, projectId: Long?): Intent = Intent(context, AssistantActivity::class.java).apply {
            if (projectId != null) putExtra(EXTRA_PROJECT_ID, projectId)
        }
    }
}
