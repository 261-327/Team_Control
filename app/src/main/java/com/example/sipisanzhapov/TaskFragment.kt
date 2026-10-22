package com.example.sipisanzhapov

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.Fragment
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.example.sipisanzhapov.TaskRepository.allTasks

class TaskFragment : Fragment() {

    override fun onCreateView(
        inflater: LayoutInflater, container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View? {
        // «Надуваем» разметку фрагмента, которую только что создали
        return inflater.inflate(R.layout.fragment_task, container, false)
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        val recyclerView = view.findViewById<RecyclerView>(R.id.recyclerViewTasks)
        recyclerView.layoutManager = LinearLayoutManager(requireContext())

        // 1. Получаем номер текущей вкладки (от 0 до 3).
        // Если аргумент не передан, по умолчанию будет 0.
        val tabPosition = arguments?.getInt("TAB_POSITION") ?: 0

        // 2. Фильтруем общий список из репозитория по статусу
        val tasksForThisTab = TaskRepository.allTasks.filter { it.status == tabPosition }

        // 3. Передаем отфильтрованный список в адаптер
        val adapter = TaskAdapter(tasksForThisTab)
        recyclerView.adapter = adapter
    }
        // Тестовые данные, чтобы проверить работу адаптера


        // Подключаем наш созданный ранее TaskAdapter

    }
