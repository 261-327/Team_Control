package com.example.sipisanzhapov

import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.RecyclerView
import java.util.Calendar

class CalendarDaysAdapter(private val onDayClick: (Calendar) -> Unit) :
    RecyclerView.Adapter<CalendarDaysAdapter.DayViewHolder>() {

    private val cells = mutableListOf<DayCell>()
    private var selected: Calendar? = null

    class DayViewHolder(itemView: View) : RecyclerView.ViewHolder(itemView) {
        val tvDay: TextView = itemView.findViewById(R.id.tvDay)
        val tvDot: TextView = itemView.findViewById(R.id.tvDot)
    }

    // Обновляем список ячеек и выбранную дату
    fun submit(newCells: List<DayCell>, selectedDate: Calendar) {
        cells.clear()
        cells.addAll(newCells)
        selected = selectedDate
        notifyDataSetChanged()
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): DayViewHolder {
        val view = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_calendar_day, parent, false)
        return DayViewHolder(view)
    }

    override fun getItemCount(): Int = cells.size

    override fun onBindViewHolder(holder: DayViewHolder, position: Int) {
        val cell = cells[position]
        val context = holder.itemView.context
        val date = cell.date

        // Пустая ячейка до первого числа месяца
        if (date == null) {
            holder.tvDay.visibility = View.INVISIBLE
            holder.tvDot.visibility = View.GONE
            holder.itemView.setOnClickListener(null)
            holder.itemView.isClickable = false
            return
        }

        holder.tvDay.visibility = View.VISIBLE
        holder.tvDay.text = date.get(Calendar.DAY_OF_MONTH).toString()
        holder.itemView.isClickable = true
        holder.itemView.setOnClickListener { onDayClick(date) }

        val isSelected = selected?.let { isSameDay(it, date) } == true
        val isToday = isSameDay(startOfDayCalendar(), date)

        // Выбранный день: фирменный круг с белым текстом
        if (isSelected) {
            holder.tvDay.background = GradientDrawable().apply {
                shape = GradientDrawable.OVAL
                setColor(ContextCompat.getColor(context, R.color.sipe_yellow_dark))
            }
            holder.tvDay.setTextColor(ContextCompat.getColor(context, R.color.white))
            holder.tvDot.setTextColor(ContextCompat.getColor(context, R.color.white))
        } else {
            holder.tvDay.background = null
            holder.tvDay.setTextColor(ContextCompat.getColor(context, R.color.black))
            holder.tvDot.setTextColor(ContextCompat.getColor(context, R.color.sipe_yellow_dark))
        }

        // Сегодняшний день выделяем жирным
        holder.tvDay.setTypeface(null, if (isToday) Typeface.BOLD else Typeface.NORMAL)

        // Точка — если на этот день есть задачи
        holder.tvDot.visibility = if (cell.taskCount > 0) View.VISIBLE else View.GONE
    }
}