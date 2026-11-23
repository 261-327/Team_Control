package com.example.sipi_ai.ui.register

import android.content.Intent
import android.os.Bundle
import android.graphics.Rect
import android.text.InputType
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.example.sipi_ai.R
import com.example.sipi_ai.data.ApiClient
import com.example.sipi_ai.databinding.ActivityLoginBinding

class LoginActivity : AppCompatActivity() {
    private lateinit var binding: ActivityLoginBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityLoginBinding.inflate(layoutInflater)
        setContentView(binding.root)
        ApiClient.initialize(this)

        // Android 15+ keeps edge-to-edge layouts behind the IME even when
        // adjustResize is requested. Apply the IME inset to the scroll view
        // and bring the focused field into the visible area explicitly.
        ViewCompat.setOnApplyWindowInsetsListener(binding.root) { view, insets ->
            val imeBottom = insets.getInsets(WindowInsetsCompat.Type.ime()).bottom
            val navigationBottom = insets.getInsets(WindowInsetsCompat.Type.navigationBars()).bottom
            view.setPadding(view.paddingLeft, view.paddingTop, view.paddingRight, maxOf(imeBottom, navigationBottom))
            if (insets.isVisible(WindowInsetsCompat.Type.ime())) {
                view.post {
                    currentFocus?.let { focused ->
                        focused.post {
                            focused.requestRectangleOnScreen(Rect(0, 0, focused.width, focused.height), true)
                        }
                    }
                }
            }
            insets
        }
        ViewCompat.requestApplyInsets(binding.root)

        var passwordVisible = false
        binding.btnTogglePassword.setOnClickListener {
            val cursor = binding.etLoginPassword.selectionStart
            passwordVisible = !passwordVisible
            binding.etLoginPassword.inputType = if (passwordVisible) {
                InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD
            } else {
                InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
            }
            if (cursor >= 0) binding.etLoginPassword.setSelection(cursor.coerceAtMost(binding.etLoginPassword.length()))
            binding.btnTogglePassword.animate().cancel()
            binding.btnTogglePassword.animate().alpha(0f).setDuration(90).withEndAction {
                binding.btnTogglePassword.setImageResource(
                if (passwordVisible) R.drawable.ic_visibility else R.drawable.ic_visibility_off,
                )
                binding.btnTogglePassword.animate().alpha(1f).setDuration(130).start()
            }.start()
            binding.btnTogglePassword.setContentDescription(
                getString(if (passwordVisible) R.string.password_hide else R.string.password_show),
            )
        }

        binding.tvGoToRegister.setOnClickListener {
            startActivity(Intent(this, RegisterActivity::class.java))
        }
        binding.tvForgotPassword.setOnClickListener {
            startActivity(Intent(this, ForgotPasswordActivity::class.java))
        }
        binding.btnLogin.setOnClickListener {
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

    private fun showError(error: Throwable) {
        Toast.makeText(this, error.message ?: getString(R.string.login_error_empty_email), Toast.LENGTH_LONG).show()
    }
}
