package com.example.sipi_ai.data

import android.content.Context
import android.os.Handler
import android.os.Looper
import com.example.sipi_ai.BuildConfig
import com.example.sipi_ai.util.projectKey
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.time.Instant
import java.util.concurrent.Executors

/** Session and CSRF aware client for the Django API shared with the website. */
object ApiClient {
    val siteBaseUrl: String get() = BuildConfig.API_BASE_URL.removeSuffix("api/")
    private const val PREFS = "sipi_api_session"
    private val io = Executors.newSingleThreadExecutor()
    private val main = Handler(Looper.getMainLooper())
    private lateinit var app: Context
    private var csrf: String? = null

    fun initialize(context: Context) {
        app = context.applicationContext
        csrf = app.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString("csrf", null)
    }

    fun warmUp(done: (Result<Unit>) -> Unit) = request("GET", "bootstrap/", null) { done(it.map { Unit }) }

    fun login(username: String, password: String, done: (Result<String>) -> Unit) = post(
        "auth/login/", JSONObject().put("username", username).put("password", password), done
    ) { it.optString("email", username) }

    fun register(name: String, username: String, email: String, password: String, done: (Result<String>) -> Unit) = post(
        "auth/register/", JSONObject().put("name", name).put("username", username)
            .put("email", email).put("password", password).put("passwordConfirm", password), done
    ) { it.optString("email", email) }

    fun verify(code: String, done: (Result<Unit>) -> Unit) = post(
        "auth/verify/", JSONObject().put("code", code), done
    ) { Unit }

    fun logout(done: (Result<JSONObject>) -> Unit) = post("auth/logout/", JSONObject(), done) { it }

    fun updateProfile(name: String, bio: String, done: (Result<JSONObject>) -> Unit) = post(
        "profile/", JSONObject().put("name", name).put("bio", bio), done, "PATCH"
    ) { it }

    fun clearSession() {
        app.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().clear().apply()
        csrf = null
    }

    fun loadSnapshot(done: (Result<JSONObject>) -> Unit) = request("GET", "bootstrap/", null, done)

    fun applyMutation(response: JSONObject, userStore: UserStore) {
        applySnapshot(response.optJSONObject("snapshot") ?: response, userStore)
    }

    fun moveTask(taskId: Long, status: String, done: (Result<JSONObject>) -> Unit, reason: String? = null) = post(
        "tasks/$taskId/move/", JSONObject().put("status", status).put("reason", reason.orEmpty()), done
    ) { it }

    fun createProject(
        name: String,
        description: String,
        profession: String = "developer",
        specialization: String = "android",
        done: (Result<JSONObject>) -> Unit,
    ) = post(
        "projects/", JSONObject().put("name", name).put("description", description)
            .put("role", JSONObject().put("profession", profession)
                .put("specialization", if (profession == "developer") specialization else "")
                .put("customRole", "")), done
    ) { it }

    fun updateProject(projectId: Long, name: String, description: String, done: (Result<JSONObject>) -> Unit) = post(
        "projects/$projectId/settings/", JSONObject().put("name", name).put("description", description), done, "PATCH"
    ) { it }

    fun deleteProject(projectId: Long, done: (Result<JSONObject>) -> Unit) = delete("projects/$projectId/", done)

    fun createTask(projectId: Long, title: String, description: String, assigneeId: Long?, deadlineMillis: Long?, tag: String, done: (Result<JSONObject>) -> Unit) = post(
        "tasks/", taskBody(projectId, title, description, assigneeId, deadlineMillis, tag), done
    ) { it }

    fun updateTask(taskId: Long, projectId: Long, title: String, description: String, assigneeId: Long?, deadlineMillis: Long?, tag: String, done: (Result<JSONObject>) -> Unit) = post(
        "tasks/$taskId/", taskBody(projectId, title, description, assigneeId, deadlineMillis, tag), done, "PATCH"
    ) { it }

    fun deleteTask(taskId: Long, done: (Result<JSONObject>) -> Unit) = delete("tasks/$taskId/", done)

    fun addComment(taskId: Long, text: String, done: (Result<JSONObject>) -> Unit) = post(
        "tasks/$taskId/comments/", JSONObject().put("text", text), done
    ) { it }

    fun invite(projectId: Long, email: String, done: (Result<JSONObject>) -> Unit) = post(
        "projects/$projectId/invitations/", JSONObject().put("email", email), done
    ) { it }

    fun removeMember(projectId: Long, userId: Long, done: (Result<JSONObject>) -> Unit) = delete(
        "projects/$projectId/members/$userId/", done
    )

    fun leaveProject(projectId: Long, done: (Result<JSONObject>) -> Unit) = post(
        "projects/$projectId/leave/", JSONObject(), done
    ) { it }

    fun addMaterial(projectId: Long, title: String, url: String, done: (Result<JSONObject>) -> Unit) = post(
        "projects/$projectId/materials/", JSONObject().put("title", title).put("url", url), done
    ) { it }

    fun deleteMaterial(materialId: Long, done: (Result<JSONObject>) -> Unit) = delete("materials/$materialId/", done)

    private fun taskBody(projectId: Long, title: String, description: String, assigneeId: Long?, deadlineMillis: Long?, tag: String) =
        JSONObject().put("projectId", projectId.toString()).put("title", title).put("description", description)
            .put("assigneeId", assigneeId?.let(::serverUserId)?.toString().orEmpty())
            .put("deadlineAt", deadlineMillis?.let { Instant.ofEpochMilli(it).toString() }.orEmpty())
            .put("tag", tag)

    private fun serverUserId(id: Long): Long = if (id == Members.ME_ID) {
        app.getSharedPreferences("UserPrefs", Context.MODE_PRIVATE).getString("USER_SERVER_ID", null)?.toLongOrNull()
            ?: error("Войдите в аккаунт заново, чтобы назначать задачи")
    } else id

    private fun delete(path: String, done: (Result<JSONObject>) -> Unit) = request("DELETE", path, null, done)

    private fun <T> post(path: String, body: JSONObject, done: (Result<T>) -> Unit, method: String = "POST", map: (JSONObject) -> T) =
        request(method, path, body) { done(it.mapCatching(map)) }

    private fun request(method: String, path: String, body: JSONObject?, done: (Result<JSONObject>) -> Unit) {
        io.execute {
            val result = runCatching {
                // The web host canonicalizes URLs without a trailing slash (308).
                // Its /api catch-all adds Django's required slash before proxying.
                val apiRoot = BuildConfig.API_BASE_URL.trimEnd('/')
                val endpoint = path.trim('/')
                val url = URL("$apiRoot/$endpoint")
                val connection = (url.openConnection() as HttpURLConnection).apply {
                    requestMethod = method
                    connectTimeout = 20000
                    readTimeout = 25000
                    setRequestProperty("Accept", "application/json")
                    setRequestProperty("Origin", "${url.protocol}://${url.host}")
                    app.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString("cookies", null)
                        ?.takeIf { it.isNotBlank() }?.let { setRequestProperty("Cookie", it) }
                    csrf?.let { setRequestProperty("X-CSRFToken", it) }
                    if (body != null) {
                        doOutput = true
                        setRequestProperty("Content-Type", "application/json")
                        outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
                    }
                }
                val setCookies = connection.headerFields.entries.firstOrNull {
                    it.key.equals("Set-Cookie", ignoreCase = true)
                }?.value.orEmpty()
                if (setCookies.isNotEmpty()) {
                    val prefs = app.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                    val cookies = prefs.getString("cookies", "").orEmpty().split("; ")
                        .filter { it.contains('=') }.associate { it.substringBefore('=') to it.substringAfter('=') }.toMutableMap()
                    setCookies.forEach { raw ->
                        val pair = raw.substringBefore(';').trim()
                        val key = pair.substringBefore('=')
                        val value = pair.substringAfter('=', "")
                        if (key == "csrftoken") {
                            csrf = value
                            prefs.edit().putString("csrf", value).apply()
                            cookies[key] = value
                        } else if (key == "sessionid") cookies[key] = value
                    }
                    prefs.edit().putString("cookies", cookies.entries.joinToString("; ") { "${it.key}=${it.value}" }).apply()
                }
                val code = connection.responseCode
                val stream = if (code in 200..299) connection.inputStream else connection.errorStream
                val text = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
                val json = if (text.isBlank()) JSONObject() else JSONObject(text)
                if (code !in 200..299) throw IllegalStateException(
                    json.optJSONObject("error")?.optString("message")?.takeIf { it.isNotBlank() }
                        ?: "Ошибка сервера ($code)"
                )
                json
            }
            main.post { done(result) }
        }
    }

    fun applySnapshot(json: JSONObject, userStore: UserStore) {
        val users = json.optJSONArray("users") ?: JSONArray()
        val currentId = json.optString("sessionId").toLongOrNull()
        val userNames = mutableMapOf<Long, String>()
        var currentName = ""
        var currentEmail = ""
        var currentBio = ""
        for (i in 0 until users.length()) {
            val u = users.optJSONObject(i) ?: continue
            val id = u.optString("id").toLongOrNull() ?: continue
            userNames[id] = u.optString("name").ifBlank { u.optString("username") }
            if (id == currentId) {
                currentName = userNames[id].orEmpty()
                currentEmail = u.optString("email")
                currentBio = u.optString("bio")
            }
        }
        if (currentId != null) userStore.saveIdentity(currentName, currentEmail, currentId.toString())
        if (currentId != null) userStore.saveProfile(currentName, currentBio)

        val memberships = json.optJSONArray("memberships") ?: JSONArray()
        val memberIdsByProject = mutableMapOf<Long, MutableList<Long>>()
        val ownerByProject = mutableMapOf<Long, Long>()
        for (i in 0 until memberships.length()) {
            val m = memberships.optJSONObject(i) ?: continue
            val pid = m.optString("projectId").toLongOrNull() ?: continue
            val uid = m.optString("userId").toLongOrNull() ?: continue
            memberIdsByProject.getOrPut(pid) { mutableListOf() }.add(if (uid == currentId) Members.ME_ID else uid)
            if (m.optString("role") == "leader") ownerByProject[pid] = if (uid == currentId) Members.ME_ID else uid
        }

        val materials = json.optJSONArray("materials") ?: JSONArray()
        val materialNamesByProject = mutableMapOf<Long, MutableList<ProjectMaterial>>()
        for (i in 0 until materials.length()) {
            val item = materials.optJSONObject(i) ?: continue
            val pid = item.optString("projectId").toLongOrNull() ?: continue
            materialNamesByProject.getOrPut(pid) { mutableListOf() }.add(
                ProjectMaterial(item.optString("id").toLongOrNull() ?: continue, item.optString("title"),
                    item.optString("description"), item.optString("url"))
            )
        }

        val projects = json.optJSONArray("projects") ?: JSONArray()
        ProjectRepository.replaceFromServer((0 until projects.length()).mapNotNull { i ->
            val p = projects.optJSONObject(i) ?: return@mapNotNull null
            val id = p.optString("id").toLongOrNull() ?: return@mapNotNull null
            val created = parseMillis(p.optString("createdAt"))
            Project(
                id = id, key = projectKey(p.optString("name")), name = p.optString("name"),
                description = p.optString("description"), season = created?.let { season(it) } ?: "",
                colorIndex = (id % ProjectRepository.COLOR_COUNT).toInt(),
                memberIds = memberIdsByProject[id].orEmpty().distinct(),
                ownerId = ownerByProject[id] ?: Members.ME_ID,
                materials = materialNamesByProject[id].orEmpty(),
            )
        }, userNames.map { (id, name) -> Member(if (id == currentId) Members.ME_ID else id, name) })

        val events = json.optJSONArray("events") ?: JSONArray()
        val eventsByTask = mutableMapOf<Long, MutableList<HistoryEntry>>()
        for (i in 0 until events.length()) {
            val e = events.optJSONObject(i) ?: continue
            val tid = e.optString("taskId").toLongOrNull() ?: continue
            eventsByTask.getOrPut(tid) { mutableListOf() }.add(HistoryEntry(e.optString("text"), parseMillis(e.optString("createdAt")) ?: 0L))
        }
        val comments = json.optJSONArray("comments") ?: JSONArray()
        val commentsByTask = mutableMapOf<Long, MutableList<Comment>>()
        for (i in 0 until comments.length()) {
            val c = comments.optJSONObject(i) ?: continue
            val tid = c.optString("taskId").toLongOrNull() ?: continue
            commentsByTask.getOrPut(tid) { mutableListOf() }.add(
                Comment(c.optString("userId").toLongOrNull()?.let { if (it == currentId) Members.ME_ID else it } ?: Members.ME_ID,
                    c.optString("text"), parseMillis(c.optString("createdAt")) ?: 0L)
            )
        }

        val tasks = json.optJSONArray("tasks") ?: JSONArray()
        TaskRepository.replaceFromServer((0 until tasks.length()).mapNotNull { i ->
            val t = tasks.optJSONObject(i) ?: return@mapNotNull null
            val id = t.optString("id").toLongOrNull() ?: return@mapNotNull null
            val pid = t.optString("projectId").toLongOrNull() ?: return@mapNotNull null
            val assignee = t.optString("assigneeId").toLongOrNull()?.let { if (it == currentId) Members.ME_ID else it }
            Task(
                id = id, projectId = pid, number = (t.optInt("position", i) + 1),
                title = t.optString("title"), description = t.optString("description"),
                status = when (t.optString("status")) {
                    "in_progress" -> TaskStatus.IN_PROGRESS
                    "in_review" -> TaskStatus.REVIEW
                    "done" -> TaskStatus.DONE
                    else -> TaskStatus.TODO
                }, deadlineMillis = parseMillis(t.optString("deadlineAt")),
                direction = t.optString("tag").ifBlank { Directions.TEAM }, assigneeId = assignee,
                authorId = t.optString("createdBy").toLongOrNull()?.let { if (it == currentId) Members.ME_ID else it } ?: Members.ME_ID,
                createdMillis = parseMillis(t.optString("createdAt")) ?: 0L,
                comments = commentsByTask[id].orEmpty(), history = eventsByTask[id].orEmpty(),
            )
        })
    }

    private fun parseMillis(value: String): Long? = value.takeIf { it.isNotBlank() }?.let {
        runCatching { Instant.parse(it).toEpochMilli() }.getOrNull()
    }

    private fun season(millis: Long): String {
        val date = java.time.Instant.ofEpochMilli(millis).atZone(java.time.ZoneId.systemDefault())
        val part = when (date.monthValue) { in 3..5 -> "Весна"; in 6..8 -> "Лето"; in 9..11 -> "Осень"; else -> "Зима" }
        return "$part ${date.year}"
    }
}
