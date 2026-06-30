import { Loader2, Play, ShieldAlert, Stethoscope } from 'lucide-react'

export function EvaluateCta({
  onEvaluate,
  evaluating,
  engineOffline,
}: {
  onEvaluate: () => void
  evaluating: boolean
  engineOffline: boolean
}) {
  return (
    <div className="card mt-4 flex flex-col items-center gap-5 py-14 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-[var(--color-brand-50)] text-[var(--color-brand)]">
        <Stethoscope size={30} strokeWidth={2} />
      </div>
      <div>
        <h3 className="text-[18px] font-bold text-[var(--color-ink)]">
          Avvia la valutazione
        </h3>
        <p className="mt-1 max-w-sm text-[13.5px] leading-relaxed text-[var(--color-ink-2)]">
          Il motore a regole verificherà i criteri della Nota AIFA per questo paziente e farmaco.
        </p>
        {engineOffline && (
          <div className="mt-3 flex items-center justify-center gap-1.5 text-[12.5px] text-[var(--color-warn-fg)]">
            <ShieldAlert size={14} />
            Motore offline · verrà usata la valutazione pre-calcolata
          </div>
        )}
      </div>
      <button
        onClick={onEvaluate}
        disabled={evaluating}
        className="flex items-center gap-2.5 rounded-xl bg-[var(--color-brand)] px-7 py-3 text-[15px] font-bold text-white shadow-sm transition hover:bg-[var(--color-brand-600)] disabled:opacity-60"
      >
        {evaluating ? (
          <>
            <Loader2 size={18} className="animate-spin" />
            Elaborazione in corso…
          </>
        ) : (
          <>
            <Play size={18} strokeWidth={2.5} />
            Valuta prescrizione
          </>
        )}
      </button>
    </div>
  )
}
