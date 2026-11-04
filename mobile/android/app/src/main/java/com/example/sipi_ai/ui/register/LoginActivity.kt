package com.example.sipi_ai.ui.register

import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.example.sipi_ai.R
import com.example.sipi_ai.databinding.ActivityLoginBinding

class LoginActivity : AppCompatActivity() {

    private lateinit var binding: ActivityLoginBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityLoginBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.tvGoToRegister.setOnClickListener {
            startActivity(Intent(this, RegisterActivity::class.java))
        }

        binding.btnLogin.setOnClickListener {
            val email = binding.etLoginEmail.text.toString().trim()
            if (email.isEmpty()) {
                Toast.makeText(this, R.string.login_error_empty_email, Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            val intent = Intent(this, VerifyCodeActivity::class.java)
            intent.putExtra(VerifyCodeActivity.EXTRA_EMAIL, email)
            startActivity(intent)
        }
    }
}
