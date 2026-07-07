/**
 * Zalo brand logo (blue rounded-square badge with the white "Zalo" wordmark).
 * Self-coloured so it reads as the real Zalo logo — distinct from the generic
 * chat/message icons used elsewhere.
 */
export function ZaloIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 48 48" className={className} role="img" aria-label="Zalo">
      <rect width="48" height="48" rx="12" fill="#0068FF" />
      <text
        x="24"
        y="31"
        textAnchor="middle"
        fontFamily="Arial, Helvetica, sans-serif"
        fontSize="16"
        fontWeight="800"
        letterSpacing="-0.5"
        fill="#ffffff"
      >
        Zalo
      </text>
    </svg>
  )
}
