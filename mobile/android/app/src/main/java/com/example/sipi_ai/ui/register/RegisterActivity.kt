package com.example.sipi_ai.ui.register

import android.content.Intent
import android.os.Bundle
import android.text.InputType
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.example.sipi_ai.R
import com.example.sipi_ai.data.ApiClient
import com.example.sipi_ai.data.UserStore
import com.example.sipi_ai.databinding.ActivityRegisterBinding

class RegisterActivity : AppCompatActivity() {
    private lateinit var binding: ActivityRegisterBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityRegisterBinding.inflate(layoutInflater)
        setContentView(binding.root)
        ApiClient.initialize(this)
        var passwordVisible = false
        binding.btnTogglePassword.setOnClickListener {
            val cursor = binding.etPassword.selectionStart
            passwordVisible = !passwordVisible
            binding.etPassword.inputType = if (passwordVisible) {
                InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD
            } else {
                InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
            }
            if (cursor >= 0) binding.etPassword.setSelection(cursor.coerceAtMost(binding.etPassword.length()))
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
        binding.btnRegister.setOnClickListener { register() }
    }

    private fun register() {
        val name = binding.etFullName.text.toString().trim()
        val email = binding.etEmail.text.toString().trim()
        val username = binding.etUsername.text.toString().trim()
        val password = binding.etPassword.text.toString()
        if (name.isBlank() || email.isBlank() || username.isBlank() || password.isBlank()) {
            Toast.makeText(this, R.string.register_error_empty_fields, Toast.LENGTH_SHORT).show()
            return
        }

        binding.btnRegister.isEnabled = false
        ApiClient.warmUp { ready ->
            ready.onSuccess {
                ApiClient.register(name, username, email, password) { response ->
                    binding.btnRegister.isEnabled = true
                    response.onSuccess { address ->
                        UserStore(this).save(name, address)
                        startActivity(Intent(this, VerifyCodeActivity::class.java).putExtra(VerifyCodeActivity.EXTRA_EMAIL, address))
                        finish()
                    }.onFailure { showError(it) }
                }
            }.onFailure {
                binding.btnRegister.isEnabled = true
                showError(it)
            }
        }
    }

    private fun showError(error: Throwable) {
        Toast.makeText(this, error.message ?: getString(R.string.register_error_empty_fields), Toast.LENGTH_LONG).show()
    }
}
