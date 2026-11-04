package com.example.sipi_ai.ui.taskdetail

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.example.sipi_ai.data.Comment
import com.example.sipi_ai.data.HistoryEntry
import com.example.sipi_ai.databinding.ItemCommentBinding
import com.example.sipi_ai.databinding.ItemHistoryBinding
import com.example.sipi_ai.ui.common.MemberNames
import com.example.sipi_ai.util.formatDateTimeShort

class CommentAdapter : ListAdapter<Comment, CommentAdapter.ViewHolder>(Diff) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder =
        ViewHolder(ItemCommentBinding.inflate(LayoutInflater.from(parent.context), parent, false))

    override fun onBindViewHolder(holder: ViewHolder, position: Int) = holder.bind(getItem(position))

    class ViewHolder(private val binding: ItemCommentBinding) : RecyclerView.ViewHolder(binding.root) {
        fun bind(comment: Comment) {
            val names = MemberNames(binding.root.context)
            binding.tvCommentAvatar.text = names.initialsOf(comment.authorId)
            binding.tvCommentAuthor.text =
                "${names.of(comment.authorId)} · ${formatDateTimeShort(comment.createdMillis)}"
            binding.tvCommentText.text = comment.text
        }
    }

    private object Diff : DiffUtil.ItemCallback<Comment>() {
        override fun areItemsTheSame(oldItem: Comment, newItem: Comment) = oldItem == newItem
        override fun areContentsTheSame(oldItem: Comment, newItem: Comment) = oldItem == newItem
    }
}

class HistoryAdapter : ListAdapter<HistoryEntry, HistoryAdapter.ViewHolder>(Diff) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder =
        ViewHolder(ItemHistoryBinding.inflate(LayoutInflater.from(parent.context), parent, false))

    override fun onBindViewHolder(holder: ViewHolder, position: Int) = holder.bind(getItem(position))

    class ViewHolder(private val binding: ItemHistoryBinding) : RecyclerView.ViewHolder(binding.root) {
        fun bind(entry: HistoryEntry) {
            binding.tvHistoryText.text = entry.text
            binding.tvHistoryTime.text = formatDateTimeShort(entry.createdMillis)
        }
    }

    private object Diff : DiffUtil.ItemCallback<HistoryEntry>() {
        override fun areItemsTheSame(oldItem: HistoryEntry, newItem: HistoryEntry) = oldItem == newItem
        override fun areContentsTheSame(oldItem: HistoryEntry, newItem: HistoryEntry) = oldItem == newItem
    }
}
