package com.example.sipisanzhapov

import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity

class RegisterActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_register)

        val etFullName = findViewById<EditText>(R.id.etFullName)
        val etEmail = findViewById<EditText>(R.id.etEmail)
        val btnRegister = findViewById<Button>(R.id.btnRegister)

        btnRegister.setOnClickListener {
            val fullName = etFullName.text.toString().trim()
            val email = etEmail.text.toString().trim()

            // Черновая проверка заполнения — пока просто Toast
            if (fullName.isEmpty() || email.isEmpty()) {
                Toast.makeText(this, "Заполните все поля", Toast.LENGTH_SHORT).show()
            } else {
                Toast.makeText(
                    this,
                    "Регистрация: $fullName / $email",
                    Toast.LENGTH_SHORT
                ).show()
                val intent = Intent(this, MainActivity::class.java)
                startActivity(intent)
                finish()
                // TODO: здесь будет логика регистрации (Firebase / API и т.п.)
            }
        }
    }
}