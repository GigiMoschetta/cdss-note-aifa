import { Ban, CheckCircle2, CornerUpRight, HelpCircle, type LucideIcon } from 'lucide-react'
import type { Decision } from './types'

export interface DecisionToken {
  label: string
  short: string
  Icon: LucideIcon
  fg: string
  bg: string
  border: string
  dot: string
}

export const DECISION_TOKENS: Record<Decision, DecisionToken> = {
  RIMBORSABILE: {
    label: 'Rimborsabile SSN',
    short: 'Rimborsabile',
    Icon: CheckCircle2,
    fg: 'var(--color-ok-fg)',
    bg: 'var(--color-ok-bg)',
    border: 'var(--color-ok-br)',
    dot: 'var(--color-ok)',
  },
  NON_RIMBORSABILE: {
    label: 'Non rimborsabile SSN',
    short: 'Non rimborsabile',
    Icon: Ban,
    fg: 'var(--color-no-fg)',
    bg: 'var(--color-no-bg)',
    border: 'var(--color-no-br)',
    dot: 'var(--color-no)',
  },
  NON_DETERMINABILE: {
    label: 'Dati insufficienti',
    short: 'Non determinabile',
    Icon: HelpCircle,
    fg: 'var(--color-warn-fg)',
    bg: 'var(--color-warn-bg)',
    border: 'var(--color-warn-br)',
    dot: 'var(--color-warn)',
  },
  ROUTED: {
    label: 'Competenza di altra Nota',
    short: 'Reindirizzato',
    Icon: CornerUpRight,
    fg: 'var(--color-route-fg)',
    bg: 'var(--color-route-bg)',
    border: 'var(--color-route-br)',
    dot: 'var(--color-route)',
  },
}

export function decisionToken(d: Decision): DecisionToken {
  return DECISION_TOKENS[d] ?? DECISION_TOKENS.NON_DETERMINABILE
}

/** Frase di razionale in italiano per la testata del verdetto. */
export function rationale(
  decision: Decision,
  notaId: string,
  drug: string,
  routeTo: string | null,
): string {
  const farmaco = drug.replace(/_/g, ' ')
  switch (decision) {
    case 'RIMBORSABILE':
      return `Il paziente soddisfa i criteri della Nota ${notaId}: la prescrizione di ${farmaco} è a carico del SSN.`
    case 'NON_RIMBORSABILE':
      return `Il paziente non soddisfa i criteri della Nota ${notaId}: la prescrizione di ${farmaco} non è rimborsabile dal SSN.`
    case 'ROUTED':
      return `Caso di competenza della Nota ${routeTo ?? '—'}: vanno verificati i criteri di quella Nota per ${farmaco}.`
    case 'NON_DETERMINABILE':
    default:
      return `Dati clinici insufficienti per decidere: completa i campi indicati per ottenere il verdetto.`
  }
}
