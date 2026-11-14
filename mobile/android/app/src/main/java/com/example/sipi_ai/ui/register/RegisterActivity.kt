package com.example.sipi_ai.ui.register

import android.content.Intent
import android.os.Bundle
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
