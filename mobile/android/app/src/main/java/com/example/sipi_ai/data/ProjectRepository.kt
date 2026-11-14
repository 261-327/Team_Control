package com.example.sipi_ai.data

import com.example.sipi_ai.util.currentSeason
import com.example.sipi_ai.util.projectKey

object ProjectRepository {

    const val COLOR_COUNT = 6

    private var nextProjectId = 1L
    private var nextMemberId = 1L

    /** Приглашённые участники (текущего пользователя здесь нет — он [Members.ME_ID]). */
    private val invited = mutableListOf<Member>()

    private val projects = mutableListOf<Project>()

    fun all(): List<Project> = projects.toList()

    @Synchronized
    fun replaceFromServer(serverProjects: List<Project>, members: List<Member>) {
        projects.clear()
        projects.addAll(serverProjects)
        invited.clear()
        invited.addAll(members.filter { it.id != Members.ME_ID })
        nextProjectId = (serverProjects.maxOfOrNull { it.id } ?: 0L) + 1L
        nextMemberId = (members.maxOfOrNull { it.id } ?: 0L) + 1L
    }

    fun get(id: Long): Project? = projects.firstOrNull { it.id == id }

    fun create(name: String, description: String): Project {
        val id = nextProjectId++
        val project = Project(
            id = id,
            key = projectKey(name),
            name = name.trim(),
            description = description.trim(),
            season = currentSeason(),
            colorIndex = (id % COLOR_COUNT).toInt(),
        )
        projects.add(project)
        return project
    }

    fun update(project: Project) {
        val index = projects.indexOfFirst { it.id == project.id }
        if (index != -1) projects[index] = project
    }

    fun delete(id: Long) {
        projects.removeAll { it.id == id }
        TaskRepository.deleteByProject(id)
    }

    fun invite(projectId: Long, name: String): Member? {
        val project = get(projectId) ?: return null
        val member = Member(nextMemberId++, name.trim())
        invited.add(member)
        update(project.copy(memberIds = project.memberIds + member.id))
        return member
    }

    fun removeMember(projectId: Long, memberId: Long) {
        val project = get(projectId) ?: return
        if (memberId == project.ownerId) return
        update(project.copy(memberIds = project.memberIds - memberId))
    }

    fun invitedMember(id: Long): Member? = invited.firstOrNull { it.id == id }

}
