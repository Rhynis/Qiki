/**
 * Route transition wrapper. Next.js re-mounts template.tsx on every navigation,
 * so this plays a subtle fade + slide on each page change. Honours reduced-motion.
 */
export default function Template({ children }: { children: React.ReactNode }) {
  return (
    <div className="duration-200 ease-out animate-in fade-in-0 slide-in-from-bottom-1 motion-reduce:animate-none">
      {children}
    </div>
  )
}
