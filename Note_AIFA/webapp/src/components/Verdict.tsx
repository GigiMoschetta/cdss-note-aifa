import { motion } from 'motion/react'
import { decisionToken, rationale } from '@/lib/decision'
import { effectiveDecision } from '@/lib/data'
import type { EvaluateResponse } from '@/lib/types'

const STATUS_LABEL: Record<string, string> = {
  FINAL: 'Decisione finale',
  ROUTED: 'Reindirizzato',
  INCOMPLETE: 'Da completare',
}

export function Verdict({ ev }: { ev: EvaluateResponse }) {
  const decision = effectiveDecision(ev)
  const tok = decisionToken(decision)
  const { Icon } = tok
  const text = rationale(decision, ev.nota_evaluated, ev.drug_evaluated, ev.route_to)
  const status = STATUS_LABEL[(ev.decision_status || '').toUpperCase()] ?? ev.decision_status

  return (
    <motion.div
      key={decision + ev.drug_evaluated}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: 'easeOut' }}
      className="flex items-center gap-5 rounded-2xl border p-5"
      style={{ background: tok.bg, borderColor: tok.border }}
    >
      <div
        className="flex h-16 w-16 flex-none items-center justify-center rounded-full text-white"
        style={{ background: tok.dot }}
      >
        <Icon size={32} strokeWidth={2.4} />
      </div>
      <div className="flex-1">
        <p className="text-[25px] font-extrabold leading-none" style={{ color: tok.fg }}>
          {tok.label}
        </p>
        <p className="mt-2 text-[14.5px] leading-snug text-[var(--color-ink)]">{text}</p>
      </div>
      <span
        className="flex-none self-start whitespace-nowrap rounded-full border border-black/5 bg-white/70 px-3 py-1 text-[11px] font-bold uppercase tracking-wide"
        style={{ color: tok.fg }}
      >
        {status}
      </span>
    </motion.div>
  )
}
