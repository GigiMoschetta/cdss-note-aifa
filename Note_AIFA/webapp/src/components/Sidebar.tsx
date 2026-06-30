import { useMemo, useState } from 'react'
import { Search } from 'lucide-react'
import { cn } from '@/lib/cn'
import { CASES } from '@/lib/data'
import type { GoldCase } from '@/lib/types'

const NOTE_TABS = ['Tutte', '01', '13', '66', '97'] as const

function CaseRow({
  c,
  active,
  onClick,
}: {
  c: GoldCase
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'group flex w-full items-center gap-3 rounded-xl border px-3 py-2.5 text-left transition',
        active
          ? 'border-[var(--color-brand)] bg-[var(--color-brand-50)]'
          : 'border-transparent hover:border-[var(--color-line)] hover:bg-[var(--color-line-soft)]',
      )}
    >
      <span
        className={cn(
          'flex h-8 w-8 flex-none items-center justify-center rounded-lg text-[11px] font-semibold',
          active
            ? 'bg-[var(--color-brand)] text-white'
            : 'bg-[var(--color-line-soft)] text-[var(--color-ink-2)]',
        )}
        title={c.patient.full_name}
      >
        {c.patient.initials}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[11px] font-semibold text-[var(--color-ink-3)]">
            {c.case_id}
          </span>
          <span className="truncate text-[13.5px] font-semibold text-[var(--color-ink)]">
            {c.patient.full_name}
          </span>
        </div>
        <div className="truncate text-[12px] text-[var(--color-ink-2)]">
          {c.drug_id.replace(/_/g, ' ')} · {c.patient.sex ?? '—'}
          {c.patient.age ? ` ${c.patient.age}a` : ''}
        </div>
      </div>
    </button>
  )
}

export function Sidebar({
  activeId,
  onSelect,
}: {
  activeId: string
  onSelect: (id: string) => void
}) {
  const [tab, setTab] = useState<(typeof NOTE_TABS)[number]>('Tutte')
  const [q, setQ] = useState('')

  const filtered = useMemo(() => {
    const query = q.trim().toLowerCase()
    return CASES.filter((c) => {
      if (tab !== 'Tutte' && c.nota_id !== tab) return false
      if (!query) return true
      return (
        c.case_id.toLowerCase().includes(query) ||
        c.patient.full_name.toLowerCase().includes(query) ||
        c.drug_id.toLowerCase().includes(query)
      )
    })
  }, [tab, q])

  return (
    <aside className="card flex h-[calc(100vh-7.5rem)] flex-col overflow-hidden p-0">
      <div className="border-b border-[var(--color-line)] p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-[13px] font-bold uppercase tracking-wide text-[var(--color-ink-2)]">
            Pazienti
          </h2>
          <span className="rounded-full bg-[var(--color-line-soft)] px-2 py-0.5 text-[11px] font-semibold text-[var(--color-ink-2)]">
            {filtered.length}
          </span>
        </div>
        <div className="relative mb-3">
          <Search
            size={15}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-ink-3)]"
          />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Cerca nome, farmaco, ID…"
            className="w-full rounded-lg border border-[var(--color-line)] bg-[var(--color-canvas)] py-2 pl-9 pr-3 text-[13px] outline-none focus:border-[var(--color-brand)] focus:bg-white"
          />
        </div>
        <div className="flex gap-1.5">
          {NOTE_TABS.map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={cn(
                'flex-1 rounded-lg px-2 py-1.5 text-[12px] font-semibold transition',
                tab === t
                  ? 'bg-[var(--color-brand)] text-white'
                  : 'bg-[var(--color-line-soft)] text-[var(--color-ink-2)] hover:bg-[var(--color-line)]',
              )}
            >
              {t}
            </button>
          ))}
        </div>
      </div>
      <div className="flex-1 space-y-1 overflow-y-auto p-2.5">
        {filtered.map((c) => (
          <CaseRow
            key={c.case_id}
            c={c}
            active={c.case_id === activeId}
            onClick={() => onSelect(c.case_id)}
          />
        ))}
        {filtered.length === 0 && (
          <p className="px-3 py-6 text-center text-[13px] text-[var(--color-ink-3)]">
            Nessun paziente trovato.
          </p>
        )}
      </div>
    </aside>
  )
}
