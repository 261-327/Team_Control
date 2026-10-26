package com.example.sipisanzhapov

import android.os.Bundle
import android.view.GestureDetector
import android.view.MotionEvent
import android.view.View
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.widget.Toolbar
import androidx.recyclerview.widget.GridLayoutManager
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Locale
import kotlin.math.abs

// Одна ячейка календаря. date == null — пустое место до первого числа месяца
data class DayCell(val date: Calendar?, val taskCount: Int)

// Сравнение двух дат без учёта времени
fun isSameDay(a: Calendar, b: Calendar): Boolean =
    a.get(Calendar.YEAR) == b.get(Calendar.YEAR) &&
            a.get(Calendar.DAY_OF_YEAR) == b.get(Calendar.DAY_OF_YEAR)

// Календарь, обнулённый до начала дня
fun startOfDayCalendar(millis: Long = System.currentTimeMillis()): Calendar =
    Calendar.getInstance().apply {
        timeInMillis = millis
        set(Calendar.HOUR_OF_DAY, 0)
        set(Calendar.MINUTE, 0)
        set(Calendar.SECOND, 0)
        set(Calendar.MILLISECOND, 0)
    }

class CalendarActivity : AppCompatActivity() {

    // Первое число показанного месяца
    private var shownMonth: Calendar = startOfDayCalendar().apply { set(Calendar.DAY_OF_MONTH, 1) }
    private var selectedDate: Calendar = startOfDayCalendar()

    private lateinit var tvMonthTitle: TextView
    private lateinit var tvSelectedDate: TextView
    private lateinit var tvEmptyDay: TextView
    private lateinit var rvDayTasks: RecyclerView
    private lateinit var daysAdapter: CalendarDaysAdapter

    private val monthFormat = SimpleDateFormat("LLLL yyyy", Locale("ru"))
    private val selectedFormat = SimpleDateFormat("d MMMM, EEEE", Locale("ru"))

    // Минимальная длина свайпа и скорость, чтобы случайное движение не листало месяц
    private val minSwipeDistancePx by lazy { 80 * resources.displayMetrics.density }
    private val minSwipeVelocityPx = 800f

    // Распознаём горизонтальный свайп
    private val swipeDetector by lazy {
        GestureDetector(this, object : GestureDetector.SimpleOnGestureListener() {
            override fun onDown(e: MotionEvent): Boolean = true

            override fun onFling(
                e1: MotionEvent?,
                e2: MotionEvent,
                velocityX: Float,
                velocityY: Float
            ): Boolean {
                if (e1 == null) return false
                val dx = e2.x - e1.x

                // Игнорируем вертикальные и слишком короткие или медленные движения
                if (abs(dx) < minSwipeDistancePx) return false
                if (abs(dx) < abs(e2.y - e1.y)) return false
                if (abs(velocityX) < minSwipeVelocityPx) return false

                // Свайп влево — следующий месяц, вправо — предыдущий
                changeMonth(if (dx < 0) 1 else -1)
                return true
            }
        })
    }

    // Передаём касания детектору жестов, но не забираем их у RecyclerView,
    // поэтому нажатия на дни и прокрутка списка задач продолжают работать
    private val swipeListener = object : RecyclerView.SimpleOnItemTouchListener() {
        override fun onInterceptTouchEvent(rv: RecyclerView, e: MotionEvent): Boolean {
            swipeDetector.onTouchEvent(e)
            return false
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_calendar)

        // Стрелка назад в верхней панели
        val toolbar = findViewById<Toolbar>(R.id.toolbarCalendar)
        setSupportActionBar(toolbar)
        supportActionBar?.setDisplayHomeAsUpEnabled(true)

        tvMonthTitle = findViewById(R.id.tvMonthTitle)
        tvSelectedDate = findViewById(R.id.tvSelectedDate)
        tvEmptyDay = findViewById(R.id.tvEmptyDay)
        rvDayTasks = findViewById(R.id.rvDayTasks)
        rvDayTasks.layoutManager = LinearLayoutManager(this)

        // Сетка дней: 7 колонок (дни недели)
        daysAdapter = CalendarDaysAdapter { date -> selectDate(date) }
        val rvDays = findViewById<RecyclerView>(R.id.rvDays)
        rvDays.layoutManager = GridLayoutManager(this, 7)
        rvDays.adapter = daysAdapter

        // Свайп работает и по сетке дней, и по списку задач под ней
        rvDays.addOnItemTouchListener(swipeListener)
        rvDayTasks.addOnItemTouchListener(swipeListener)

        findViewById<View>(R.id.btnPrevMonth).setOnClickListener { changeMonth(-1) }
        findViewById<View>(R.id.btnNextMonth).setOnClickListener { changeMonth(1) }

        // При открытии выбран сегодняшний день
        selectDate(startOfDayCalendar())
    }

    override fun onSupportNavigateUp(): Boolean {
        finish()
        return true
    }

    // Переключаем месяц на delta (+1 — следующий, -1 — предыдущий)
    private fun changeMonth(delta: Int) {
        shownMonth.add(Calendar.MONTH, delta)
        refreshMonth()
    }

    private fun selectDate(date: Calendar) {
        selectedDate = date
        // Показываем месяц выбранного дня
        shownMonth = (date.clone() as Calendar).apply { set(Calendar.DAY_OF_MONTH, 1) }
        refreshMonth()
        TaskRepository.refreshUrgency()
        updateDayTasks()
    }

    // Перерисовываем заголовок месяца и сетку дней
    private fun refreshMonth() {
        tvMonthTitle.text = monthFormat.format(shownMonth.time).replaceFirstChar { it.uppercase() }
        daysAdapter.submit(buildMonthCells(), selectedDate)
    }

    // Обновляем список задач под календарём
    private fun updateDayTasks() {
        tvSelectedDate.text = selectedFormat.format(selectedDate.time).replaceFirstChar { it.uppercase() }
        val tasks = tasksOn(selectedDate)
        rvDayTasks.adapter = TaskAdapter(tasks)
        tvEmptyDay.visibility = if (tasks.isEmpty()) View.VISIBLE else View.GONE
        rvDayTasks.visibility = if (tasks.isEmpty()) View.GONE else View.VISIBLE
    }

    // Все задачи, у которых дедлайн приходится на эту дату
    private fun tasksOn(date: Calendar): List<Task> =
        TaskRepository.allTasks.filter { task ->
            isSameDay(startOfDayCalendar(task.deadlineTimestamp), date)
        }

    // Ячейки месяца. Неделя начинается с понедельника
    private fun buildMonthCells(): List<DayCell> {
        val cells = mutableListOf<DayCell>()

        // Calendar: воскресенье = 1, понедельник = 2 ... суббота = 7
        val emptyBefore = (shownMonth.get(Calendar.DAY_OF_WEEK) + 5) % 7
        repeat(emptyBefore) { cells.add(DayCell(null, 0)) }

        val daysInMonth = shownMonth.getActualMaximum(Calendar.DAY_OF_MONTH)
        for (day in 1..daysInMonth) {
            val date = (shownMonth.clone() as Calendar).apply { set(Calendar.DAY_OF_MONTH, day) }
            cells.add(DayCell(date, tasksOn(date).size))
        }
        return cells
    }
}