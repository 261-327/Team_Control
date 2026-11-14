package com.example.sipi_ai.data

import android.content.Context
import androidx.core.content.edit

class UserStore(context: Context) {

    private val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    val fullName: String?
        get() = prefs.getString(KEY_FULL_NAME, null)

    val email: String?
        get() = prefs.getString(KEY_EMAIL, null)

    val about: String
        get() = prefs.getString(KEY_ABOUT, null).orEmpty()

    val serverId: Long?
        get() = prefs.getString(KEY_SERVER_ID, null)?.toLongOrNull()

    fun save(fullName: String, email: String) {
        prefs.edit {
            putString(KEY_FULL_NAME, fullName)
            putString(KEY_EMAIL, email)
        }
    }

    fun saveIdentity(fullName: String, email: String, serverId: String) {
        prefs.edit {
            putString(KEY_FULL_NAME, fullName)
            putString(KEY_EMAIL, email)
            putString(KEY_SERVER_ID, serverId)
        }
    }

    fun saveProfile(fullName: String, about: String) {
        prefs.edit {
            putString(KEY_FULL_NAME, fullName)
            putString(KEY_ABOUT, about)
        }
    }

    fun clear() {
        prefs.edit { clear() }
    }

    private companion object {
        const val PREFS_NAME = "UserPrefs"
        const val KEY_FULL_NAME = "USER_NAME"
        const val KEY_EMAIL = "USER_EMAIL"
        const val KEY_ABOUT = "USER_ABOUT"
        const val KEY_SERVER_ID = "USER_SERVER_ID"
    }
}
