package com.example.sipi_ai.ui.profile

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.example.sipi_ai.R
import com.example.sipi_ai.data.UserStore
import com.example.sipi_ai.databinding.ActivityProfileBinding

class ProfileActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val binding = ActivityProfileBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setSupportActionBar(binding.toolbarProfile)
        supportActionBar?.setDisplayHomeAsUpEnabled(true)

        val user = UserStore(this)
        binding.tvProfileName.text = user.fullName ?: getString(R.string.profile_name_missing)
        binding.tvProfileEmail.text = user.email ?: getString(R.string.profile_email_missing)
    }

    override fun onSupportNavigateUp(): Boolean {
        finish()
        return true
    }
}
