import type { ReactNode } from 'react'

export function SectionTitle({ children, hint }: { children: ReactNode; hint?: string }) {
  return (
    <div className="mb-2.5 mt-6 flex items-center gap-2.5 px-0.5">
      <span className="h-3.5 w-1 rounded-full bg-[var(--color-brand)]" />
      <span className="text-[13px] font-bold uppercase tracking-wide text-[var(--color-ink-2)]">
        {children}
      </span>
      {hint && <span className="text-[12px] font-normal normal-case text-[var(--color-ink-3)]">· {hint}</span>}
    </div>
  )
}
