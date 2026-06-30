import { ExternalLink, FileText } from 'lucide-react'
import { cn } from '@/lib/cn'
import { pdfHref } from '@/lib/pdf'
import type { Anchor } from '@/lib/types'

export type SourceKind = 'block' | 'pass' | 'neutral'

const BORDER: Record<SourceKind, string> = {
  block: 'border-l-[var(--color-no)]',
  pass: 'border-l-[var(--color-ok)]',
  neutral: 'border-l-[var(--color-brand)]',
}

function TruthChip({ truth }: { truth?: string }) {
  if (!truth) return null
  const t = truth.toUpperCase()
  const isTrue = t === 'TRUE' || t === 'VERO'
  const isFalse = t === 'FALSE' || t === 'FALSO'
  return (
    <span
      className={cn(
        'rounded-full px-2 py-0.5 text-[10.5px] font-bold uppercase tracking-wide',
        isTrue && 'bg-[var(--color-ok-bg)] text-[var(--color-ok-fg)]',
        isFalse && 'bg-[var(--color-no-bg)] text-[var(--color-no-fg)]',
        !isTrue && !isFalse && 'bg-[var(--color-line-soft)] text-[var(--color-ink-2)]',
      )}
    >
      {truth}
    </span>
  )
}

export function SourceCard({
  ruleId,
  ruleType,
  truth,
  description,
  anchor,
  kind = 'neutral',
}: {
  ruleId: string
  ruleType?: string
  truth?: string
  description?: string
  anchor: Anchor
  kind?: SourceKind
}) {
  const ref = [
    anchor.pdf_file,
    anchor.page !== undefined && anchor.page !== '' ? `pag. ${anchor.page}` : null,
    anchor.section,
  ]
    .filter(Boolean)
    .join(' · ')

  return (
    <div className={cn('rounded-xl border border-l-4 bg-white p-4', BORDER[kind])}>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="font-mono text-[12px] font-bold text-[var(--color-ink)]">{ruleId}</span>
        {ruleType && (
          <span className="rounded-full bg-[var(--color-line-soft)] px-2 py-0.5 text-[10.5px] font-bold uppercase tracking-wide text-[var(--color-ink-2)]">
            {ruleType}
          </span>
        )}
        <TruthChip truth={truth} />
      </div>
      {description && (
        <p className="mb-2.5 text-[13px] leading-snug text-[var(--color-ink-2)]">{description}</p>
      )}
      <blockquote className="whitespace-pre-wrap rounded-lg bg-[var(--color-canvas)] px-3.5 py-2.5 text-[13.5px] italic leading-relaxed text-[var(--color-ink)]">
        {anchor.excerpt}
      </blockquote>
      <div className="mt-2.5 flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 text-[12px] text-[var(--color-ink-2)]">
          <FileText size={13} className="text-[var(--color-ink-3)]" />
          <span>{ref}</span>
        </div>
        {anchor.pdf_file && anchor.page !== undefined && anchor.page !== '' && (
          <a
            href={pdfHref(anchor.pdf_file, anchor.page, anchor.excerpt)}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 rounded-lg border border-[var(--color-brand)] px-2.5 py-1 text-[11.5px] font-semibold text-[var(--color-brand)] hover:bg-[var(--color-brand-50)]"
          >
            Apri nel PDF <ExternalLink size={11} />
          </a>
        )}
      </div>
    </div>
  )
}
