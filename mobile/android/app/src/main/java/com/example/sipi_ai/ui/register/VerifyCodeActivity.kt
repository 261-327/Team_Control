package com.example.sipi_ai.ui.register // Твой пакет!

import com.example.sipi_ai.R
import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.example.sipi_ai.ui.main.MainActivity

class VerifyCodeActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_verify_code)

        val etCode = findViewById<android.widget.EditText>(R.id.etCode)
        val btnVerify = findViewById<Button>(R.id.btnVerify)
        val tvEmailSubtitle = findViewById<TextView>(R.id.tvEmailSubtitle)

        // Получаем почту, которую передали с предыдущего экрана
        val userEmail = intent.getStringExtra("USER_EMAIL") ?: "вашу почту"
        tvEmailSubtitle.text = "Код отправлен на $userEmail"

        btnVerify.setOnClickListener {
            val code = etCode.text.toString().trim()
            // Заглушка: правильный код - 1234
            if (code == "1234") {
                // Успех! Переходим на главный экран и очищаем историю (чтобы нельзя было вернуться назад)
                val intent = Intent(this, MainActivity::class.java)
                intent.flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
                startActivity(intent)
            } else {
                Toast.makeText(this, "Неверный код (введите 1234)", Toast.LENGTH_SHORT).show()
            }
        }
    }
}