package com.example.sipi_ai.ui.search

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.annotation.DrawableRes
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.example.sipi_ai.databinding.ItemSearchResultBinding

data class ResultRow(
    val key: String,
    val title: String,
    val subtitle: String,
    @DrawableRes val iconRes: Int,
    val onClick: () -> Unit,
)

/** Список «иконка + заголовок + подпись»: результаты поиска и уведомления. */
class ResultAdapter : ListAdapter<ResultRow, ResultAdapter.ViewHolder>(Diff) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder =
        ViewHolder(ItemSearchResultBinding.inflate(LayoutInflater.from(parent.context), parent, false))

    override fun onBindViewHolder(holder: ViewHolder, position: Int) = holder.bind(getItem(position))

    class ViewHolder(private val binding: ItemSearchResultBinding) : RecyclerView.ViewHolder(binding.root) {
        fun bind(row: ResultRow) {
            binding.ivResultIcon.setImageResource(row.iconRes)
            binding.tvResultTitle.text = row.title
            binding.tvResultSubtitle.text = row.subtitle
            binding.root.setOnClickListener { row.onClick() }
        }
    }

    private object Diff : DiffUtil.ItemCallback<ResultRow>() {
        override fun areItemsTheSame(oldItem: ResultRow, newItem: ResultRow) = oldItem.key == newItem.key
        override fun areContentsTheSame(oldItem: ResultRow, newItem: ResultRow) =
            oldItem.key == newItem.key && oldItem.title == newItem.title && oldItem.subtitle == newItem.subtitle
    }
}
