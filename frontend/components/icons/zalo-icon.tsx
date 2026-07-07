/**
 * Zalo brand logo — the blue rounded-square app icon with a white speech bubble
 * and the "Zalo" wordmark. Self-coloured and meant to be shown on its own (no
 * extra wrapper/background), the way Zalo appears on other sites.
 */
export function ZaloIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 48 48" className={className} role="img" aria-label="Zalo">
      <rect width="48" height="48" rx="11" fill="#0068FF" />
      <path
        fill="#ffffff"
        d="M24 9.5c-9.1 0-16 5.7-16 12.7 0 4 2.2 7.6 5.7 10-.3 1.7-1.1 3.2-2.3 4.4-.6.6-.2 1.7.7 1.6 3-.2 5.6-1.2 7.6-2.6 1.4.3 2.8.5 4.3.5 9.1 0 16-5.7 16-12.7S33.1 9.5 24 9.5z"
      />
      <text
        x="24"
        y="26.6"
        textAnchor="middle"
        fontFamily="Arial, Helvetica, sans-serif"
        fontSize="11.5"
        fontWeight="800"
        letterSpacing="-0.6"
        fill="#0068FF"
      >
        Zalo
      </text>
    </svg>
  )
}
