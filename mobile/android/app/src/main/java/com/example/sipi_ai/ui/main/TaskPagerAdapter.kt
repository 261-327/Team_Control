package com.example.sipi_ai.ui.main

import androidx.fragment.app.Fragment
import androidx.fragment.app.FragmentActivity
import androidx.viewpager2.adapter.FragmentStateAdapter
import com.example.sipi_ai.data.TaskStatus
import com.example.sipi_ai.ui.tasks.TaskFragment

class TaskPagerAdapter(
    activity: FragmentActivity,
    private val statuses: List<TaskStatus>,
) : FragmentStateAdapter(activity) {

    override fun getItemCount(): Int = statuses.size

    override fun createFragment(position: Int): Fragment = TaskFragment.newInstance(statuses[position])
}
