package com.example.sipi_ai.util

import android.content.Context
import androidx.appcompat.app.AppCompatDelegate

enum class ThemeChoice(val storedValue: String, val nightMode: Int) {
    SYSTEM("system", AppCompatDelegate.MODE_NIGHT_FOLLOW_SYSTEM),
    LIGHT("light", AppCompatDelegate.MODE_NIGHT_NO),
    DARK("dark", AppCompatDelegate.MODE_NIGHT_YES),
}

object ThemeSettings {
    private const val PREFS = "display_preferences"
    private const val KEY_THEME = "theme_choice"

    fun choice(context: Context): ThemeChoice {
        val stored = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_THEME, ThemeChoice.SYSTEM.storedValue)
        return ThemeChoice.entries.firstOrNull { it.storedValue == stored } ?: ThemeChoice.SYSTEM
    }

    fun apply(context: Context) {
        AppCompatDelegate.setDefaultNightMode(choice(context).nightMode)
    }

    fun select(context: Context, choice: ThemeChoice) {
        if (choice(context) == choice) return
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(KEY_THEME, choice.storedValue)
            .apply()
        AppCompatDelegate.setDefaultNightMode(choice.nightMode)
    }
}
