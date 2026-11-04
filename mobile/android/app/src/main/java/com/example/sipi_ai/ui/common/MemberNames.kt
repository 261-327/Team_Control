package com.example.sipi_ai.ui.common

import android.content.Context
import com.example.sipi_ai.R
import com.example.sipi_ai.data.Members
import com.example.sipi_ai.data.ProjectRepository
import com.example.sipi_ai.data.UserStore
import com.example.sipi_ai.util.initials

/** Превращает id участника в имя. Текущий пользователь берётся из профиля. */
class MemberNames(private val context: Context) {

    private val myName: String =
        UserStore(context).fullName ?: context.getString(R.string.profile_name_missing)

    fun of(id: Long?): String = when (id) {
        null -> context.getString(R.string.task_unassigned)
        Members.ME_ID -> myName
        else -> ProjectRepository.invitedMember(id)?.name ?: context.getString(R.string.profile_name_missing)
    }

    fun initialsOf(id: Long?): String = if (id == null) "" else initials(of(id))
}
