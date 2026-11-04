package com.example.sipi_ai.ui.common

import android.view.LayoutInflater
import android.widget.LinearLayout
import com.example.sipi_ai.databinding.ViewStatCardBinding

/** Заполняет строку карточками статистики: пары (строка-подпись, значение). */
fun LinearLayout.showStats(stats: List<Pair<Int, Int>>) {
    removeAllViews()
    val inflater = LayoutInflater.from(context)
    for ((labelRes, value) in stats) {
        val card = ViewStatCardBinding.inflate(inflater, this, false)
        card.tvStatLabel.setText(labelRes)
        card.tvStatValue.text = value.toString()
        addView(card.root)
    }
}
