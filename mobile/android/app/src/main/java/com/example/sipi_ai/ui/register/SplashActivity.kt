package com.example.sipi_ai.ui.register

import android.content.Intent
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.isVisible
import com.example.sipi_ai.R
import com.example.sipi_ai.data.ApiClient
import com.example.sipi_ai.data.UserStore
import com.example.sipi_ai.databinding.ActivitySplashBinding
import com.example.sipi_ai.ui.main.MainActivity

/** Checks the saved server session before showing the sign-in screen. */
class SplashActivity : AppCompatActivity() {
    private lateinit var binding: ActivitySplashBinding
    private var checkInProgress = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivitySplashBinding.inflate(layoutInflater)
        setContentView(binding.root)
        ApiClient.initialize(this)

        binding.btnRetryStartup.setOnClickListener { checkSession() }
        binding.btnOpenLogin.setOnClickListener { openLogin() }
        checkSession()
    }

    private fun checkSession() {
        if (checkInProgress) return
        checkInProgress = true
        binding.tvStartupMessage.setText(R.string.startup_loading)
        binding.progressStartup.isVisible = true
        binding.btnRetryStartup.isVisible = false
        binding.btnOpenLogin.isVisible = false

        ApiClient.loadSnapshot { result ->
            if (isFinishing || isDestroyed) return@loadSnapshot
            checkInProgress = false
            result.onSuccess { snapshot ->
                if (ApiClient.hasAuthenticatedSession(snapshot)) {
                    ApiClient.applySnapshot(snapshot, UserStore(this))
                    openMain()
                } else {
                    openLogin()
                }
            }.onFailure { error ->
                binding.progressStartup.isVisible = false
                binding.tvStartupMessage.text = getString(
                    R.string.startup_error,
                    error.message ?: getString(R.string.startup_network_error),
                )
                binding.btnRetryStartup.isVisible = true
                binding.btnOpenLogin.isVisible = true
            }
        }
    }

    private fun openMain() = open(MainActivity::class.java)

    private fun openLogin() {
        ApiClient.clearLocalAccountState()
        open(LoginActivity::class.java)
    }

    private fun open(destination: Class<*>) {
        startActivity(Intent(this, destination).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
        })
        finish()
    }
}
