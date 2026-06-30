import { useState } from 'react'
import { ChevronDown, ChevronUp, ExternalLink, FileText } from 'lucide-react'
import { SectionTitle } from './SectionTitle'
import { cn } from '@/lib/cn'
import { flagLabel, ruleDescription } from '@/lib/data'
import { pdfHref } from '@/lib/pdf'
import type { CoverageTraceEntry, EvaluateResponse } from '@/lib/types'

// ── Etichette per fase ──────────────────────────────────────────────────────
const PHASE_LABEL: Record<number, string> = {
  0: 'Variabili derivate',
  1: 'Scope',
  2: 'Eccezioni / Routing',
  3: 'Esclusioni assolute',
  4: 'Criteri di inclusione',
  5: 'Percorso terapeutico',
  6: 'Dose',
  7: 'Preferenza',
  8: 'Avvertenze',
  9: 'Conflitti di dose',
  10: 'Decisione finale',
}

// ── Contesto semantico per tipo di regola ───────────────────────────────────
const RULE_TYPE_META: Record<string, { label: string; explain: string }> = {
  SCOPE: {
    label: 'Ambito di applicazione',
    explain:
      'Verifica che il paziente rientri nell\'ambito clinico della Nota. VERO = Nota applicabile; FALSO = non applicabile.',
  },
  EXCL_HARD: {
    label: 'Controindicazione assoluta',
    explain:
      'Condizione che esclude categoricamente la rimborsabilità se presente. FALSO = controindicazione assente (favorevole); VERO = controindicazione presente (blocca).',
  },
  EXCL: {
    label: 'Esclusione',
    explain: 'Condizione escludente. FALSO = esclusione non applicata (favorevole).',
  },
  EXCL_HARD_L2: {
    label: 'Controindicazione (livello 2)',
    explain: 'Controindicazione secondaria. FALSO = controindicazione assente (favorevole).',
  },
  INCLHARD: {
    label: 'Inclusione obbligatoria',
    explain: 'Condizione strettamente necessaria. VERO = soddisfatta; FALSO = non soddisfatta.',
  },
  INCLUSION: {
    label: 'Criterio di inclusione',
    explain:
      'Condizione necessaria per la rimborsabilità. VERO = criterio soddisfatto; FALSO = non soddisfatto.',
  },
  PATHWAY: {
    label: 'Percorso terapeutico',
    explain:
      'Determina il percorso di rimborsabilità (es. percorso A/B/C della Nota). VERO = percorso attivato.',
  },
  EXCEPTION: {
    label: 'Eccezione',
    explain: 'Consente di bypassare le restrizioni standard in casi particolari.',
  },
  DOSE_STANDARD: { label: 'Dose standard', explain: 'Posologia standard rimborsata.' },
  DOSE_RIDOTTA: { label: 'Dose ridotta', explain: 'Dose ridotta raccomandata per questo paziente.' },
  DOSE_CONTROINDICATA: {
    label: 'Dose controindicata',
    explain: 'Questo dosaggio non è rimborsabile per il profilo clinico.',
  },
  PREFERENCE: {
    label: 'Preferenza terapeutica',
    explain: 'Indica la preferenza tra opzioni equivalenti rimborsate.',
  },
  WARNING: {
    label: 'Avvertenza',
    explain: 'Nota informativa; non blocca la rimborsabilità.',
  },
  SCORE: {
    label: 'Punteggio clinico',
    explain: 'Verifica un punteggio clinico calcolato (es. CHA2DS2-VASc).',
  },
}

// ── Interpretazione clinica dell'esito ──────────────────────────────────────
function getInterpretation(entry: CoverageTraceEntry): string {
  const type = entry.rule_type.toUpperCase()
  const tv = entry.truth_value

  if (type === 'EXCL_HARD' || type === 'EXCL' || type === 'EXCL_HARD_L2') {
    if (tv === 'FALSE') return 'Controindicazione assente → non blocca la rimborsabilità'
    if (tv === 'TRUE') return 'Controindicazione presente → blocca la rimborsabilità'
    return 'Presenza controindicazione non determinabile (dato mancante)'
  }
  if (type === 'SCOPE') {
    if (tv === 'TRUE') return 'Paziente nell\'ambito → la Nota si applica'
    if (tv === 'FALSE') return 'Paziente fuori dall\'ambito → non rimborsabile'
    return 'Ambito non determinabile (dato mancante)'
  }
  if (type === 'INCLUSION' || type === 'INCLHARD') {
    if (tv === 'TRUE') return 'Criterio soddisfatto → rimborsabilità confermata'
    if (tv === 'FALSE') return 'Criterio non soddisfatto → non rimborsabile'
    return 'Criterio non valutabile (dato mancante)'
  }
  if (type === 'PATHWAY') {
    if (tv === 'TRUE') return 'Percorso attivato → criteri clinici soddisfatti'
    if (tv === 'FALSE') return 'Percorso non applicabile per questo paziente'
    return 'Percorso non determinabile (dato mancante)'
  }
  if (type === 'EXCEPTION') {
    if (tv === 'TRUE') return 'Eccezione attivata → bypass delle restrizioni standard'
    return 'Eccezione non applicabile'
  }
  if (entry.outcome === 'BYPASS') return 'Non applicabile → bypassato'
  if (entry.outcome === 'PROCEED') return 'Valutazione superata → fase successiva'
  if (entry.outcome === 'UNKNOWN_PENDING') return 'Non determinabile → dati insufficienti'
  return ''
}

// ── Colori outcome (colore primario nella riga) ─────────────────────────────
const OUTCOME_STYLE: Record<string, string> = {
  PROCEED: 'bg-[var(--color-ok-bg)] text-[var(--color-ok-fg)]',
  NON_RIMBORSABILE: 'bg-[var(--color-no-bg)] text-[var(--color-no-fg)]',
  BYPASS: 'bg-[var(--color-line-soft)] text-[var(--color-ink-2)]',
  ROUTE: 'bg-[var(--color-route-bg)] text-[var(--color-route-fg)]',
  UNKNOWN_PENDING: 'bg-[var(--color-warn-bg)] text-[var(--color-warn-fg)]',
}
const OUTCOME_LABEL: Record<string, string> = {
  PROCEED: 'Avanza',
  NON_RIMBORSABILE: 'Blocca',
  BYPASS: 'Bypassato',
  ROUTE: 'Reindirizzato',
  UNKNOWN_PENDING: 'Indeterminato',
}

// Colore truth_value per regole "normali" vs "escludenti" (EXCL ha semantica inversa)
function truthStyle(entry: CoverageTraceEntry) {
  const isExcl =
    entry.rule_type.toUpperCase().startsWith('EXCL') ||
    entry.rule_type.toUpperCase() === 'EXCLUSION'
  // Per EXCL: FALSE = favorevole (verde), TRUE = sfavorevole (rosso)
  // Per il resto: TRUE = favorevole, FALSE = sfavorevole
  const good = isExcl ? entry.truth_value === 'FALSE' : entry.truth_value === 'TRUE'
  const bad = isExcl ? entry.truth_value === 'TRUE' : entry.truth_value === 'FALSE'
  if (good) return 'bg-[var(--color-ok-bg)] text-[var(--color-ok-fg)]'
  if (bad) return 'bg-[var(--color-no-bg)] text-[var(--color-no-fg)]'
  return 'bg-[var(--color-warn-bg)] text-[var(--color-warn-fg)]'
}
const TRUTH_LABEL: Record<string, string> = { TRUE: 'VERO', FALSE: 'FALSO', UNKNOWN: '?' }

// ── Riga espandibile della traccia ──────────────────────────────────────────
function TraceRow({ entry }: { entry: CoverageTraceEntry }) {
  const [open, setOpen] = useState(false)
  const hasFacts = Object.keys(entry.facts_used).length > 0
  const hasMissing = entry.missing_fields.length > 0
  const desc = ruleDescription(entry.rule_id)
  const meta = RULE_TYPE_META[entry.rule_type.toUpperCase()] ?? RULE_TYPE_META[entry.rule_type]
  const interpretation = getInterpretation(entry)
  const hasAnchor = !!entry.anchor?.pdf_file

  return (
    <div className="border-b border-[var(--color-line-soft)] last:border-0">
      {/* Riga compatta — click per espandere */}
      <div
        className="flex cursor-pointer items-center gap-2 px-3 py-2.5 text-[12.5px] hover:bg-[var(--color-line-soft)]"
        onClick={() => setOpen(!open)}
      >
        <span className="w-5 flex-none text-center font-mono text-[10.5px] text-[var(--color-ink-3)]">
          {entry.phase}
        </span>
        <span className="w-36 flex-none truncate font-mono text-[11.5px] font-semibold text-[var(--color-ink)]">
          {entry.rule_id}
        </span>
        <span className="hidden w-24 flex-none truncate text-[11px] text-[var(--color-ink-3)] sm:block">
          {meta?.label ?? entry.rule_type}
        </span>
        <span
          className={cn(
            'w-16 flex-none rounded-full px-2 py-0.5 text-center text-[10.5px] font-bold',
            truthStyle(entry),
          )}
        >
          {TRUTH_LABEL[entry.truth_value] ?? entry.truth_value}
        </span>
        <span
          className={cn(
            'flex-none rounded-full px-2 py-0.5 text-[10.5px] font-bold',
            OUTCOME_STYLE[entry.outcome] ?? 'bg-[var(--color-line-soft)] text-[var(--color-ink-2)]',
          )}
        >
          {OUTCOME_LABEL[entry.outcome] ?? entry.outcome}
        </span>
        <span className="min-w-0 flex-1 truncate text-[11px] text-[var(--color-ink-3)]">
          {interpretation}
        </span>
        {open
          ? <ChevronUp size={13} className="flex-none text-[var(--color-ink-3)]" />
          : <ChevronDown size={13} className="flex-none text-[var(--color-ink-3)]" />}
      </div>

      {/* Pannello espanso: cosa / come / perché */}
      {open && (
        <div className="mx-3 mb-3 space-y-3 rounded-xl border border-[var(--color-line)] bg-white p-4 text-[13px]">
          {/* Interpretazione */}
          {interpretation && (
            <div
              className={cn(
                'rounded-lg px-3 py-2 text-[12.5px] font-semibold',
                OUTCOME_STYLE[entry.outcome] ?? 'bg-[var(--color-line-soft)] text-[var(--color-ink-2)]',
              )}
            >
              {interpretation}
            </div>
          )}

          {/* COSA: tipo + descrizione */}
          <div>
            <p className="mb-1 text-[10.5px] font-bold uppercase tracking-wide text-[var(--color-ink-3)]">
              Cosa verifica questa regola
            </p>
            {meta && (
              <p className="mb-0.5 text-[12px] font-semibold text-[var(--color-brand)]">
                {meta.label}
              </p>
            )}
            {meta && (
              <p className="text-[12px] leading-snug text-[var(--color-ink-2)]">{meta.explain}</p>
            )}
            {desc && (
              <p className="mt-1 text-[12.5px] leading-snug text-[var(--color-ink)]">{desc}</p>
            )}
          </div>

          {/* COME: dati clinici usati */}
          {(hasFacts || hasMissing) && (
            <div>
              <p className="mb-1.5 text-[10.5px] font-bold uppercase tracking-wide text-[var(--color-ink-3)]">
                Come è stata valutata
              </p>
              {hasFacts && (
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(entry.facts_used).map(([k, v]) => (
                    <span
                      key={k}
                      className="rounded border border-[var(--color-line)] bg-[var(--color-canvas)] px-2 py-1 text-[11.5px]"
                    >
                      <span className="text-[var(--color-ink-2)]">{k.replace(/_/g, ' ')}: </span>
                      <b className={cn(
                        v === true ? 'text-[var(--color-ok-fg)]' :
                        v === false ? 'text-[var(--color-no-fg)]' :
                        'text-[var(--color-ink)]'
                      )}>
                        {v === true ? 'sì' : v === false ? 'no' : String(v)}
                      </b>
                    </span>
                  ))}
                </div>
              )}
              {hasMissing && (
                <div className="mt-2">
                  <p className="mb-1 text-[11px] font-semibold text-[var(--color-warn-fg)]">
                    Dati mancanti (impossibile valutare):
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {entry.missing_fields.map((f) => (
                      <span
                        key={f}
                        className="rounded border border-[var(--color-warn-br)] bg-[var(--color-warn-bg)] px-2 py-0.5 text-[11.5px] text-[var(--color-warn-fg)]"
                      >
                        {flagLabel(f)}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* PERCHÉ: testo normativo AIFA + link PDF */}
          {hasAnchor && (
            <div>
              <p className="mb-1.5 text-[10.5px] font-bold uppercase tracking-wide text-[var(--color-ink-3)]">
                Testo normativo AIFA
              </p>
              <blockquote className="mb-2 rounded-lg border-l-4 border-l-[var(--color-brand)] bg-[var(--color-canvas)] px-3.5 py-2.5 text-[13px] italic leading-relaxed text-[var(--color-ink)]">
                {entry.anchor.excerpt}
              </blockquote>
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5 text-[11.5px] text-[var(--color-ink-3)]">
                  <FileText size={12} />
                  <span>
                    {entry.anchor.pdf_file} · pag. {entry.anchor.page}
                    {entry.anchor.section ? ` · ${entry.anchor.section}` : ''}
                  </span>
                </div>
                <a
                  href={pdfHref(entry.anchor.pdf_file, entry.anchor.page, entry.anchor.excerpt)}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="flex items-center gap-1 rounded-lg border border-[var(--color-brand)] px-3 py-1 text-[12px] font-semibold text-[var(--color-brand)] hover:bg-[var(--color-brand-50)]"
                >
                  Apri nel PDF <ExternalLink size={11} />
                </a>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// Descrizioni cliniche per punteggi noti
const SCORE_DESCRIPTION: Record<string, string> = {
  'CHA2DS2-VASc': 'Stratificazione del rischio tromboembolico in fibrillazione atriale (scompenso, ipertensione, età, diabete, ictus/TIA, vascolopatia, sesso)',
  'HAS-BLED':     'Rischio emorragico in pazienti in terapia anticoagulante',
  'SCORE2':       'Rischio cardiovascolare a 10 anni nella popolazione generale',
  'SCORE2-OP':    'Rischio cardiovascolare a 10 anni negli anziani (≥70 anni)',
}

// Numero di Nota a cui appartiene un PDF (es. "nota-97.pdf" → "97", "Nota_01.pdf" → "01")
function notaOfPdf(pdf?: string): string | null {
  const m = pdf?.match(/(\d{2})/)
  return m ? m[1] : null
}

// ── Sezione punteggi calcolati ───────────────────────────────────────────────
function ScoresSection({
  scores,
  notaEvaluated,
}: {
  scores: EvaluateResponse['rag_payload']['computed_scores']
  notaEvaluated: string
}) {
  // Mostra solo i punteggi pertinenti alla Nota valutata (il documento di
  // ancoraggio dello score deve corrispondere alla Nota). Evita di proporre,
  // es., il CHA2DS2-VASc su un caso di gastroprotezione (Nota 01).
  const entries = Object.values(scores).filter(
    (s) => notaOfPdf(s.anchor?.pdf_file) === notaEvaluated,
  )
  if (!entries.length) return null
  return (
    <div className="mt-4">
      <SectionTitle hint="punteggi clinici calcolati dal motore">Punteggi calcolati</SectionTitle>
      <div className="card divide-y divide-[var(--color-line-soft)] p-0">
        {entries.map((s) => {
          const desc = SCORE_DESCRIPTION[s.score_name]
          const unknown = s.eligible === 'UNKNOWN'
          return (
            <div key={s.score_name} className="flex items-start gap-3 px-4 py-3.5">
              <div className="flex-1 min-w-0">
                <p className="text-[14px] font-semibold text-[var(--color-ink)]">{s.score_name}</p>
                {desc && (
                  <p className="mt-0.5 text-[12px] leading-snug text-[var(--color-ink-3)]">{desc}</p>
                )}
                {unknown && s.missing_components.length > 0 && (
                  <p className="mt-1 text-[11.5px] text-[var(--color-warn-fg)]">
                    Non determinabile: {s.missing_components.length === 1 ? 'manca il dato' : 'mancano i dati'}{' '}
                    {s.missing_components.map((c) => flagLabel(c)).join(', ')}.
                  </p>
                )}
              </div>
              <div className="flex flex-none items-center gap-3">
                <div className="text-right text-[13.5px]">
                  <span className="font-bold text-[var(--color-ink)]">
                    {s.min_score === s.max_score ? s.min_score : `${s.min_score}–${s.max_score}`}
                  </span>
                  {s.threshold !== null && (
                    <span className="ml-1 text-[var(--color-ink-2)]">/ soglia ≥{s.threshold}</span>
                  )}
                </div>
                <span
                  className={cn(
                    'rounded-full px-3 py-1 text-[11.5px] font-bold whitespace-nowrap',
                    s.eligible === 'TRUE'
                      ? 'bg-[var(--color-ok-bg)] text-[var(--color-ok-fg)]'
                      : s.eligible === 'FALSE'
                        ? 'bg-[var(--color-no-bg)] text-[var(--color-no-fg)]'
                        : 'bg-[var(--color-warn-bg)] text-[var(--color-warn-fg)]',
                  )}
                >
                  {s.eligible === 'TRUE' ? 'Eleggibile' : s.eligible === 'FALSE' ? 'Non eleggibile' : 'Non determinabile'}
                </span>
                {s.anchor.pdf_file && (
                  <a
                    href={pdfHref(s.anchor.pdf_file, s.anchor.page, s.score_name)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 rounded-lg border border-[var(--color-brand)] px-2.5 py-1 text-[11.5px] font-semibold text-[var(--color-brand)] hover:bg-[var(--color-brand-50)] whitespace-nowrap"
                  >
                    Apri nel PDF <ExternalLink size={11} />
                  </a>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Componente principale ────────────────────────────────────────────────────
export function RuleTrace({ ev }: { ev: EvaluateResponse }) {
  const [open, setOpen] = useState(false)
  const trace = ev.coverage_trace ?? []
  const scores = ev.rag_payload.computed_scores ?? {}

  const byPhase = trace.reduce<Record<number, CoverageTraceEntry[]>>((acc, e) => {
    ;(acc[e.phase] ??= []).push(e)
    return acc
  }, {})

  return (
    <>
      <div className="mt-4">
        <button
          onClick={() => setOpen(!open)}
          className="flex w-full items-center justify-between text-left"
        >
          <SectionTitle hint={`${trace.length} regole verificate · click per espandere`}>
            Traccia del motore
          </SectionTitle>
          <span className="mb-2 flex items-center gap-1 rounded-lg border border-[var(--color-line)] px-2.5 py-1 text-[12px] font-semibold text-[var(--color-ink-2)] hover:bg-[var(--color-line-soft)]">
            {open ? <><ChevronUp size={13} /> chiudi</> : <><ChevronDown size={13} /> espandi</>}
          </span>
        </button>

        {open && (
          <div className="card overflow-hidden p-0">
            {/* Header colonne */}
            <div className="flex items-center gap-2 border-b border-[var(--color-line)] bg-[var(--color-canvas)] px-3 py-2 text-[10.5px] font-bold uppercase tracking-wide text-[var(--color-ink-3)]">
              <span className="w-5 flex-none text-center">#</span>
              <span className="w-36 flex-none">Regola</span>
              <span className="hidden w-24 flex-none sm:block">Tipo</span>
              <span className="w-16 flex-none">Valore</span>
              <span className="flex-none">Esito</span>
              <span className="flex-1">Interpretazione</span>
            </div>
            {Object.entries(byPhase)
              .sort(([a], [b]) => Number(a) - Number(b))
              .map(([phase, entries]) => (
                <div key={phase}>
                  <div className="border-b border-[var(--color-line-soft)] bg-[var(--color-canvas)] px-3 py-1.5 text-[10.5px] font-bold uppercase tracking-wider text-[var(--color-ink-2)]">
                    Fase {phase} · {PHASE_LABEL[Number(phase)] ?? `Fase ${phase}`}
                  </div>
                  {entries.map((e, i) => (
                    <TraceRow key={`${e.rule_id}-${i}`} entry={e} />
                  ))}
                </div>
              ))}
          </div>
        )}
      </div>

      <ScoresSection scores={scores} notaEvaluated={ev.nota_evaluated} />
    </>
  )
}
