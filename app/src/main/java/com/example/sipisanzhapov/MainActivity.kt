package com.example.sipisanzhapov

import android.content.Intent
import android.os.Bundle
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.ActionBarDrawerToggle
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.widget.Toolbar
import androidx.core.view.WindowInsetsControllerCompat
import androidx.drawerlayout.widget.DrawerLayout
import androidx.viewpager2.widget.ViewPager2
import com.google.android.material.bottomnavigation.BottomNavigationView
import com.google.android.material.navigation.NavigationView

class MainActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContentView(R.layout.activity_main)

        // Фон окна (виден за статус-баром): бежевый вместо фиолетового
        window.setBackgroundDrawableResource(R.color.beige)
        // Тёмные иконки статус-бара (время, сеть, батарея), так как фон светлый
        WindowInsetsControllerCompat(window, window.decorView).isAppearanceLightStatusBars = true

        // Инициализируем элементы из разметки activity_main.xml
        val viewPager = findViewById<ViewPager2>(R.id.viewPager)
        val bottomNavigationView = findViewById<BottomNavigationView>(R.id.bottomNavigationView)
        val drawerLayout = findViewById<DrawerLayout>(R.id.drawerLayout)
        val toolbar = findViewById<Toolbar>(R.id.toolbar)
        val navView = findViewById<NavigationView>(R.id.navView)

        // 1. Верхняя панель: сначала подключаем тулбар, потом скрываем заголовок
        setSupportActionBar(toolbar)
        supportActionBar?.setDisplayShowTitleEnabled(false)

        // 2. Боковое меню (выезжает по кнопке с тремя полосками)
        val toggle = ActionBarDrawerToggle(
            this,
            drawerLayout,
            toolbar,
            R.string.navigation_drawer_open,
            R.string.navigation_drawer_close
        )
        drawerLayout.addDrawerListener(toggle)
        toggle.syncState()

        navView.setNavigationItemSelectedListener { menuItem ->
            when (menuItem.itemId) {
                R.id.nav_profile -> {
                    startActivity(Intent(this, ProfileActivity::class.java))
                }
                R.id.nav_calendar -> {
                    startActivity(Intent(this, CalendarActivity::class.java))
                }
            }
            drawerLayout.closeDrawers()
            true
        }

        // 3. Устанавливаем адаптер для ViewPager2
        viewPager.adapter = ViewPagerAdapter(this)

        // 4. Синхронизируем смену страниц с подсветкой иконок внизу
        viewPager.registerOnPageChangeCallback(object : ViewPager2.OnPageChangeCallback() {
            override fun onPageSelected(position: Int) {
                super.onPageSelected(position)
                bottomNavigationView.menu.getItem(position).isChecked = true
            }
        })

        // 5. Обрабатываем нажатия на иконки нижнего меню
        bottomNavigationView.setOnItemSelectedListener { item ->
            when (item.itemId) {
                R.id.nav_urgent -> {
                    viewPager.currentItem = 0
                    true
                }
                R.id.nav_in_progress -> {
                    viewPager.currentItem = 1
                    true
                }
                R.id.nav_review -> {
                    viewPager.currentItem = 2
                    true
                }
                R.id.nav_backlog -> {
                    viewPager.currentItem = 3
                    true
                }
                else -> false
            }
        }
    }
}