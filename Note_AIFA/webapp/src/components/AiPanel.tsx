import { AlertTriangle, BookOpen, CheckCircle, ExternalLink, FileText, Loader2, Sparkles, XCircle } from 'lucide-react'
import { cn } from '@/lib/cn'
import { ruleDescription, ruleType } from '@/lib/data'
import { pdfHref } from '@/lib/pdf'
import { SectionTitle } from './SectionTitle'
import type { CDSSResponse, ExplainStatus, NormativeEvidence } from '@/lib/types'

// ── Narrazione del modello — sezioni pulite ─────────────────────────────────
// L'LLM produce 5 sezioni numerate (DECISIONE/MOTIVAZIONE/RACCOMANDAZIONI/
// DATI MANCANTI/FONTI). Mostriamo solo 1-4 e rimuoviamo il rumore: la sezione
// "FONTI" (dump sha/righe/char) e i riferimenti orfani "FONTE n" (le fonti vere
// stanno nelle card "Su cosa si basa" sotto).
const SECTION_TITLE: Record<string, string> = {
  DECISIONE: 'Decisione',
  MOTIVAZIONE: 'Motivazione',
  RACCOMANDAZIONI: 'Raccomandazioni',
  'DATI MANCANTI': 'Dati mancanti',
}

function cleanProse(s: string): string {
  return s
    // riferimenti orfani "FONTE n" (varie forme)
    .replace(/\(\s*fonte\s*\d+\s*\)/gi, '')
    .replace(/,?\s*come (?:indicato|riportato|specificato|descritto|mostrato)(?:\s+(?:nella|nelle|nel|in|dalla|dal))?\s+fonte\s*\d+/gi, '')
    .replace(/\b(?:secondo|nella|nelle|nel|in|dalla|dal|della|del)\s+fonte\s*\d+/gi, '')
    .replace(/\bfonte\s*\d+/gi, '')
    // riferimenti inline ai PDF "(Nota_66.pdf p.4)" / "(: nota-97.pdf, p. 1)"
    .replace(/\(\s*:?\s*[^)]*\.pdf[^)]*\)/gi, '')
    // enum grezzi → italiano leggibile (NON_ prima di RIMBORSABILE)
    .replace(/\bNON_RIMBORSABILE\b/g, 'non rimborsabile')
    .replace(/\bNON_DETERMINABILE\b/g, 'non determinabile')
    .replace(/\bRIMBORSABILE\b/g, 'rimborsabile')
    // pulizia spaziatura/punteggiatura residua
    .replace(/[ \t]{2,}/g, ' ')
    .replace(/[ \t]+([,.;:])/g, '$1')
    .replace(/,\s*,/g, ',')
    .replace(/\(\s*\)/g, '')
    .replace(/[ \t]+\./g, '.')
    .trim()
}

function parseNarration(text: string): { title: string; body: string }[] {
  const lines = text.split('\n')
  const out: { key: string; title: string; body: string }[] = []
  let cur: { key: string; title: string; body: string } | null = null
  for (const line of lines) {
    const m = line.match(/^\s*\d+\.\s+([A-ZÀ-Ù][A-ZÀ-Ù\s]+?)\s*$/)
    if (m) {
      if (cur) out.push(cur)
      const raw = m[1].trim()
      cur = { key: raw, title: SECTION_TITLE[raw] ?? raw.charAt(0) + raw.slice(1).toLowerCase(), body: '' }
    } else if (cur) {
      cur.body += line + '\n'
    }
  }
  if (cur) out.push(cur)
  return out.filter((s) => !/FONTI/i.test(s.key)).map(({ title, body }) => ({ title, body }))
}

function Paragraphs({ text }: { text: string }) {
  const paras = text
    .split(/\n\n+/)
    .map((p) => p.replace(/\n/g, ' ').replace(/^[\s,;:]+/, '').replace(/[ \t]{2,}/g, ' ').trim())
    .filter(Boolean)
  return (
    <div className="space-y-2 text-[13.5px] leading-relaxed text-[var(--color-ink)]">
      {paras.map((para, i) => (
        <p key={i}>
          {para.split(/(\*\*[^*]+\*\*)/).map((part, j) =>
            part.startsWith('**') && part.endsWith('**') ? (
              <strong key={j}>{part.slice(2, -2)}</strong>
            ) : (
              <span key={j}>{part}</span>
            ),
          )}
        </p>
      ))}
    </div>
  )
}

function Narration({ text }: { text: string }) {
  const sections = parseNarration(text)
  if (!sections.length) return <Paragraphs text={cleanProse(text)} />
  return (
    <div className="space-y-3.5">
      {sections.map((s, i) => {
        const body = cleanProse(s.body)
        if (!body) return null
        return (
          <div key={i}>
            <p className="mb-1 text-[11px] font-bold uppercase tracking-wide text-[var(--color-ink-3)]">
              {s.title}
            </p>
            <Paragraphs text={body} />
          </div>
        )
      })}
    </div>
  )
}

function ValidationPanel({ v }: { v: CDSSResponse['validation'] }) {
  if (!v) return null
  const ungrounded = v.ungrounded_citations ?? []
  const checks = [
    { ok: v.decision_consistent, label: 'Decisione coerente con il motore' },
    { ok: !v.decision_contradicted, label: 'Nessuna contraddizione rilevata' },
    { ok: v.citation_complete, label: 'Tutte le citazioni presenti' },
    { ok: v.justification_complete, label: 'Giustificazione completa' },
    { ok: v.suspected_hallucinations.length === 0, label: 'Nessuna allucinazione sospetta' },
    { ok: ungrounded.length === 0, label: 'Tutte le citazioni ancorate alle fonti recuperate' },
  ]
  const allOk = checks.every((c) => c.ok)
  return (
    <div
      className={cn(
        'mt-4 rounded-xl border p-3',
        allOk
          ? 'border-[var(--color-ok-br)] bg-[var(--color-ok-bg)]'
          : 'border-[var(--color-warn-br)] bg-[var(--color-warn-bg)]',
      )}
    >
      <p className={cn('mb-2 text-[12px] font-bold uppercase tracking-wide', allOk ? 'text-[var(--color-ok-fg)]' : 'text-[var(--color-warn-fg)]')}>
        Verifica qualità output
      </p>
      <div className="space-y-1">
        {checks.map(({ ok, label }) => (
          <div key={label} className="flex items-center gap-2 text-[12.5px]">
            {ok
              ? <CheckCircle size={13} className="flex-none text-[var(--color-ok-fg)]" />
              : <XCircle size={13} className="flex-none text-[var(--color-no-fg)]" />}
            <span className={ok ? 'text-[var(--color-ok-fg)]' : 'text-[var(--color-no-fg)]'}>{label}</span>
          </div>
        ))}
        {v.suspected_hallucinations.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {v.suspected_hallucinations.map((h) => (
              <span key={h} className="rounded-full bg-white px-2 py-0.5 text-[11px] text-[var(--color-no-fg)]">{h}</span>
            ))}
          </div>
        )}
        {ungrounded.length > 0 && (
          <div className="mt-2">
            <p className="mb-1 text-[11px] font-semibold text-[var(--color-warn-fg)]">
              Citazioni non riscontrate nelle fonti recuperate (segnalate, non rimosse):
            </p>
            <div className="flex flex-wrap gap-1">
              {ungrounded.map((h) => (
                <span key={h} className="rounded-full bg-white px-2 py-0.5 text-[11px] text-[var(--color-warn-fg)]">{h}</span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Fonti — ogni criterio della Nota + perché si attinge a quel passaggio ────
type Tone = 'block' | 'pass' | 'neutral'

// Ricostruisce, dal tipo di regola e dal ruolo della fonte, un'etichetta umana
// e un "tono". Il campo `reason` del backend è valorizzato solo per la regola
// che blocca, quindi la spiegazione del "perché" viene dal catalogo regole.
function sourceFraming(rType: string, role: string): { label: string; tone: Tone } {
  const t = (rType || '').toUpperCase()
  const blocking = role === 'blocking'
  if (t === 'SCOPE')
    return blocking ? { label: 'Ambito non applicabile', tone: 'block' } : { label: 'Ambito di applicabilità', tone: 'pass' }
  if (t.startsWith('EXCL'))
    return blocking ? { label: 'Controindicazione presente', tone: 'block' } : { label: 'Controindicazione esclusa', tone: 'pass' }
  if (t === 'INCLUSION' || t === 'INCLHARD')
    return blocking ? { label: 'Criterio di inclusione non soddisfatto', tone: 'block' } : { label: 'Criterio di inclusione soddisfatto', tone: 'pass' }
  if (t === 'PATHWAY')
    return blocking ? { label: 'Percorso non applicabile', tone: 'block' } : { label: 'Soglia di rimborsabilità', tone: 'pass' }
  if (t === 'EXCEPTION') return { label: 'Eccezione applicabile', tone: 'pass' }
  if (t === 'PREFERENCE') return { label: 'Preferenza terapeutica', tone: 'neutral' }
  if (t.startsWith('DOSE')) return { label: 'Posologia', tone: 'neutral' }
  if (t === 'WARNING') return { label: 'Avvertenza', tone: 'neutral' }
  if (t === 'SCORE') return { label: 'Punteggio clinico', tone: 'neutral' }
  return blocking ? { label: 'Motivo del blocco', tone: 'block' } : { label: 'Criterio verificato', tone: 'neutral' }
}

const TONE_BORDER: Record<Tone, string> = {
  block: 'border-l-[var(--color-no)]',
  pass: 'border-l-[var(--color-ok)]',
  neutral: 'border-l-[var(--color-brand)]',
}

function SourceCard({ e }: { e: NormativeEvidence }) {
  const rType = e.rule_type || ruleType(e.rule_id)
  const { label, tone } = sourceFraming(rType, e.role)
  const why = ruleDescription(e.rule_id)
  const ref = [e.pdf_file, e.page ? `pag. ${e.page}` : null, e.section].filter(Boolean).join(' · ')
  return (
    <div className={cn('rounded-xl border border-l-4 bg-white p-3.5', TONE_BORDER[tone])}>
      <div className="mb-1.5 flex flex-wrap items-center gap-2">
        {e.role === 'blocking' && (
          <span className="rounded-full bg-[var(--color-no-bg)] px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-[var(--color-no-fg)]">
            Motivo del blocco
          </span>
        )}
        <span className="text-[13px] font-semibold text-[var(--color-ink)]">{label}</span>
        <span className="ml-auto flex items-center gap-1 text-[11.5px] font-semibold">
          {tone === 'block' ? (
            <>
              <XCircle size={13} className="text-[var(--color-no-fg)]" />
              <span className="text-[var(--color-no-fg)]">blocca</span>
            </>
          ) : tone === 'pass' ? (
            <>
              <CheckCircle size={13} className="text-[var(--color-ok-fg)]" />
              <span className="text-[var(--color-ok-fg)]">verificato</span>
            </>
          ) : null}
        </span>
      </div>
      {why && <p className="mb-2 text-[12.5px] leading-snug text-[var(--color-ink-2)]">{why}</p>}
      {e.evidence_missing ? (
        <p className="mb-2 text-[12px] italic text-[var(--color-warn-fg)]">
          Testo normativo non recuperato dall'archivio.
        </p>
      ) : e.exact_text ? (
        <blockquote className="mb-2 rounded-lg bg-[var(--color-canvas)] px-3 py-2 text-[12.5px] italic leading-relaxed text-[var(--color-ink)]">
          “{e.exact_text.slice(0, 360).trim()}{e.exact_text.length > 360 ? '…' : ''}”
        </blockquote>
      ) : null}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 text-[11px] text-[var(--color-ink-3)]">
          <FileText size={11} />
          <span>{ref}</span>
        </div>
        {e.pdf_file && e.page && (
          <a
            href={pdfHref(e.pdf_file, e.page, e.exact_text)}
            target="_blank"
            rel="noopener noreferrer"
            className="flex flex-none items-center gap-1 rounded-lg border border-[var(--color-brand)] px-2.5 py-1 text-[11.5px] font-semibold text-[var(--color-brand)] hover:bg-[var(--color-brand-50)]"
          >
            Apri nel PDF <ExternalLink size={11} />
          </a>
        )}
      </div>
    </div>
  )
}

function SourcesSection({ items }: { items: NormativeEvidence[] }) {
  if (!items.length) return null
  // La fonte decisiva (blocking) per prima.
  const sorted = [...items].sort(
    (a, b) => (a.role === 'blocking' ? 0 : 1) - (b.role === 'blocking' ? 0 : 1),
  )
  return (
    <div className="mt-5">
      <p className="text-[12px] font-bold uppercase tracking-wide text-[var(--color-ink-2)]">
        Su cosa si basa
      </p>
      <p className="mb-2.5 mt-0.5 text-[12px] leading-snug text-[var(--color-ink-3)]">
        I criteri della Nota AIFA verificati dal motore, ciascuno con il passaggio normativo corrispondente.
        Clicca «Apri nel PDF» per leggere il testo originale alla pagina esatta.
      </p>
      <div className="space-y-2">
        {sorted.map((e) => (
          <SourceCard key={e.evidence_id} e={e} />
        ))}
      </div>
    </div>
  )
}

function MetaLine({ cdss }: { cdss: CDSSResponse }) {
  return (
    <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-[var(--color-line-soft)] pt-3 text-[11px] text-[var(--color-ink-3)]">
      <span className="flex items-center gap-1">
        <Sparkles size={12} />
        {cdss.llm_model}
      </span>
      <span className="flex items-center gap-1">
        <BookOpen size={12} />
        {cdss.normative_evidence.length} fonti · {cdss.retrieval_strategy}
      </span>
      {cdss.prompt_tokens > 0 && <span>{cdss.prompt_tokens + cdss.completion_tokens} token</span>}
    </div>
  )
}


export function AiPanel({
  status,
  cdss,
}: {
  status: ExplainStatus
  cdss: CDSSResponse | null
}) {
  return (
    <>
      <SectionTitle hint="narrazione clinica generata dal pipeline RAG + LLM">Spiegazione AI</SectionTitle>
      <div className="card p-4">
        {status === 'idle' && (
          <div className="flex items-start gap-3">
            <div className="flex h-9 w-9 flex-none items-center justify-center rounded-lg bg-[var(--color-brand-50)] text-[var(--color-brand)]">
              <Sparkles size={18} />
            </div>
            <p className="text-[13.5px] leading-relaxed text-[var(--color-ink-2)]">
              La spiegazione discorsiva apparirà qui dopo la valutazione, se il servizio RAG + LLM è online.
            </p>
          </div>
        )}

        {status === 'loading' && (
          <div className="flex items-start gap-3">
            <div className="flex h-9 w-9 flex-none items-center justify-center rounded-lg bg-[var(--color-brand-50)] text-[var(--color-brand)]">
              <Loader2 size={18} className="animate-spin" />
            </div>
            <div>
              <p className="text-[14px] font-semibold text-[var(--color-ink)]">
                Generazione in corso…
              </p>
              <p className="mt-1 text-[13px] text-[var(--color-ink-2)]">
                RAG → retrieval documenti · LLM → narrazione clinica in italiano. Operazione tipicamente 30–90 secondi.
              </p>
            </div>
          </div>
        )}

        {status === 'error' && (
          <div className="flex items-start gap-3">
            <div className="flex h-9 w-9 flex-none items-center justify-center rounded-lg bg-[var(--color-no-bg)] text-[var(--color-no-fg)]">
              <AlertTriangle size={18} />
            </div>
            <div>
              <p className="text-[14px] font-semibold text-[var(--color-ink)]">Errore nella generazione</p>
              <p className="mt-1 text-[13px] text-[var(--color-ink-2)]">
                Il servizio RAG + LLM non ha risposto. Il verdetto deterministico del motore a regole è comunque valido.
              </p>
            </div>
          </div>
        )}

        {status === 'done' && cdss && (
          <>
            {cdss.explanation_redacted && (
              <div className="mb-4 flex items-center gap-2 rounded-lg border border-[var(--color-warn-br)] bg-[var(--color-warn-bg)] px-3 py-2 text-[12.5px] text-[var(--color-warn-fg)]">
                <AlertTriangle size={14} />
                Spiegazione redatta: il testo originale è stato sostituito con un template di sicurezza perché contraddiceva la decisione del motore.
              </div>
            )}

            <Narration text={cdss.generated_explanation} />
            <SourcesSection items={cdss.normative_evidence} />
            <ValidationPanel v={cdss.validation} />
            <MetaLine cdss={cdss} />
          </>
        )}
      </div>
    </>
  )
}
