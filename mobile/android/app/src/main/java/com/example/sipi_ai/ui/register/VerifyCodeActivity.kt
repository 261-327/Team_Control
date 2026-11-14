package com.example.sipi_ai.ui.register

import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.example.sipi_ai.R
import com.example.sipi_ai.data.ApiClient
import com.example.sipi_ai.databinding.ActivityVerifyCodeBinding
import com.example.sipi_ai.ui.main.MainActivity

class VerifyCodeActivity : AppCompatActivity() {
    private lateinit var binding: ActivityVerifyCodeBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityVerifyCodeBinding.inflate(layoutInflater)
        setContentView(binding.root)
        ApiClient.initialize(this)
        val email = intent.getStringExtra(EXTRA_EMAIL) ?: getString(R.string.verify_email_fallback)
        binding.tvEmailSubtitle.text = getString(R.string.verify_email_subtitle, email)

        binding.btnVerify.setOnClickListener {
            val code = binding.etCode.text.toString().trim()
            binding.btnVerify.isEnabled = false
            ApiClient.verify(code) { result ->
                binding.btnVerify.isEnabled = true
                result.onSuccess {
                    startActivity(Intent(this, MainActivity::class.java).apply {
                        flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
                    })
                    finish()
                }.onFailure {
                    Toast.makeText(this, it.message ?: getString(R.string.verify_error_code), Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    companion object { const val EXTRA_EMAIL = "USER_EMAIL" }
}
