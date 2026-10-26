package com.example.sipisanzhapov

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.fragment.app.Fragment
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.snackbar.Snackbar

class TaskFragment : Fragment() {

    private var recyclerView: RecyclerView? = null
    private var tvEmptyTasks: TextView? = null

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View? {
        return inflater.inflate(R.layout.fragment_task, container, false)
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        recyclerView = view.findViewById(R.id.recyclerViewTasks)
        tvEmptyTasks = view.findViewById(R.id.tvEmptyTasks)
        recyclerView?.layoutManager = LinearLayoutManager(requireContext())
        loadTasks()
    }

    override fun onResume() {
        super.onResume()
        // Перечитываем список, чтобы изменения были видны сразу после возврата на вкладку
        loadTasks()
    }

    override fun onDestroyView() {
        recyclerView = null
        tvEmptyTasks = null
        super.onDestroyView()
    }

    private fun loadTasks() {
        // Сначала обновляем статусы по дедлайнам, потом фильтруем вкладку
        TaskRepository.refreshUrgency()

        val tabPosition = arguments?.getInt("TAB_POSITION") ?: 0
        val tasksForThisTab = TaskRepository.allTasks.filter { it.status == tabPosition }

        recyclerView?.adapter = TaskAdapter(tasksForThisTab) { task ->
            submitForReview(task)
        }

        // Если задач нет, показываем надпись и скрываем пустой список
        val isEmpty = tasksForThisTab.isEmpty()
        tvEmptyTasks?.visibility = if (isEmpty) View.VISIBLE else View.GONE
        recyclerView?.visibility = if (isEmpty) View.GONE else View.VISIBLE
    }

    private fun submitForReview(task: Task) {
        // Запоминаем прежний статус, чтобы «Отменить» мог его вернуть
        val previousStatus = task.status
        task.status = STATUS_REVIEW
        loadTasks()

        val bottomNav = requireActivity().findViewById<View>(R.id.bottomNavigationView)

        Snackbar.make(requireView(), "Задача отправлена на проверку", Snackbar.LENGTH_LONG)
            .setAnchorView(bottomNav)
            .setAction("Отменить") {
                task.status = previousStatus
                loadTasks()
            }
            .show()
    }
}