/** Instant skeleton for the order-tracking page during route transitions. */
export default function Loading() {
  return (
    <section className="mx-auto max-w-xl space-y-6 px-4 py-8">
      <div className="space-y-2">
        <div className="h-8 w-48 animate-pulse rounded-md bg-slate-200" />
        <div className="h-4 w-64 max-w-full animate-pulse rounded bg-slate-100" />
      </div>
      <div className="space-y-4">
        {Array.from({ length: 2 }).map((_, i) => (
          <div key={i} className="space-y-2">
            <div className="h-4 w-28 animate-pulse rounded bg-slate-200" />
            <div className="h-10 w-full animate-pulse rounded-md bg-slate-100" />
          </div>
        ))}
        <div className="h-10 w-full animate-pulse rounded-md bg-slate-200" />
      </div>
    </section>
  )
}
