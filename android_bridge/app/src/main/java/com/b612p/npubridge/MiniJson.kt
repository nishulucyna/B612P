package com.b612p.npubridge

/**
 * A small strict JSON reader/writer that behaves like Python's json.loads / json.dumps(indent=2, ensure_ascii=True).
 *
 * Why not org.json: it is lenient about malformed input (the laptop brain rejects it, e.g. trailing garbage) and it
 * escapes "/" and non-ASCII differently, so prompts built on the board would not be byte-identical to the laptop's.
 * Values: Map<String, Any?> (insertion ordered), List<Any?>, String, Long, Double, Boolean, null.
 */
class JsonException(message: String) : Exception(message)

object MiniJson {

    fun parse(text: String): Any? {
        val p = Parser(text)
        p.skipWs()
        val value = p.value()
        p.skipWs()
        if (!p.atEnd()) throw JsonException("extra data at ${p.pos}")
        return value
    }

    /** Python str() of a parsed JSON value (what sanitize_extracted does to non-string scalars). */
    fun pyStr(v: Any?): String = when (v) {
        null -> "None"
        is Boolean -> if (v) "True" else "False"
        is Double -> if (v == Math.floor(v) && Math.abs(v) < 1e16) v.toLong().toString() + ".0" else v.toString()
        else -> v.toString()
    }

    /** json.dumps(map, indent=2) for a flat map of String -> String (null values are written as null). */
    fun dumpsFlat(map: Map<String, String?>): String {
        if (map.isEmpty()) return "{}"
        val sb = StringBuilder("{\n")
        var first = true
        for ((k, v) in map) {
            if (!first) sb.append(",\n")
            first = false
            sb.append("  ").append(quote(k)).append(": ").append(if (v == null) "null" else quote(v))
        }
        return sb.append("\n}").toString()
    }

    fun quote(s: String): String {
        val sb = StringBuilder("\"")
        for (c in s) {
            when {
                c == '"' -> sb.append("\\\"")
                c == '\\' -> sb.append("\\\\")
                c == '\n' -> sb.append("\\n")
                c == '\r' -> sb.append("\\r")
                c == '\t' -> sb.append("\\t")
                c == '\b' -> sb.append("\\b")
                c == '\u000c' -> sb.append("\\f")
                c < ' ' || c.code > 126 -> sb.append(String.format("\\u%04x", c.code))
                else -> sb.append(c)
            }
        }
        return sb.append('"').toString()
    }

    private class Parser(val s: String) {
        var pos = 0

        fun atEnd() = pos >= s.length

        fun skipWs() {
            while (pos < s.length && (s[pos] == ' ' || s[pos] == '\t' || s[pos] == '\n' || s[pos] == '\r')) pos++
        }

        fun value(): Any? {
            if (atEnd()) throw JsonException("unexpected end")
            return when (val c = s[pos]) {
                '{' -> obj()
                '[' -> arr()
                '"' -> str()
                't' -> literal("true", true)
                'f' -> literal("false", false)
                'n' -> literal("null", null)
                else -> if (c == '-' || c.isDigit()) number() else throw JsonException("unexpected '$c' at $pos")
            }
        }

        private fun literal(word: String, v: Any?): Any? {
            if (!s.startsWith(word, pos)) throw JsonException("bad literal at $pos")
            pos += word.length
            return v
        }

        private fun obj(): Map<String, Any?> {
            pos++ // {
            val out = LinkedHashMap<String, Any?>()
            skipWs()
            if (!atEnd() && s[pos] == '}') { pos++; return out }
            while (true) {
                skipWs()
                if (atEnd() || s[pos] != '"') throw JsonException("expected key at $pos")
                val key = str()
                skipWs()
                if (atEnd() || s[pos] != ':') throw JsonException("expected ':' at $pos")
                pos++
                skipWs()
                out[key] = value()
                skipWs()
                if (atEnd()) throw JsonException("unterminated object")
                when (s[pos]) {
                    ',' -> pos++
                    '}' -> { pos++; return out }
                    else -> throw JsonException("expected ',' or '}' at $pos")
                }
            }
        }

        private fun arr(): List<Any?> {
            pos++ // [
            val out = ArrayList<Any?>()
            skipWs()
            if (!atEnd() && s[pos] == ']') { pos++; return out }
            while (true) {
                skipWs()
                out.add(value())
                skipWs()
                if (atEnd()) throw JsonException("unterminated array")
                when (s[pos]) {
                    ',' -> pos++
                    ']' -> { pos++; return out }
                    else -> throw JsonException("expected ',' or ']' at $pos")
                }
            }
        }

        private fun str(): String {
            pos++ // opening quote
            val sb = StringBuilder()
            while (true) {
                if (atEnd()) throw JsonException("unterminated string")
                val c = s[pos++]
                when {
                    c == '"' -> return sb.toString()
                    c == '\\' -> {
                        if (atEnd()) throw JsonException("bad escape")
                        when (val e = s[pos++]) {
                            '"' -> sb.append('"'); '\\' -> sb.append('\\'); '/' -> sb.append('/')
                            'b' -> sb.append('\b'); 'f' -> sb.append('\u000c'); 'n' -> sb.append('\n')
                            'r' -> sb.append('\r'); 't' -> sb.append('\t')
                            'u' -> {
                                if (pos + 4 > s.length) throw JsonException("bad \\u escape")
                                sb.append(s.substring(pos, pos + 4).toIntOrNull(16)?.toChar()
                                    ?: throw JsonException("bad \\u escape"))
                                pos += 4
                            }
                            else -> throw JsonException("bad escape \\$e")
                        }
                    }
                    c < ' ' -> throw JsonException("control character in string")   // strict, like Python
                    else -> sb.append(c)
                }
            }
        }

        private fun number(): Any {
            val start = pos
            if (s[pos] == '-') pos++
            while (!atEnd() && s[pos].isDigit()) pos++
            var isFloat = false
            if (!atEnd() && s[pos] == '.') { isFloat = true; pos++; while (!atEnd() && s[pos].isDigit()) pos++ }
            if (!atEnd() && (s[pos] == 'e' || s[pos] == 'E')) {
                isFloat = true; pos++
                if (!atEnd() && (s[pos] == '+' || s[pos] == '-')) pos++
                while (!atEnd() && s[pos].isDigit()) pos++
            }
            val text = s.substring(start, pos)
            return try {
                if (isFloat) text.toDouble() else text.toLong()
            } catch (e: NumberFormatException) {
                throw JsonException("bad number $text")
            }
        }
    }
}
