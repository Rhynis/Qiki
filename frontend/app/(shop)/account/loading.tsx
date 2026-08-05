/** Instant skeleton for the account page during route transitions. */
export default function Loading() {
  return (
    <section className="mx-auto max-w-4xl space-y-6 px-4 py-8">
      <div className="space-y-2">
        <div className="h-8 w-48 animate-pulse rounded-md bg-slate-200" />
        <div className="h-4 w-72 max-w-full animate-pulse rounded bg-slate-100" />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="space-y-3 rounded-xl border border-slate-100 p-5">
            <div className="h-4 w-24 animate-pulse rounded bg-slate-200" />
            <div className="h-4 w-full animate-pulse rounded bg-slate-100" />
            <div className="h-4 w-2/3 animate-pulse rounded bg-slate-100" />
          </div>
        ))}
      </div>
    </section>
  )
}
