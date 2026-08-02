/**
 * Serialize a JSON-LD object for safe embedding inside an inline `<script>` tag.
 *
 * `JSON.stringify` does not escape characters that can terminate the script
 * element or break the surrounding JavaScript — most importantly the `<` in a
 * `</script>` sequence, plus the U+2028/U+2029 line separators. When the object
 * carries user- or admin-supplied text (product name, description, …) an
 * unescaped value such as `</script><script>…` would break out of the script
 * and execute, i.e. stored XSS. Escaping these characters to their `\uXXXX`
 * form keeps the JSON-LD valid (consumers decode the escapes back) while making
 * the payload inert as HTML.
 */

// Built from char codes so the source stays pure ASCII (no literal separators).
const LINE_SEPARATOR = new RegExp(String.fromCharCode(0x2028), 'g')
const PARAGRAPH_SEPARATOR = new RegExp(String.fromCharCode(0x2029), 'g')

export function serializeJsonLd(data: unknown): string {
  return JSON.stringify(data)
    .replace(/</g, '\\u003c')
    .replace(/>/g, '\\u003e')
    .replace(/&/g, '\\u0026')
    .replace(LINE_SEPARATOR, '\\u2028')
    .replace(PARAGRAPH_SEPARATOR, '\\u2029')
}
