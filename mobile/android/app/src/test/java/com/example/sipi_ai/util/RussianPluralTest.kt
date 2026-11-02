package com.example.sipi_ai.util

import org.junit.Assert.assertEquals
import org.junit.Test

class RussianPluralTest {

    private fun days(count: Int): String = russianPlural(count, "день", "дня", "дней")

    @Test
    fun oneForm() {
        listOf(1, 21, 101, -1).forEach { assertEquals("день", days(it)) }
    }

    @Test
    fun fewForm() {
        listOf(2, 3, 4, 22, 34).forEach { assertEquals("дня", days(it)) }
    }

    @Test
    fun manyForm() {
        listOf(0, 5, 11, 12, 14, 20, 111, 112).forEach { assertEquals("дней", days(it)) }
    }
}
