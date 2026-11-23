package com.example.sipi_ai.ui.common

import android.view.LayoutInflater
import android.widget.LinearLayout
import com.example.sipi_ai.databinding.ViewStatCardBinding

/** Заполняет строку карточками статистики: пары (строка-подпись, значение). */
fun LinearLayout.showStats(stats: List<Pair<Int, Int>>, onClick: ((Int) -> Unit)? = null) {
    removeAllViews()
    val inflater = LayoutInflater.from(context)
    for ((index, stat) in stats.withIndex()) {
        val (labelRes, value) = stat
        val card = ViewStatCardBinding.inflate(inflater, this, false)
        card.tvStatLabel.setText(labelRes)
        card.tvStatValue.text = value.toString()
        if (onClick != null) {
            card.root.isClickable = true
            card.root.isFocusable = true
            card.root.setOnClickListener { onClick(index) }
        }
        addView(card.root)
    }
}
