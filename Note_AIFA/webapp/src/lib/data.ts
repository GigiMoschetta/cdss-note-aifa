import casesJson from '@/data/cases.json'
import evaluationsJson from '@/data/evaluations.json'
import type { CasesPayload, Decision, EvaluateResponse, GoldCase } from './types'

const payload = casesJson as unknown as CasesPayload
const bakedEvals = evaluationsJson as unknown as Record<string, EvaluateResponse>

export const CASES: GoldCase[] = payload.cases
export const FLAG_CATALOG = payload.flag_catalog
export const RULE_CATALOG = payload.rule_catalog
export const HIGHLIGHT_IDS = payload.highlight_case_ids

export function getCase(id: string): GoldCase | undefined {
  return CASES.find((c) => c.case_id === id)
}

/** Valutazione "di base" pre-calcolata (congelata dal rule engine). */
export function bakedEvaluation(caseId: string): EvaluateResponse | undefined {
  return bakedEvals[caseId]
}

/** Decisione effettiva: ROUTED se c'è un route_to, altrimenti la decisione. */
export function effectiveDecision(ev: EvaluateResponse): Decision {
  if (ev.route_to) return 'ROUTED'
  return ev.reimbursement_decision
}

// Override per campi che il catalogo lascia grezzi/minuscoli (es. anagrafica)
const LABEL_OVERRIDE: Record<string, string> = {
  paziente_sesso: 'Sesso',
  paziente_eta: 'Età',
}

export function flagLabel(key: string): string {
  return LABEL_OVERRIDE[key] ?? FLAG_CATALOG[key]?.label ?? key.replace(/_/g, ' ')
}

export function ruleDescription(ruleId: string): string {
  return RULE_CATALOG[ruleId]?.description_it ?? ''
}

export function ruleType(ruleId: string, fallback?: string): string {
  return RULE_CATALOG[ruleId]?.rule_type ?? fallback ?? ''
}

const NOTE_TITLES: Record<string, string> = {
  '01': 'Gastroprotezione (PPI / misoprostolo)',
  '13': 'Ipolipemizzanti (statine, ezetimibe)',
  '66': 'FANS e analgesici',
  '97': 'Anticoagulanti orali (FANV)',
}

export function notaTitle(notaId: string): string {
  return NOTE_TITLES[notaId] ?? `Nota ${notaId}`
}
