import { useEffect, useMemo, useState } from 'react'
import { Topbar } from './components/Topbar'
import { Sidebar } from './components/Sidebar'
import { PatientHeader } from './components/PatientHeader'
import { Verdict } from './components/Verdict'
import { Reasons } from './components/Reasons'
import { RuleTrace } from './components/RuleTrace'
import { WhatIf } from './components/WhatIf'
import { AiPanel } from './components/AiPanel'
import { EvaluateCta } from './components/EvaluateCta'
import { bakedEvaluation, getCase, HIGHLIGHT_IDS } from './lib/data'
import { evaluate, explain, health, type ServiceHealth } from './lib/api'
import type { CDSSResponse, EvalStatus, EvaluateResponse, ExplainStatus } from './lib/types'

type Value = boolean | number | string | null

const FIRST_ID = HIGHLIGHT_IDS[0] ?? 'N01-002'

export default function App() {
  const [selectedId, setSelectedId] = useState(FIRST_ID)
  const [patientData, setPatientData] = useState<Record<string, Value>>(
    () => ({ ...getCase(FIRST_ID)!.patient_data }),
  )
  const [ev, setEv] = useState<EvaluateResponse | null>(null)
  const [cdss, setCdss] = useState<CDSSResponse | null>(null)
  const [evalStatus, setEvalStatus] = useState<EvalStatus>('idle')
  const [explainStatus, setExplainStatus] = useState<ExplainStatus>('idle')
  const [svc, setSvc] = useState<ServiceHealth>({ engine: false, llm: false })

  const selectedCase = getCase(selectedId)!
  const baseData = selectedCase.patient_data as Record<string, Value>

  useEffect(() => {
    let alive = true
    const run = () => health().then((h) => alive && setSvc(h))
    run()
    const t = setInterval(run, 15000)
    return () => {
      alive = false
      clearInterval(t)
    }
  }, [])

  const dirty = useMemo(
    () => JSON.stringify(baseData) !== JSON.stringify(patientData),
    [baseData, patientData],
  )

  // Re-valuta live al cambio dei flag (solo se già valutato e motore online)
  useEffect(() => {
    if (evalStatus !== 'done' || !svc.engine || !dirty) return
    let cancelled = false
    evaluate({
      note_id: selectedCase.nota_id,
      drug_id: selectedCase.drug_id,
      patient_data: patientData,
      clinician_asserted: selectedCase.clinician_asserted,
    })
      .then((r) => !cancelled && setEv(r))
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [patientData, dirty, svc.engine, evalStatus, selectedCase])

  async function handleEvaluate() {
    setEvalStatus('evaluating')
    try {
      let result: EvaluateResponse
      if (svc.engine) {
        result = await evaluate({
          note_id: selectedCase.nota_id,
          drug_id: selectedCase.drug_id,
          patient_data: patientData,
          clinician_asserted: selectedCase.clinician_asserted,
        })
      } else {
        const baked = bakedEvaluation(selectedId)
        if (!baked) throw new Error('No baked evaluation for ' + selectedId)
        result = baked
      }
      setEv(result)
      setEvalStatus('done')

      // Avvia la spiegazione LLM in parallelo se disponibile
      if (svc.llm) {
        setExplainStatus('loading')
        explain({
          note_id: selectedCase.nota_id,
          drug_id: selectedCase.drug_id,
          patient_data: patientData,
          clinician_asserted: selectedCase.clinician_asserted,
        })
          .then((r) => {
            setCdss(r)
            setExplainStatus('done')
          })
          .catch(() => setExplainStatus('error'))
      }
    } catch {
      setEvalStatus('error')
    }
  }

  function selectPatient(id: string) {
    setSelectedId(id)
    setPatientData({ ...getCase(id)!.patient_data })
    setEv(null)
    setCdss(null)
    setEvalStatus('idle')
    setExplainStatus('idle')
  }

  function changeFlag(key: string, value: Value) {
    setPatientData((d) => ({ ...d, [key]: value }))
  }

  function resetCase() {
    setPatientData({ ...baseData })
  }

  const showResults = evalStatus === 'done' && ev !== null

  return (
    <div className="mx-auto max-w-[1180px] px-5 py-5">
      <Topbar engineOk={svc.engine} llmOk={svc.llm} />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[320px_minmax(0,1fr)]">
        <Sidebar activeId={selectedId} onSelect={selectPatient} />

        <main>
          <PatientHeader c={selectedCase} />

          {(evalStatus === 'idle' || evalStatus === 'evaluating') && (
            <EvaluateCta
              onEvaluate={handleEvaluate}
              evaluating={evalStatus === 'evaluating'}
              engineOffline={!svc.engine}
            />
          )}

          {evalStatus === 'error' && (
            <div className="card mt-4 p-5 text-center text-[13.5px] text-[var(--color-no-fg)]">
              Errore durante la valutazione. Riprova o verifica che il motore sia online.
            </div>
          )}

          {showResults && (
            <>
              <div className="mt-4">
                <Verdict ev={ev} />
              </div>
              <Reasons ev={ev} />
              <RuleTrace ev={ev} />
              <WhatIf
                data={patientData}
                baseData={baseData}
                onChange={changeFlag}
                onReset={resetCase}
                live={svc.engine}
              />
              <AiPanel status={explainStatus} cdss={cdss} />
            </>
          )}
        </main>
      </div>
    </div>
  )
}
