package com.example.sipi_ai.ui.assistant

import android.graphics.Bitmap
import android.view.Gravity
import android.view.LayoutInflater
import android.view.ViewGroup
import android.widget.LinearLayout
import androidx.core.view.isVisible
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.example.sipi_ai.R
import com.example.sipi_ai.databinding.ItemMessageBinding

enum class AssistantMode(val apiValue: String) { CHAT("chat"), TASKS("tasks"), LOGO("logo") }

data class AssistantTaskDraft(
    val title: String,
    val description: String,
    val tag: String,
    val assigneeId: String = "",
    val deadlineAt: String = "",
)

data class ChatMessage(
    val id: Long,
    val fromUser: Boolean,
    val text: String,
    val turnId: String? = null,
    val drafts: List<AssistantTaskDraft> = emptyList(),
    val draftsAdded: Boolean = false,
    val image: Bitmap? = null,
    val imageLoading: Boolean = false,
    val pending: Boolean = false,
)

class MessageAdapter(
    private val onAddDrafts: (ChatMessage) -> Unit,
) : ListAdapter<ChatMessage, MessageAdapter.ViewHolder>(Diff) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder =
        ViewHolder(ItemMessageBinding.inflate(LayoutInflater.from(parent.context), parent, false))

    override fun onBindViewHolder(holder: ViewHolder, position: Int) = holder.bind(getItem(position))

    inner class ViewHolder(private val binding: ItemMessageBinding) : RecyclerView.ViewHolder(binding.root) {

        fun bind(message: ChatMessage) {
            val context = binding.root.context
            val gravity = if (message.fromUser) Gravity.END else Gravity.START

            binding.tvMessageText.text = message.text
            binding.ivGeneratedImage.isVisible = message.image != null
            binding.ivGeneratedImage.setImageBitmap(message.image)
            binding.tvMessageText.setBackgroundResource(
                if (message.fromUser) R.drawable.bg_message_user else R.drawable.bg_message_assistant,
            )
            binding.tvMessageText.setTextColor(
                context.getColor(if (message.fromUser) R.color.white else R.color.text_primary),
            )
            binding.tvMessageText.layoutParams =
                (binding.tvMessageText.layoutParams as LinearLayout.LayoutParams).also { it.gravity = gravity }

            val hasDrafts = !message.fromUser && message.drafts.isNotEmpty()
            binding.btnAddDrafts.isVisible = hasDrafts
            binding.btnAddDrafts.isEnabled = hasDrafts && !message.draftsAdded
            if (hasDrafts) {
                binding.btnAddDrafts.text = if (message.draftsAdded) {
                    context.getString(R.string.assistant_drafts_added)
                } else {
                    context.getString(R.string.assistant_add_drafts, message.drafts.size)
                }
                binding.btnAddDrafts.setOnClickListener { onAddDrafts(message) }
            }
            binding.pbImageLoading.isVisible = message.imageLoading
        }
    }

    private object Diff : DiffUtil.ItemCallback<ChatMessage>() {
        override fun areItemsTheSame(oldItem: ChatMessage, newItem: ChatMessage) = oldItem.id == newItem.id
        override fun areContentsTheSame(oldItem: ChatMessage, newItem: ChatMessage) = oldItem == newItem
    }
}
