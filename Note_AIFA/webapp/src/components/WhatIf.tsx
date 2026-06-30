import { RotateCcw } from 'lucide-react'
import { cn } from '@/lib/cn'
import { FLAG_CATALOG } from '@/lib/data'
import { SectionTitle } from './SectionTitle'

type Value = boolean | number | string | null

const SEV_DOT: Record<string, string> = {
  danger: 'var(--color-no)',
  warn: 'var(--color-warn)',
  info: 'var(--color-brand)',
}

function Switch({ on, onChange }: { on: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      role="switch"
      aria-checked={on}
      onClick={() => onChange(!on)}
      className={cn(
        'relative h-[22px] w-[40px] flex-none rounded-full transition-colors',
        on ? 'bg-[var(--color-brand)]' : 'bg-[var(--color-line)]',
      )}
    >
      <span
        className={cn(
          'absolute top-[2px] h-[18px] w-[18px] rounded-full bg-white shadow transition-all',
          on ? 'left-[20px]' : 'left-[2px]',
        )}
      />
    </button>
  )
}

function BoolRow({
  flagKey,
  value,
  dirty,
  onChange,
}: {
  flagKey: string
  value: boolean
  dirty: boolean
  onChange: (v: boolean) => void
}) {
  const meta = FLAG_CATALOG[flagKey]
  return (
    <label
      className={cn(
        'flex cursor-pointer items-center gap-2.5 rounded-lg border px-3 py-2 transition',
        dirty ? 'border-[var(--color-brand)] bg-[var(--color-brand-50)]' : 'border-[var(--color-line)] bg-white',
      )}
    >
      <span
        className="h-2 w-2 flex-none rounded-full"
        style={{ background: SEV_DOT[meta?.severity ?? 'info'] }}
      />
      <span className="flex-1 text-[13px] leading-tight text-[var(--color-ink)]">
        {meta?.label ?? flagKey.replace(/_/g, ' ')}
      </span>
      <Switch on={value} onChange={onChange} />
    </label>
  )
}

function NumberRow({
  flagKey,
  value,
  dirty,
  onChange,
}: {
  flagKey: string
  value: number
  dirty: boolean
  onChange: (v: number) => void
}) {
  const meta = FLAG_CATALOG[flagKey]
  return (
    <div
      className={cn(
        'flex items-center gap-3 rounded-lg border px-3 py-2 transition',
        dirty ? 'border-[var(--color-brand)] bg-[var(--color-brand-50)]' : 'border-[var(--color-line)] bg-white',
      )}
    >
      <span className="flex-1 text-[13px] text-[var(--color-ink)]">
        {meta?.label ?? flagKey.replace(/_/g, ' ')}
      </span>
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-20 rounded-md border border-[var(--color-line)] bg-white px-2 py-1 text-right text-[13px] outline-none focus:border-[var(--color-brand)]"
      />
      {meta?.unit && <span className="w-12 text-[12px] text-[var(--color-ink-3)]">{meta.unit}</span>}
    </div>
  )
}

export function WhatIf({
  data,
  baseData,
  onChange,
  onReset,
  live,
}: {
  data: Record<string, Value>
  baseData: Record<string, Value>
  onChange: (key: string, value: Value) => void
  onReset: () => void
  live: boolean
}) {
  const entries = Object.entries(data)
  const bools = entries.filter(([, v]) => typeof v === 'boolean') as [string, boolean][]
  const nums = entries.filter(([, v]) => typeof v === 'number') as [string, number][]
  const strs = entries.filter(([, v]) => typeof v === 'string') as [string, string][]
  const isDirty = (k: string, v: Value) => baseData[k] !== v

  return (
    <>
      <SectionTitle hint={live ? 'modifica e ricalcola in tempo reale' : 'motore non avviato'}>
        Quadro clinico · what-if
      </SectionTitle>
      <div className="card p-4">
        {strs.length > 0 && (
          <div className="mb-3 flex flex-wrap gap-2">
            {strs.map(([k, v]) => (
              <span
                key={k}
                className="rounded-full border border-[var(--color-line)] bg-[var(--color-canvas)] px-2.5 py-1 text-[12px] text-[var(--color-ink-2)]"
              >
                {FLAG_CATALOG[k]?.label ?? k}: <b className="text-[var(--color-ink)]">{v}</b>
              </span>
            ))}
          </div>
        )}

        <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
          {bools.map(([k, v]) => (
            <BoolRow
              key={k}
              flagKey={k}
              value={v}
              dirty={isDirty(k, v)}
              onChange={(nv) => onChange(k, nv)}
            />
          ))}
        </div>

        {nums.length > 0 && (
          <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2">
            {nums.map(([k, v]) => (
              <NumberRow
                key={k}
                flagKey={k}
                value={v}
                dirty={isDirty(k, v)}
                onChange={(nv) => onChange(k, nv)}
              />
            ))}
          </div>
        )}

        <div className="mt-3 flex items-center justify-between border-t border-[var(--color-line-soft)] pt-3">
          <p className="text-[12px] text-[var(--color-ink-3)]">
            {live
              ? 'Ogni modifica ricalcola il verdetto sul motore regole (< 5 ms).'
              : 'Avvia il motore regole per il ricalcolo live; ora mostro la valutazione di base.'}
          </p>
          <button
            onClick={onReset}
            className="flex items-center gap-1.5 rounded-lg border border-[var(--color-line)] bg-white px-3 py-1.5 text-[12.5px] font-semibold text-[var(--color-ink-2)] hover:bg-[var(--color-line-soft)]"
          >
            <RotateCcw size={13} /> Ripristina caso
          </button>
        </div>
      </div>
    </>
  )
}
