/**
 * Instant loading skeleton for a product detail route. Next.js streams this while
 * the server component fetches the product, so opening a product (and coming back)
 * feels smooth instead of blocking on the fetch.
 */
export default function Loading() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <div className="h-4 w-40 animate-pulse rounded bg-slate-100" />
      <div className="mt-6 grid grid-cols-1 gap-8 lg:grid-cols-2">
        <div className="aspect-[4/3] w-full animate-pulse rounded-xl bg-slate-100" />
        <div className="space-y-4">
          <div className="h-4 w-24 animate-pulse rounded bg-slate-100" />
          <div className="h-8 w-3/4 animate-pulse rounded-md bg-slate-200" />
          <div className="flex gap-2">
            <div className="h-6 w-20 animate-pulse rounded-full bg-slate-100" />
            <div className="h-6 w-28 animate-pulse rounded-full bg-slate-100" />
          </div>
          <div className="h-9 w-40 animate-pulse rounded-md bg-slate-200" />
          <div className="space-y-2">
            <div className="h-4 w-full animate-pulse rounded bg-slate-100" />
            <div className="h-4 w-5/6 animate-pulse rounded bg-slate-100" />
          </div>
          <div className="h-11 w-full animate-pulse rounded-md bg-slate-100" />
        </div>
      </div>
    </section>
  )
}
