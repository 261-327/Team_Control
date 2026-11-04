package com.example.sipi_ai.ui.register

import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.AdapterView
import android.widget.ArrayAdapter
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.example.sipi_ai.R
import com.example.sipi_ai.data.UserStore
import com.example.sipi_ai.databinding.ActivityRegisterBinding

class RegisterActivity : AppCompatActivity() {

    private lateinit var binding: ActivityRegisterBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityRegisterBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupRoleSpinner()

        binding.btnRegister.setOnClickListener { register() }
    }

    private fun setupRoleSpinner() {
        val adapter = ArrayAdapter.createFromResource(
            this,
            R.array.register_roles,
            android.R.layout.simple_spinner_item
        )
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item)
        binding.spinnerRole.adapter = adapter

        // Группа нужна только студентам
        binding.spinnerRole.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                if (position == ROLE_STUDENT) {
                    binding.llGroupContainer.visibility = View.VISIBLE
                } else {
                    binding.llGroupContainer.visibility = View.GONE
                    binding.etGroup.text?.clear()
                }
            }

            override fun onNothingSelected(parent: AdapterView<*>?) = Unit
        }
    }

    private fun register() {
        val fullName = binding.etFullName.text.toString().trim()
        val email = binding.etEmail.text.toString().trim()
        val isStudent = binding.spinnerRole.selectedItemPosition == ROLE_STUDENT
        val group = binding.etGroup.text.toString().trim()

        if (fullName.isEmpty() || email.isEmpty() || (isStudent && group.isEmpty())) {
            Toast.makeText(this, R.string.register_error_empty_fields, Toast.LENGTH_SHORT).show()
            return
        }

        UserStore(this).save(fullName, email)
        Toast.makeText(this, R.string.register_success, Toast.LENGTH_SHORT).show()

        val intent = Intent(this, VerifyCodeActivity::class.java)
        intent.putExtra(VerifyCodeActivity.EXTRA_EMAIL, email)
        startActivity(intent)
        finish()
    }

    private companion object {
        const val ROLE_STUDENT = 0
    }
}
