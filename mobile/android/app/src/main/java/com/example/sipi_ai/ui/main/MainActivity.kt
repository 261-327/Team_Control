package com.example.sipi_ai.ui.main

import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import androidx.activity.SystemBarStyle
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.ActionBarDrawerToggle
import androidx.appcompat.app.AppCompatActivity
import androidx.viewpager2.widget.ViewPager2
import com.example.sipi_ai.R
import com.example.sipi_ai.data.TaskStatus
import com.example.sipi_ai.data.UserStore
import com.example.sipi_ai.databinding.ActivityMainBinding
import com.example.sipi_ai.databinding.NavHeaderBinding
import com.example.sipi_ai.ui.calendar.CalendarActivity
import com.example.sipi_ai.ui.profile.ProfileActivity

private data class Tab(val menuItemId: Int, val status: TaskStatus)

class MainActivity : AppCompatActivity() {

    private val tabs = listOf(
        Tab(R.id.nav_urgent, TaskStatus.URGENT),
        Tab(R.id.nav_in_progress, TaskStatus.IN_PROGRESS),
        Tab(R.id.nav_review, TaskStatus.REVIEW),
        Tab(R.id.nav_backlog, TaskStatus.BACKLOG),
    )

    private lateinit var binding: ActivityMainBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge(statusBarStyle = SystemBarStyle.light(Color.TRANSPARENT, Color.TRANSPARENT))
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setUpToolbarAndDrawer()
        setUpTabs()
    }

    private fun setUpToolbarAndDrawer() {
        setSupportActionBar(binding.toolbar)
        supportActionBar?.setDisplayShowTitleEnabled(false)

        // DrawerLayout сам рисует фон под статус-баром цветом colorPrimaryDark из темы
        binding.drawerLayout.setStatusBarBackgroundColor(getColor(R.color.beige))

        val header = NavHeaderBinding.bind(binding.navView.getHeaderView(0))
        val user = UserStore(this)
        header.tvHeaderName.text = user.fullName ?: getString(R.string.profile_name_missing)
        header.tvHeaderEmail.text = user.email ?: getString(R.string.profile_email_missing)

        val toggle = ActionBarDrawerToggle(
            this,
            binding.drawerLayout,
            binding.toolbar,
            R.string.navigation_drawer_open,
            R.string.navigation_drawer_close,
        )
        binding.drawerLayout.addDrawerListener(toggle)
        toggle.syncState()

        binding.navView.setNavigationItemSelectedListener { item ->
            when (item.itemId) {
                R.id.nav_profile -> startActivity(Intent(this, ProfileActivity::class.java))
                R.id.nav_calendar -> startActivity(Intent(this, CalendarActivity::class.java))
            }
            binding.drawerLayout.closeDrawers()
            true
        }
    }

    //Ты что реально читаешь PR? У тебя ребятки слабенькие(
    private fun setUpTabs() {
        binding.viewPager.adapter = TaskPagerAdapter(this, tabs.map { it.status })

        binding.viewPager.registerOnPageChangeCallback(object : ViewPager2.OnPageChangeCallback() {
            override fun onPageSelected(position: Int) {
                binding.bottomNavigationView.menu.findItem(tabs[position].menuItemId).isChecked = true
            }
        })

        binding.bottomNavigationView.setOnItemSelectedListener { item ->
            val page = tabs.indexOfFirst { it.menuItemId == item.itemId }
            if (page != -1) binding.viewPager.currentItem = page
            page != -1
        }
    }
}
