/**
 * Instant loading skeleton for the products route. Next.js streams this while the
 * server component fetches the catalog, so navigating between categories feels
 * smooth instead of blocking on the fetch.
 */
export default function Loading() {
  return (
    <section className="mx-auto max-w-6xl space-y-6 px-4 py-8">
      <div className="space-y-2">
        <div className="h-8 w-56 animate-pulse rounded-md bg-slate-200" />
        <div className="h-4 w-80 max-w-full animate-pulse rounded bg-slate-100" />
      </div>
      <div className="flex flex-wrap gap-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-9 w-24 animate-pulse rounded-full bg-slate-100" />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="space-y-3 rounded-xl border border-slate-100 p-4">
            <div className="h-32 w-full animate-pulse rounded-lg bg-slate-100" />
            <div className="h-4 w-3/4 animate-pulse rounded bg-slate-200" />
            <div className="h-4 w-1/2 animate-pulse rounded bg-slate-100" />
            <div className="h-9 w-full animate-pulse rounded-md bg-slate-100" />
          </div>
        ))}
      </div>
    </section>
  )
}
