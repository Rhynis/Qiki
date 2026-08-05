/** Instant skeleton for a single order's detail during route transitions. */
export default function Loading() {
  return (
    <section className="mx-auto max-w-3xl space-y-6 px-4 py-8">
      <div className="h-4 w-28 animate-pulse rounded bg-slate-100" />
      <div className="space-y-2">
        <div className="h-8 w-56 animate-pulse rounded-md bg-slate-200" />
        <div className="h-4 w-40 animate-pulse rounded bg-slate-100" />
      </div>
      <div className="h-24 animate-pulse rounded-xl border border-slate-100 bg-slate-50" />
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div
            key={i}
            className="flex items-center justify-between rounded-xl border border-slate-100 p-4"
          >
            <div className="h-4 w-1/2 animate-pulse rounded bg-slate-200" />
            <div className="h-4 w-20 animate-pulse rounded bg-slate-100" />
          </div>
        ))}
      </div>
    </section>
  )
}
