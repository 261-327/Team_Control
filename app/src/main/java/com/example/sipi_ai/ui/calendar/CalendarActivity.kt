package com.example.sipi_ai.ui.calendar

import android.content.Intent
import android.os.Bundle
import android.view.GestureDetector
import android.view.Menu
import android.view.MenuItem
import android.view.MotionEvent
import android.view.View
import android.widget.AdapterView
import android.widget.ArrayAdapter
import android.widget.Toast
import androidx.core.content.FileProvider
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.isVisible
import androidx.recyclerview.widget.GridLayoutManager
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.example.sipi_ai.R
import com.example.sipi_ai.data.Project
import com.example.sipi_ai.data.ProjectRepository
import com.example.sipi_ai.data.Task
import com.example.sipi_ai.data.TaskRepository
import com.example.sipi_ai.databinding.ActivityCalendarBinding
import com.example.sipi_ai.ui.common.openTask
import com.example.sipi_ai.ui.tasks.TaskAdapter
import com.example.sipi_ai.util.buildIcs
import com.example.sipi_ai.util.copy
import com.example.sipi_ai.util.isSameDay
import com.example.sipi_ai.util.startOfDay
import java.io.File
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Locale
import kotlin.math.abs

private val RUSSIAN: Locale = Locale.forLanguageTag("ru")

class CalendarActivity : AppCompatActivity() {

    private lateinit var binding: ActivityCalendarBinding
    private val daysAdapter = CalendarDaysAdapter { day -> select(day) }
    private val dayTasksAdapter = TaskAdapter(onClick = { task -> openTask(task.id) })
    private var projects: List<Project> = emptyList()
    private var filterProjectId: Long? = null

    private var selectedDay: Calendar = startOfDay()
    private var shownMonth: Calendar = selectedDay.copy { set(Calendar.DAY_OF_MONTH, 1) }

    private val monthFormat = SimpleDateFormat("LLLL yyyy", RUSSIAN)
    private val selectedDayFormat = SimpleDateFormat("d MMMM, EEEE", RUSSIAN)

    private val minSwipeDistancePx by lazy { MIN_SWIPE_DISTANCE_DP * resources.displayMetrics.density }

    private val swipeDetector by lazy {
        GestureDetector(this, object : GestureDetector.SimpleOnGestureListener() {
            override fun onDown(e: MotionEvent): Boolean = true

            override fun onFling(
                e1: MotionEvent?,
                e2: MotionEvent,
                velocityX: Float,
                velocityY: Float,
            ): Boolean {
                if (e1 == null) return false
                val dx = e2.x - e1.x
                val isHorizontalSwipe = abs(dx) >= minSwipeDistancePx &&
                    abs(dx) >= abs(e2.y - e1.y) &&
                    abs(velocityX) >= MIN_SWIPE_VELOCITY_PX
                if (!isHorizontalSwipe) return false

                shiftMonth(if (dx < 0) 1 else -1)
                return true
            }
        })
    }

    // Касания только подсматриваем и не перехватываем, иначе перестанут работать
    // нажатия на дни и прокрутка списка задач
    private val swipeListener = object : RecyclerView.SimpleOnItemTouchListener() {
        override fun onInterceptTouchEvent(rv: RecyclerView, e: MotionEvent): Boolean {
            swipeDetector.onTouchEvent(e)
            return false
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityCalendarBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setSupportActionBar(binding.toolbarCalendar)
        supportActionBar?.setDisplayHomeAsUpEnabled(true)

        binding.rvDays.layoutManager = GridLayoutManager(this, DAYS_IN_WEEK)
        binding.rvDays.adapter = daysAdapter
        binding.rvDayTasks.layoutManager = LinearLayoutManager(this)
        binding.rvDayTasks.adapter = dayTasksAdapter

        binding.rvDays.addOnItemTouchListener(swipeListener)
        binding.rvDayTasks.addOnItemTouchListener(swipeListener)

        binding.btnPrevMonth.setOnClickListener { shiftMonth(-1) }
        binding.btnNextMonth.setOnClickListener { shiftMonth(1) }
        binding.btnToday.setOnClickListener { select(startOfDay()) }

        setUpProjectFilter()
        render()
    }

    override fun onResume() {
        super.onResume()
        render()
    }

    override fun onCreateOptionsMenu(menu: Menu): Boolean {
        menuInflater.inflate(R.menu.menu_calendar, menu)
        return true
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean = when (item.itemId) {
        R.id.action_export -> {
            exportNextWeek()
            true
        }
        else -> super.onOptionsItemSelected(item)
    }

    private fun setUpProjectFilter() {
        projects = ProjectRepository.all()
        val labels = listOf(getString(R.string.calendar_all_projects)) + projects.map { it.name }
        binding.spinnerCalendarProject.adapter =
            ArrayAdapter(this, android.R.layout.simple_spinner_item, labels).also {
                it.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item)
            }
        binding.spinnerCalendarProject.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                filterProjectId = if (position == 0) null else projects.getOrNull(position - 1)?.id
                render()
            }

            override fun onNothingSelected(parent: AdapterView<*>?) = Unit
        }
    }

    /** Личные дедлайны (задачи, где исполнитель — текущий пользователь), с учётом фильтра проекта. */
    private fun personalTasks(): List<Task> =
        TaskRepository.mine().filter { filterProjectId == null || it.projectId == filterProjectId }

    private fun exportNextWeek() {
        val now = System.currentTimeMillis()
        val weekEnd = startOfDay().copy { add(Calendar.DAY_OF_YEAR, 7) }.timeInMillis
        val upcoming = personalTasks().filter {
            val deadline = it.deadlineMillis
            deadline != null && deadline in startOfDay().timeInMillis..weekEnd
        }
        if (upcoming.isEmpty()) {
            Toast.makeText(this, R.string.calendar_export_empty, Toast.LENGTH_SHORT).show()
            return
        }
        try {
            val dir = File(cacheDir, "exports").apply { mkdirs() }
            val file = File(dir, "sipi_deadlines.ics")
            file.writeText(buildIcs(upcoming, now))
            val uri = FileProvider.getUriForFile(this, "$packageName.fileprovider", file)
            val send = Intent(Intent.ACTION_SEND)
                .setType("text/calendar")
                .putExtra(Intent.EXTRA_STREAM, uri)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            startActivity(Intent.createChooser(send, getString(R.string.calendar_export_share)))
        } catch (e: Exception) {
            Toast.makeText(this, R.string.calendar_export_error, Toast.LENGTH_SHORT).show()
        }
    }

    override fun onSupportNavigateUp(): Boolean {
        finish()
        return true
    }

    private fun shiftMonth(delta: Int) {
        shownMonth = shownMonth.copy { add(Calendar.MONTH, delta) }
        render()
    }

    private fun select(day: Calendar) {
        selectedDay = day
        shownMonth = day.copy { set(Calendar.DAY_OF_MONTH, 1) }
        render()
    }

    private fun render() {
        val tasks = personalTasks()

        binding.tvMonthTitle.text = monthFormat.format(shownMonth.time).replaceFirstChar { it.uppercase() }
        daysAdapter.submit(monthCells(shownMonth) { day -> tasks.any { it.isDueOn(day) } }, selectedDay)

        val dayTasks = tasks.filter { it.isDueOn(selectedDay) }
        binding.tvSelectedDate.text = selectedDayFormat.format(selectedDay.time).replaceFirstChar { it.uppercase() }
        dayTasksAdapter.submitList(dayTasks)
        binding.tvEmptyDay.isVisible = dayTasks.isEmpty()
        binding.rvDayTasks.isVisible = dayTasks.isNotEmpty()
    }

    private companion object {
        const val DAYS_IN_WEEK = 7
        const val MIN_SWIPE_DISTANCE_DP = 80
        const val MIN_SWIPE_VELOCITY_PX = 800f
    }
}

private fun Task.isDueOn(day: Calendar): Boolean {
    val deadline = deadlineMillis ?: return false
    return startOfDay(deadline).isSameDay(day)
}
