package com.example.sipi_ai.ui.main

import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import android.view.Menu
import android.view.MenuItem
import androidx.activity.SystemBarStyle
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.ActionBarDrawerToggle
import androidx.appcompat.app.AppCompatActivity
import androidx.viewpager2.widget.ViewPager2
import com.example.sipi_ai.R
import com.example.sipi_ai.data.ProjectRepository
import com.example.sipi_ai.data.TaskRepository
import com.example.sipi_ai.data.TaskStatus
import com.example.sipi_ai.data.TaskTab
import com.example.sipi_ai.data.UserStore
import com.example.sipi_ai.databinding.ActivityMainBinding
import com.example.sipi_ai.databinding.NavHeaderBinding
import com.example.sipi_ai.ui.calendar.CalendarActivity
import com.example.sipi_ai.ui.common.openAssistant
import com.example.sipi_ai.ui.common.openNewTask
import com.example.sipi_ai.ui.common.openProject
import com.example.sipi_ai.ui.notifications.NotificationsActivity
import com.example.sipi_ai.ui.profile.ProfileActivity
import com.example.sipi_ai.ui.projects.ProjectsActivity
import com.example.sipi_ai.ui.search.SearchActivity
import com.example.sipi_ai.ui.tasks.TaskFragment
import com.example.sipi_ai.ui.team.TeamOverviewActivity
import com.example.sipi_ai.ui.common.showStats
import com.example.sipi_ai.util.initials
import com.google.android.material.dialog.MaterialAlertDialogBuilder

private data class Tab(val menuItemId: Int, val tab: TaskTab)

class MainActivity : AppCompatActivity(), TaskFragment.StatsHost {

    private val tabs = listOf(
        Tab(R.id.nav_urgent, TaskTab.URGENT),
        Tab(R.id.nav_todo, TaskTab.TODO),
        Tab(R.id.nav_in_progress, TaskTab.IN_PROGRESS),
        Tab(R.id.nav_review, TaskTab.REVIEW),
        Tab(R.id.nav_done, TaskTab.DONE),
    )

    private lateinit var binding: ActivityMainBinding
    private lateinit var header: NavHeaderBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge(statusBarStyle = SystemBarStyle.light(Color.TRANSPARENT, Color.TRANSPARENT))
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setUpToolbarAndDrawer()
        setUpTabs()
        binding.fabAssistant.setOnClickListener { openAssistant() }
    }

    override fun onResume() {
        super.onResume()
        refreshHeader()
        refreshDrawerProjects()
        refreshStats()
    }

    override fun onCreateOptionsMenu(menu: Menu): Boolean {
        menuInflater.inflate(R.menu.top_bar_menu, menu)
        return true
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean = when (item.itemId) {
        R.id.action_add_task -> {
            openNewTask()
            true
        }
        R.id.action_search -> {
            startActivity(Intent(this, SearchActivity::class.java))
            true
        }
        R.id.action_notifications -> {
            startActivity(Intent(this, NotificationsActivity::class.java))
            true
        }
        else -> super.onOptionsItemSelected(item)
    }

    override fun refreshStats() {
        val mine = TaskRepository.mine()
        binding.statsRow.showStats(
            listOf(
                R.string.stat_open to mine.count { it.status != TaskStatus.DONE },
                R.string.stat_today to mine.count { TaskRepository.isDueToday(it) },
                R.string.stat_overdue to mine.count { TaskRepository.isOverdue(it) },
                R.string.stat_done to mine.count { it.status == TaskStatus.DONE },
            ),
        )
    }

    private fun setUpToolbarAndDrawer() {
        setSupportActionBar(binding.toolbar)
        supportActionBar?.setDisplayShowTitleEnabled(false)

        // DrawerLayout сам рисует фон под статус-баром цветом colorPrimaryDark из темы
        binding.drawerLayout.setStatusBarBackgroundColor(getColor(R.color.beige))

        header = NavHeaderBinding.bind(binding.navView.getHeaderView(0))

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
            when {
                item.groupId == GROUP_PROJECTS -> openProject((item.itemId - PROJECT_ITEM_BASE).toLong())
                item.itemId == R.id.nav_projects -> startActivity(Intent(this, ProjectsActivity::class.java))
                item.itemId == R.id.nav_calendar -> startActivity(Intent(this, CalendarActivity::class.java))
                item.itemId == R.id.nav_team_overview -> startActivity(Intent(this, TeamOverviewActivity::class.java))
                item.itemId == R.id.nav_assistant -> openAssistant()
                item.itemId == R.id.nav_profile -> startActivity(Intent(this, ProfileActivity::class.java))
                item.itemId == R.id.nav_help -> showHelp()
            }
            binding.drawerLayout.closeDrawers()
            true
        }
    }

    private fun refreshHeader() {
        val user = UserStore(this)
        val name = user.fullName
        header.tvHeaderName.text = name ?: getString(R.string.profile_name_missing)
        header.tvHeaderEmail.text = user.email ?: getString(R.string.profile_email_missing)
        header.tvHeaderAvatar.text = if (name.isNullOrBlank()) "?" else initials(name)
    }

    private fun refreshDrawerProjects() {
        val subMenu = binding.navView.menu.findItem(R.id.nav_projects_group)?.subMenu ?: return
        subMenu.clear()
        for (project in ProjectRepository.all()) {
            subMenu.add(GROUP_PROJECTS, PROJECT_ITEM_BASE + project.id.toInt(), Menu.NONE, project.name)
                .setIcon(R.drawable.ic_folder)
        }
    }

    private fun showHelp() {
        MaterialAlertDialogBuilder(this)
            .setTitle(R.string.help_title)
            .setMessage(R.string.help_message)
            .setPositiveButton(R.string.action_close, null)
            .show()
    }

    private fun setUpTabs() {
        binding.viewPager.adapter = TaskPagerAdapter(this, tabs.map { it.tab })

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

    private companion object {
        const val GROUP_PROJECTS = 7001
        const val PROJECT_ITEM_BASE = 10_000
    }
}
