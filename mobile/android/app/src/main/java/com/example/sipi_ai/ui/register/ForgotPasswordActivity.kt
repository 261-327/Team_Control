package com.example.sipi_ai.ui.register

import android.os.Bundle
import android.util.Patterns
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.example.sipi_ai.R
import com.example.sipi_ai.data.ApiClient
import com.example.sipi_ai.databinding.ActivityForgotPasswordBinding

class ForgotPasswordActivity : AppCompatActivity() {
    private lateinit var binding: ActivityForgotPasswordBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityForgotPasswordBinding.inflate(layoutInflater)
        setContentView(binding.root)
        ApiClient.initialize(this)
        binding.btnSendReset.setOnClickListener {
            val email = binding.etResetEmail.text.toString().trim()
            if (!Patterns.EMAIL_ADDRESS.matcher(email).matches()) {
                Toast.makeText(this, R.string.reset_invalid_email, Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            binding.btnSendReset.isEnabled = false
            ApiClient.warmUp { warmUp ->
                warmUp.onSuccess {
                    ApiClient.requestPasswordReset(email) { result ->
                        binding.btnSendReset.isEnabled = true
                        result.onSuccess {
                            binding.tvResetResult.text = getString(R.string.reset_email_sent)
                            binding.tvResetResult.visibility = android.view.View.VISIBLE
                        }.onFailure {
                            Toast.makeText(this, it.message ?: getString(R.string.reset_request_error), Toast.LENGTH_LONG).show()
                        }
                    }
                }.onFailure {
                    binding.btnSendReset.isEnabled = true
                    Toast.makeText(this, it.message ?: getString(R.string.reset_request_error), Toast.LENGTH_LONG).show()
                }
            }
        }
        binding.tvBackToLogin.setOnClickListener { finish() }
    }
}
