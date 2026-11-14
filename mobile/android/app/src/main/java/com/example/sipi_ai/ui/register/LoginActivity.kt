package com.example.sipi_ai.ui.register

import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.example.sipi_ai.R
import com.example.sipi_ai.data.ApiClient
import com.example.sipi_ai.databinding.ActivityLoginBinding
import com.example.sipi_ai.ui.main.MainActivity

class LoginActivity : AppCompatActivity() {
    private lateinit var binding: ActivityLoginBinding
    private var userChoseAuthFlow = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityLoginBinding.inflate(layoutInflater)
        setContentView(binding.root)
        ApiClient.initialize(this)

        val skipRestore = intent.getBooleanExtra(EXTRA_SKIP_SESSION_RESTORE, false)
        if (!skipRestore) ApiClient.loadSnapshot { result ->
            if (!userChoseAuthFlow && !isFinishing && result.getOrNull()?.optString("sessionId").orEmpty().isNotBlank()) openMain()
        }
        binding.tvGoToRegister.setOnClickListener {
            userChoseAuthFlow = true
            startActivity(Intent(this, RegisterActivity::class.java))
        }
        binding.btnLogin.setOnClickListener {
            userChoseAuthFlow = true
            val username = binding.etLoginEmail.text.toString().trim()
            val password = binding.etLoginPassword.text.toString()
            if (username.isBlank() || password.isBlank()) {
                Toast.makeText(this, "Введите логин/почту и пароль", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            binding.btnLogin.isEnabled = false
            ApiClient.warmUp { ready ->
                ready.onSuccess {
                    ApiClient.login(username, password) { response ->
                        binding.btnLogin.isEnabled = true
                        response.onSuccess { email ->
                            startActivity(Intent(this, VerifyCodeActivity::class.java).putExtra(VerifyCodeActivity.EXTRA_EMAIL, email))
                        }.onFailure { showError(it) }
                    }
                }.onFailure {
                    binding.btnLogin.isEnabled = true
                    showError(it)
                }
            }
        }
    }

    private fun openMain() {
        startActivity(Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
        })
        finish()
    }

    private fun showError(error: Throwable) {
        Toast.makeText(this, error.message ?: getString(R.string.login_error_empty_email), Toast.LENGTH_LONG).show()
    }

    companion object {
        const val EXTRA_SKIP_SESSION_RESTORE = "skip_session_restore"
    }
}
