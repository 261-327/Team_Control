package com.example.sipi_ai.ui.register

import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.example.sipi_ai.R
import com.example.sipi_ai.data.UserStore
import com.example.sipi_ai.databinding.ActivityRegisterBinding
import com.example.sipi_ai.ui.main.MainActivity

class RegisterActivity : AppCompatActivity() {

    private lateinit var binding: ActivityRegisterBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityRegisterBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.btnRegister.setOnClickListener { register() }
    }

    private fun register() {
        val fullName = binding.etFullName.text.toString().trim()
        val email = binding.etEmail.text.toString().trim()

        if (fullName.isEmpty() || email.isEmpty()) {
            Toast.makeText(this, R.string.register_error_empty_fields, Toast.LENGTH_SHORT).show()
            return
        }

        UserStore(this).save(fullName, email)
        Toast.makeText(this, getString(R.string.register_success, fullName, email), Toast.LENGTH_SHORT).show()
        startActivity(Intent(this, MainActivity::class.java))
        finish()
    }
}
