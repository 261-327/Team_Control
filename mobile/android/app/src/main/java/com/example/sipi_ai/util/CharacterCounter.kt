package com.example.sipi_ai.util

import android.text.Editable
import android.text.TextWatcher
import android.widget.EditText
import android.widget.TextView
import com.example.sipi_ai.R

fun EditText.bindCharacterCounter(counter: TextView, limit: Int) {
    fun updateCount(length: Int) {
        counter.text = context.getString(R.string.character_count, length, limit)
    }

    updateCount(text?.length ?: 0)
    addTextChangedListener(object : TextWatcher {
        override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) = Unit
        override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) = Unit
        override fun afterTextChanged(s: Editable?) = updateCount(s?.length ?: 0)
    })
}
