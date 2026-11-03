package com.example.sipi_ai // ВАЖНО: проверь, чтобы пакет совпадал с твоим!

import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import com.example.sipi_ai.ui.register.RegisterActivity
import com.example.sipi_ai.ui.register.VerifyCodeActivity

class LoginActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_login)

        val btnLogin = findViewById<Button>(R.id.btnLogin)
        val tvGoToRegister = findViewById<TextView>(R.id.tvGoToRegister)

        // Переход на экран ввода кода
        // Находим поле ввода почты
        val etLoginEmail = findViewById<android.widget.EditText>(R.id.etLoginEmail)

        tvGoToRegister.setOnClickListener {
            val intent = Intent(this, RegisterActivity::class.java)
            startActivity(intent)
        }

        btnLogin.setOnClickListener {
            // Берем текст, который пользователь ввел в поле
            val email = etLoginEmail.text.toString().trim()

            // Проверяем, не пустое ли поле (чтобы не отправлять пустоту)
            if (email.isEmpty()) {
                android.widget.Toast.makeText(this, "Введите почту", android.widget.Toast.LENGTH_SHORT).show()
                return@setOnClickListener // Останавливаем код, если поле пустое
            }

            // Создаем намерение перейти на экран кода
            val intent = Intent(this, VerifyCodeActivity::class.java)

            // Передаем РЕАЛЬНУЮ почту, которую ввел пользователь
            intent.putExtra("USER_EMAIL", email)

            startActivity(intent)
        }
    }
}