package com.example.sipi_ai.ui.projects

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.example.sipi_ai.databinding.ItemMemberBinding

/** Простая строка «аватар + заголовок + подпись»: участники команды и материалы. */
data class Row(
    val key: String,
    val badge: String,
    val title: String,
    val subtitle: String,
    val payload: Long? = null,
    val clickable: Boolean = true,
)

class RowAdapter(
    private val onClick: (Row) -> Unit,
) : ListAdapter<Row, RowAdapter.ViewHolder>(Diff) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder =
        ViewHolder(ItemMemberBinding.inflate(LayoutInflater.from(parent.context), parent, false))

    override fun onBindViewHolder(holder: ViewHolder, position: Int) = holder.bind(getItem(position))

    inner class ViewHolder(private val binding: ItemMemberBinding) : RecyclerView.ViewHolder(binding.root) {
        fun bind(row: Row) {
            binding.tvMemberAvatar.text = row.badge
            binding.tvMemberName.text = row.title
            binding.tvMemberRole.text = row.subtitle
            binding.root.isClickable = row.clickable
            binding.root.setOnClickListener { if (row.clickable) onClick(row) }
        }
    }

    private object Diff : DiffUtil.ItemCallback<Row>() {
        override fun areItemsTheSame(oldItem: Row, newItem: Row) = oldItem.key == newItem.key
        override fun areContentsTheSame(oldItem: Row, newItem: Row) = oldItem == newItem
    }
}
