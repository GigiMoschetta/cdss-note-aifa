import { Pill } from 'lucide-react'
import type { GoldCase } from '@/lib/types'
import { notaTitle } from '@/lib/data'

export function PatientHeader({ c }: { c: GoldCase }) {
  const p = c.patient
  const meta = [
    p.sex === 'F' ? 'Femmina' : p.sex === 'M' ? 'Maschio' : null,
    p.age ? `${p.age} anni` : null,
    p.city,
    p.fiscal_code,
  ]
    .filter(Boolean)
    .join(' · ')

  return (
    <div className="card flex items-center gap-4 px-5 py-4">
      <img
        src={p.avatar_url}
        alt={p.full_name}
        className="h-14 w-14 flex-none rounded-xl border border-[var(--color-line)]"
      />
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <h2 className="text-[19px] font-bold leading-tight text-[var(--color-ink)]">
            {p.full_name}
          </h2>
          <span className="font-mono text-[11px] font-semibold text-[var(--color-ink-3)]">
            {c.case_id}
          </span>
        </div>
        <p className="mt-1 truncate text-[12.5px] text-[var(--color-ink-2)]">{meta}</p>
      </div>

      <div className="ml-auto flex flex-none items-center gap-3 border-l border-[var(--color-line)] pl-4 text-right">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--color-ink-3)]">
            Prescrizione · Nota {c.nota_id}
          </p>
          <p className="text-[17px] font-bold capitalize text-[var(--color-brand)]">
            {c.drug_id.replace(/_/g, ' ')}
          </p>
          <p className="text-[12px] text-[var(--color-ink-2)]">{c.drug_class_label}</p>
          <p className="mt-0.5 text-[11px] text-[var(--color-ink-3)]">{notaTitle(c.nota_id)}</p>
        </div>
        <div className="flex h-11 w-11 flex-none items-center justify-center rounded-xl bg-[var(--color-brand-50)] text-[var(--color-brand)]">
          <Pill size={20} />
        </div>
      </div>
    </div>
  )
}
