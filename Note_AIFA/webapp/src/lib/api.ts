import type { CDSSResponse, EvaluateResponse } from './types'

export interface EvalBody {
  note_id: string
  drug_id: string
  patient_data: Record<string, unknown>
  clinician_asserted?: Record<string, unknown>
}

const SCHEMA_VERSION = '3.3' // contratto API; engine interno 3.4.0

export async function evaluate(body: EvalBody): Promise<EvaluateResponse> {
  const res = await fetch('/api/evaluate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      schema_version: SCHEMA_VERSION,
      clinician_asserted: {},
      ...body,
    }),
  })
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new Error(`Rule engine HTTP ${res.status}: ${detail}`)
  }
  return res.json()
}

export async function explain(body: EvalBody): Promise<CDSSResponse> {
  const res = await fetch('/llm/explain', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      schema_version: SCHEMA_VERSION,
      clinician_asserted: {},
      ...body,
    }),
  })
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new Error(`Orchestrator HTTP ${res.status}: ${detail}`)
  }
  return res.json()
}

export interface ServiceHealth {
  engine: boolean
  llm: boolean
}

export async function health(): Promise<ServiceHealth> {
  const ping = async (url: string) => {
    try {
      const r = await fetch(url, { signal: AbortSignal.timeout(3000) })
      return r.ok
    } catch {
      return false
    }
  }
  const [engine, llm] = await Promise.all([
    ping('/api/health'),
    ping('/llm/health'),
  ])
  return { engine, llm }
}
