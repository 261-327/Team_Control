package com.example.sipi_ai

import android.app.Application
import com.example.sipi_ai.util.ThemeSettings

class SipiApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        ThemeSettings.apply(this)
    }
}
