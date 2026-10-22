package com.example.sipisanzhapov

import android.os.Bundle
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.viewpager2.widget.ViewPager2
import com.google.android.material.bottomnavigation.BottomNavigationView

class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContentView(R.layout.activity_main)

        // Инициализируем элементы из разметки activity_main.xml
        val viewPager = findViewById<ViewPager2>(R.id.viewPager)
        val bottomNavigationView = findViewById<BottomNavigationView>(R.id.bottomNavigationView)

        // 1. Устанавливаем адаптер для ViewPager2
        viewPager.adapter = ViewPagerAdapter(this)

        // 2. Синхронизируем смену страниц с подсветкой иконок внизу
        viewPager.registerOnPageChangeCallback(object : ViewPager2.OnPageChangeCallback() {
            override fun onPageSelected(position: Int) {
                super.onPageSelected(position)
                bottomNavigationView.menu.getItem(position).isChecked = true
            }
        })

        // 3. Обрабатываем нажатия на иконки нижнего меню
        bottomNavigationView.setOnItemSelectedListener { item ->
            when (item.itemId) {
                R.id.nav_urgent -> {
                    viewPager.currentItem = 0 // Первая вкладка
                    true
                }
                R.id.nav_in_progress -> {
                    viewPager.currentItem = 1 // Вторая вкладка
                    true
                }
                R.id.nav_review -> {
                    viewPager.currentItem = 2 // Третья вкладка
                    true
                }
                R.id.nav_backlog -> {
                    viewPager.currentItem = 3 // Четвертая вкладка
                    true
                }
                else -> false
            }
        }
    }
}