/** Normalize customer-entered order number before guest lookup. */
export function sanitizeOrderNumberForLookup(value: string): string {
  return value
    .trim()
    .replace(/[.,;:]+$/u, '')
    .trim()
}
