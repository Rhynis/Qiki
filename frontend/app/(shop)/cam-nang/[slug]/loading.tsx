/**
 * Instant loading skeleton for a single Cẩm nang article while the server component
 * reads and renders its markdown body.
 */
export default function Loading() {
  return (
    <article className="mx-auto max-w-3xl space-y-6 px-4 py-8">
      <div className="h-4 w-32 animate-pulse rounded bg-slate-100" />
      <div className="space-y-3 border-b border-slate-200 pb-6">
        <div className="h-9 w-3/4 animate-pulse rounded-md bg-slate-200" />
        <div className="h-4 w-full max-w-xl animate-pulse rounded bg-slate-100" />
      </div>
      <div className="space-y-3">
        {Array.from({ length: 8 }).map((_, i) => (
          <div
            key={i}
            className="h-4 animate-pulse rounded bg-slate-100"
            style={{ width: `${[92, 84, 96, 70, 88, 60, 90, 76][i]}%` }}
          />
        ))}
      </div>
    </article>
  )
}
