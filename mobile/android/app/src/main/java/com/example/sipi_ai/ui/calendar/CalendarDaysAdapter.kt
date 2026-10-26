package com.example.sipi_ai.ui.calendar

import android.graphics.Typeface
import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.core.content.ContextCompat
import androidx.core.view.isInvisible
import androidx.recyclerview.widget.RecyclerView
import com.example.sipi_ai.R
import com.example.sipi_ai.databinding.ItemCalendarDayBinding
import com.example.sipi_ai.util.isSameDay
import com.example.sipi_ai.util.startOfDay
import java.util.Calendar

class CalendarDaysAdapter(
    private val onDayClick: (Calendar) -> Unit,
) : RecyclerView.Adapter<CalendarDaysAdapter.DayViewHolder>() {

    private var cells: List<DayCell> = emptyList()
    private var selectedDay: Calendar? = null

    fun submit(cells: List<DayCell>, selectedDay: Calendar) {
        this.cells = cells
        this.selectedDay = selectedDay
        notifyDataSetChanged()
    }

    override fun getItemCount(): Int = cells.size

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): DayViewHolder =
        DayViewHolder(ItemCalendarDayBinding.inflate(LayoutInflater.from(parent.context), parent, false))

    override fun onBindViewHolder(holder: DayViewHolder, position: Int) {
        holder.bind(cells[position])
    }

    inner class DayViewHolder(
        private val binding: ItemCalendarDayBinding,
    ) : RecyclerView.ViewHolder(binding.root) {

        fun bind(cell: DayCell) {
            val day = cell.day
            if (day == null) {
                binding.tvDay.isInvisible = true
                binding.tvDot.isInvisible = true
                binding.root.setOnClickListener(null)
                binding.root.isClickable = false
                return
            }

            val isSelected = selectedDay?.isSameDay(day) == true
            val isToday = day.isSameDay(startOfDay())
            val background = when {
                isSelected -> R.drawable.bg_calendar_day_selected
                isToday -> R.drawable.bg_calendar_day_today
                else -> 0
            }
            val textColor = when {
                isSelected -> R.color.white
                isToday -> R.color.mustard_dark
                else -> R.color.text_primary
            }

            binding.tvDay.isInvisible = false
            binding.tvDay.text = day.get(Calendar.DAY_OF_MONTH).toString()
            binding.tvDay.setBackgroundResource(background)
            binding.tvDay.setTextColor(ContextCompat.getColor(binding.root.context, textColor))
            binding.tvDay.setTypeface(null, if (isSelected || isToday) Typeface.BOLD else Typeface.NORMAL)
            binding.tvDot.isInvisible = !cell.hasTasks

            binding.root.setOnClickListener { onDayClick(day) }
        }
    }
}
