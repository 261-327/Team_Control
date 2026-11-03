package com.example.sipi_ai.ui.register

import android.view.View
import android.widget.AdapterView
import android.content.Intent
import android.os.Bundle
import android.widget.ArrayAdapter
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.example.sipi_ai.R
import com.example.sipi_ai.data.UserStore
import com.example.sipi_ai.databinding.ActivityRegisterBinding
// ВАЖНО: Нам нужно будет создать VerifyCodeActivity.
// Пока импорт может гореть красным, мы создадим его на следующем шаге.
// import com.example.sipi_ai.ui.verify.VerifyCodeActivity

class RegisterActivity : AppCompatActivity() {

    private lateinit var binding: ActivityRegisterBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityRegisterBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupSpinner()

        binding.btnRegister.setOnClickListener { register() }
    }

    private fun setupSpinner() {
        val roles = arrayOf("Студент", "Преподаватель")
        val adapter = ArrayAdapter(this, android.R.layout.simple_spinner_item, roles)
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item)
        binding.spinnerRole.adapter = adapter

        // Магия: следим за выбором
        binding.spinnerRole.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                val selectedRole = parent?.getItemAtPosition(position).toString()

                if (selectedRole == "Студент") {
                    // Показываем группу
                    binding.llGroupContainer.visibility = View.VISIBLE
                } else {
                    // Прячем группу и ОЧИЩАЕМ текст в ней, чтобы не ушло пустым
                    binding.llGroupContainer.visibility = View.GONE
                    binding.etGroup.text?.clear()
                }
            }

            override fun onNothingSelected(parent: AdapterView<*>?) {
                // Оставляем пустым (обязательный метод)
            }
        }
    }

    private fun register() {
        val fullName = binding.etFullName.text.toString().trim()
        val email = binding.etEmail.text.toString().trim()
        val role = binding.spinnerRole.selectedItem.toString()
        val group = binding.etGroup.text.toString().trim()

        // Проверяем поля. Группу проверяем ТОЛЬКО если это студент!
        if (fullName.isEmpty() || email.isEmpty() || (role == "Студент" && group.isEmpty())) {
            Toast.makeText(this, "Заполните все обязательные поля", Toast.LENGTH_SHORT).show()
            return
        }

        UserStore(this).save(fullName, email)

        Toast.makeText(this, "Регистрация успешна!", Toast.LENGTH_SHORT).show()

        val intent = Intent(this, VerifyCodeActivity::class.java)
        intent.putExtra("USER_EMAIL", email)
        startActivity(intent)
        finish()
    }
}