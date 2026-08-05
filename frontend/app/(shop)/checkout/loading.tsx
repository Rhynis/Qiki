/** Instant skeleton for the checkout page during route transitions. */
export default function Loading() {
  return (
    <section className="mx-auto max-w-6xl space-y-6 px-4 py-8">
      <div className="h-8 w-48 animate-pulse rounded-md bg-slate-200" />
      <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        <div className="space-y-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="space-y-2">
              <div className="h-4 w-32 animate-pulse rounded bg-slate-200" />
              <div className="h-10 w-full animate-pulse rounded-md bg-slate-100" />
            </div>
          ))}
        </div>
        <div className="h-64 animate-pulse rounded-xl border border-slate-100 bg-slate-50" />
      </div>
    </section>
  )
}
