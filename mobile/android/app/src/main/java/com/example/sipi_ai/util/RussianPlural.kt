package com.example.sipi_ai.util

import kotlin.math.abs

fun <T> russianPlural(count: Int, one: T, few: T, many: T): T {
    val n = abs(count)
    return when {
        n % 100 in 11..14 -> many
        n % 10 == 1 -> one
        n % 10 in 2..4 -> few
        else -> many
    }
}
