package com.example.sipi_ai.ui.common

import android.content.Context
import com.example.sipi_ai.R
import com.example.sipi_ai.data.Task
import com.google.android.material.dialog.MaterialAlertDialogBuilder

fun Context.confirmTaskSubmitForReview(task: Task, onConfirm: () -> Unit) {
    MaterialAlertDialogBuilder(this)
        .setTitle(R.string.task_submit_confirm_title)
        .setMessage(getString(R.string.task_submit_confirm_message, task.title))
        .setNegativeButton(R.string.action_cancel, null)
        .setPositiveButton(R.string.task_submit_confirm_action) { _, _ -> onConfirm() }
        .show()
}
