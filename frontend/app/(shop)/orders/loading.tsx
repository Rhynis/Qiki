/** Instant skeleton for the orders list during route transitions. */
export default function Loading() {
  return (
    <section className="mx-auto max-w-6xl space-y-6 px-4 py-8">
      <div className="h-8 w-44 animate-pulse rounded-md bg-slate-200" />
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="flex items-center justify-between gap-4 rounded-xl border border-slate-100 p-4"
          >
            <div className="space-y-2">
              <div className="h-4 w-40 animate-pulse rounded bg-slate-200" />
              <div className="h-4 w-24 animate-pulse rounded bg-slate-100" />
            </div>
            <div className="h-8 w-28 animate-pulse rounded-full bg-slate-100" />
          </div>
        ))}
      </div>
    </section>
  )
}
