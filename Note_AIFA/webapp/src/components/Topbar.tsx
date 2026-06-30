import { Stethoscope } from 'lucide-react'
import { cn } from '@/lib/cn'

function ServiceDot({ label, ok }: { label: string; ok: boolean }) {
  return (
    <span className="flex items-center gap-2 text-[12.5px] text-[var(--color-ink-2)]">
      <span
        className={cn(
          'h-2.5 w-2.5 rounded-full',
          ok
            ? 'bg-[var(--color-ok)] shadow-[0_0_0_3px_rgba(22,163,74,0.15)]'
            : 'bg-[var(--color-ink-3)] shadow-[0_0_0_3px_rgba(152,162,179,0.15)]',
        )}
      />
      {label} · {ok ? 'online' : 'offline'}
    </span>
  )
}

export function Topbar({ engineOk, llmOk }: { engineOk: boolean; llmOk: boolean }) {
  return (
    <header className="card flex items-center justify-between px-5 py-3.5">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 flex-none items-center justify-center rounded-xl bg-gradient-to-br from-[#0e7c7b] to-[#13a3a2] text-white">
          <Stethoscope size={20} strokeWidth={2.2} />
        </div>
        <div>
          <h1 className="text-[15.5px] font-bold leading-tight text-[var(--color-ink)]">
            Verifica prescrizione · Note AIFA
          </h1>
          <p className="mt-0.5 text-[12px] text-[var(--color-ink-2)]">
            Supporto decisionale alla rimborsabilità SSN · Note 01 · 13 · 66 · 97
          </p>
        </div>
      </div>
      <div className="flex items-center gap-5">
        <ServiceDot label="Motore regole" ok={engineOk} />
        <ServiceDot label="Spiegazione AI" ok={llmOk} />
      </div>
    </header>
  )
}
