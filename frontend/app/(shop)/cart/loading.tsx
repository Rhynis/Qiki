/** Instant skeleton for the cart page during route transitions. */
export default function Loading() {
  return (
    <section className="mx-auto max-w-6xl space-y-6 px-4 py-8">
      <div className="h-8 w-40 animate-pulse rounded-md bg-slate-200" />
      <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="flex items-center gap-4 rounded-xl border border-slate-100 p-4">
              <div className="h-16 w-16 animate-pulse rounded-lg bg-slate-100" />
              <div className="flex-1 space-y-2">
                <div className="h-4 w-1/2 animate-pulse rounded bg-slate-200" />
                <div className="h-4 w-1/4 animate-pulse rounded bg-slate-100" />
              </div>
              <div className="h-8 w-24 animate-pulse rounded bg-slate-100" />
            </div>
          ))}
        </div>
        <div className="h-56 animate-pulse rounded-xl border border-slate-100 bg-slate-50" />
      </div>
    </section>
  )
}
