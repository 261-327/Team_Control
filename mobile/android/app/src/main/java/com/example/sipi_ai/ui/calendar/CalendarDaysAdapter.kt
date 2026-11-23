package com.example.sipi_ai.ui.calendar

import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
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
                binding.root.setOnClickListener(null)
                binding.root.isClickable = false
                return
            }

            val isSelected = selectedDay?.isSameDay(day) == true
            val isToday = day.isSameDay(startOfDay())
            val context = binding.root.context
            val background = cell.marker?.let { marker ->
                GradientDrawable().apply {
                    shape = GradientDrawable.OVAL
                    setColor(ContextCompat.getColor(context, if (isSelected) R.color.mustard else marker.backgroundRes))
                    setStroke(
                        (1.5f * context.resources.displayMetrics.density).toInt().coerceAtLeast(1),
                        ContextCompat.getColor(context, marker.colorRes),
                    )
                }
            }
            val textColor = when {
                isSelected -> R.color.white
                cell.marker != null -> cell.marker.colorRes
                isToday -> R.color.mustard_dark
                else -> R.color.text_primary
            }

            binding.tvDay.isInvisible = false
            binding.tvDay.text = day.get(Calendar.DAY_OF_MONTH).toString()
            binding.tvDay.background = background ?: when {
                isSelected -> ContextCompat.getDrawable(context, R.drawable.bg_calendar_day_selected)
                isToday -> ContextCompat.getDrawable(context, R.drawable.bg_calendar_day_today)
                else -> null
            }
            binding.tvDay.setTextColor(ContextCompat.getColor(context, textColor))
            binding.tvDay.setTypeface(null, if (isSelected || isToday) Typeface.BOLD else Typeface.NORMAL)

            binding.root.setOnClickListener { onDayClick(day) }
        }
    }
}
