import { describe, expect, it } from 'vitest'
import { serializeJsonLd } from '@/lib/utils/json-ld'

describe('serializeJsonLd', () => {
  it('escapes a </script> breakout attempt so no raw closing tag survives', () => {
    const html = serializeJsonLd({ name: '</script><script>alert(1)</script>' })

    expect(html).not.toContain('</script>')
    expect(html).not.toContain('<script>')
    expect(html).toContain('\\u003c')
  })

  it('escapes < > & and the U+2028/U+2029 line separators', () => {
    const html = serializeJsonLd({
      a: '<',
      b: '>',
      c: '&',
      d: `x${String.fromCharCode(0x2028)}y${String.fromCharCode(0x2029)}z`,
    })

    expect(html).not.toMatch(/[<>&]/)
    expect(html).not.toContain(String.fromCharCode(0x2028))
    expect(html).not.toContain(String.fromCharCode(0x2029))
    expect(html).toContain('\\u2028')
    expect(html).toContain('\\u2029')
  })

  it('stays valid JSON that round-trips back to the original value', () => {
    const data = {
      '@context': 'https://schema.org',
      name: 'Bình gas </script> 12kg',
      price: 710000,
    }

    // The escapes are inside JSON string values, so JSON.parse restores them.
    expect(JSON.parse(serializeJsonLd(data))).toEqual(data)
  })
})
