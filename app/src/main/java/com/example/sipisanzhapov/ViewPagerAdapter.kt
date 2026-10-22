package com.example.sipisanzhapov

import android.os.Bundle
import androidx.fragment.app.Fragment
import androidx.fragment.app.FragmentActivity
import androidx.viewpager2.adapter.FragmentStateAdapter

class ViewPagerAdapter(fragmentActivity: FragmentActivity) : FragmentStateAdapter(fragmentActivity) {
    override fun getItemCount(): Int = 4

    override fun createFragment(position: Int): Fragment {
        val fragment = TaskFragment()

        // Упаковываем позицию вкладки в аргументы
        val args = Bundle().apply {
            putInt("TAB_POSITION", position)
        }
        fragment.arguments = args

        return fragment
    }
}