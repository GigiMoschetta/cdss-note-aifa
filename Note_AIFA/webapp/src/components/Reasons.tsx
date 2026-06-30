import { AlertTriangle, CornerUpRight } from 'lucide-react'
import { SectionTitle } from './SectionTitle'
import { SourceCard } from './SourceCard'
import { effectiveDecision, flagLabel, ruleDescription, ruleType } from '@/lib/data'
import type { EvaluateResponse } from '@/lib/types'

const INCLUSIVE_TYPES = new Set(['INCLUSION', 'EXCEPTION', 'EXCEPT', 'PATHWAY', 'SCORE'])

export function Reasons({ ev }: { ev: EvaluateResponse }) {
  const decision = effectiveDecision(ev)
  const rag = ev.rag_payload

  // ---- ROUTED ----
  if (decision === 'ROUTED') {
    return (
      <>
        <SectionTitle hint="motivo del reindirizzamento">Perché</SectionTitle>
        <div className="flex items-start gap-3 rounded-xl border border-[var(--color-route-br)] bg-[var(--color-route-bg)] p-4">
          <CornerUpRight size={20} className="mt-0.5 flex-none text-[var(--color-route-fg)]" />
          <div>
            <p className="text-[14px] font-semibold text-[var(--color-route-fg)]">
              Competenza della Nota {ev.route_to}
            </p>
            {ev.route_reason && (
              <p className="mt-1 text-[13px] leading-snug text-[var(--color-ink-2)]">
                {ev.route_reason}
              </p>
            )}
          </div>
        </div>
        {rag.blocking_rules.map((r) => (
          <div key={r.rule_id} className="mt-3">
            <SourceCard
              ruleId={r.rule_id}
              ruleType={r.rule_type ?? ruleType(r.rule_id)}
              truth={r.truth_value}
              description={ruleDescription(r.rule_id)}
              anchor={r.anchor}
              kind="neutral"
            />
          </div>
        ))}
      </>
    )
  }

  // ---- NON_DETERMINABILE ----
  if (decision === 'NON_DETERMINABILE') {
    const missing = ev.missing_fields_coverage.length
      ? ev.missing_fields_coverage
      : rag.missing_fields
    return (
      <>
        <SectionTitle hint="dati clinici mancanti">Perché</SectionTitle>
        <div className="flex items-start gap-3 rounded-xl border border-[var(--color-warn-br)] bg-[var(--color-warn-bg)] p-4">
          <AlertTriangle size={20} className="mt-0.5 flex-none text-[var(--color-warn-fg)]" />
          <div className="flex-1">
            <p className="text-[14px] font-semibold text-[var(--color-warn-fg)]">
              Servono altri dati per decidere
            </p>
            <p className="mt-1 text-[13px] text-[var(--color-ink-2)]">
              Completa i seguenti campi nel quadro clinico:
            </p>
            <div className="mt-2.5 flex flex-wrap gap-2">
              {missing.map((m) => (
                <span
                  key={m}
                  className="rounded-full border border-[var(--color-warn-br)] bg-white px-2.5 py-1 text-[12.5px] text-[var(--color-warn-fg)]"
                >
                  {flagLabel(m)}
                </span>
              ))}
            </div>
          </div>
        </div>
      </>
    )
  }

  // ---- NON_RIMBORSABILE ----
  if (decision === 'NON_RIMBORSABILE') {
    return (
      <>
        <SectionTitle hint="regola che blocca la rimborsabilità">Perché</SectionTitle>
        {rag.blocking_rules.map((r) => (
          <SourceCard
            key={r.rule_id}
            ruleId={r.rule_id}
            ruleType={r.rule_type ?? ruleType(r.rule_id)}
            truth={r.truth_value}
            description={ruleDescription(r.rule_id)}
            anchor={r.anchor}
            kind="block"
          />
        ))}
      </>
    )
  }

  // ---- RIMBORSABILE ----
  const decisive = rag.passed_rules.filter((r) =>
    INCLUSIVE_TYPES.has(ruleType(r.rule_id).toUpperCase()),
  )
  const shown = decisive.length ? decisive : rag.passed_rules
  return (
    <>
      <SectionTitle hint="criteri soddisfatti nella Nota AIFA">Perché</SectionTitle>
      {shown.map((r) => (
        <SourceCard
          key={r.rule_id}
          ruleId={r.rule_id}
          ruleType={ruleType(r.rule_id)}
          truth="VERO"
          description={ruleDescription(r.rule_id)}
          anchor={r.anchor}
          kind="pass"
        />
      ))}
    </>
  )
}
