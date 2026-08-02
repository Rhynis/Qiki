/**
 * Instant loading skeleton for the Cẩm nang index. Next.js streams this while the
 * server component reads and groups the article content, mirroring the products
 * route so navigation feels smooth instead of blocking.
 */
export default function Loading() {
  return (
    <section className="mx-auto max-w-6xl space-y-10 px-4 py-8">
      <div className="space-y-2">
        <div className="h-9 w-48 animate-pulse rounded-md bg-slate-200" />
        <div className="h-4 w-96 max-w-full animate-pulse rounded bg-slate-100" />
      </div>
      {Array.from({ length: 2 }).map((_, group) => (
        <div key={group} className="space-y-4">
          <div className="h-6 w-40 animate-pulse rounded bg-slate-200" />
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, card) => (
              <div key={card} className="space-y-3 rounded-xl border border-slate-100 p-5">
                <div className="h-5 w-3/4 animate-pulse rounded bg-slate-200" />
                <div className="h-4 w-full animate-pulse rounded bg-slate-100" />
                <div className="h-4 w-2/3 animate-pulse rounded bg-slate-100" />
                <div className="h-4 w-24 animate-pulse rounded bg-slate-100" />
              </div>
            ))}
          </div>
        </div>
      ))}
    </section>
  )
}
