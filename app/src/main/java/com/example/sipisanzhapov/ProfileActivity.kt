package com.example.sipisanzhapov

import android.os.Bundle
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.widget.Toolbar

class ProfileActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_profile)

        // Подключаем тулбар и показываем стрелку назад
        val toolbar = findViewById<Toolbar>(R.id.toolbarProfile)
        setSupportActionBar(toolbar)
        supportActionBar?.setDisplayHomeAsUpEnabled(true)

        val tvName = findViewById<TextView>(R.id.tvProfileName)
        val tvEmail = findViewById<TextView>(R.id.tvProfileEmail)

        // Читаем сохраненные данные из SharedPreferences
        val sharedPreferences = getSharedPreferences("UserPrefs", MODE_PRIVATE)
        tvName.text = sharedPreferences.getString("USER_NAME", "Имя не указано")
        tvEmail.text = sharedPreferences.getString("USER_EMAIL", "Email не указан")
    }

    // Нажатие на стрелку назад: закрываем экран и возвращаемся в главное меню
    override fun onSupportNavigateUp(): Boolean {
        finish()
        return true
    }
}