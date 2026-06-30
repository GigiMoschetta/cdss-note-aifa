export type Decision =
  | 'RIMBORSABILE'
  | 'NON_RIMBORSABILE'
  | 'NON_DETERMINABILE'
  | 'ROUTED'

export type EvalStatus = 'idle' | 'evaluating' | 'done' | 'error'
export type ExplainStatus = 'idle' | 'loading' | 'done' | 'error'

export interface FlagMeta {
  label: string
  icon: string
  severity: 'info' | 'warn' | 'danger'
  kind: 'bool' | 'number' | 'string'
  unit: string
}

export interface RuleMeta {
  description_it: string
  rule_type: string
}

export interface PatientVanity {
  occupation?: string
  allergies?: string
  other_comorbidities?: string[]
  fiscal_code?: string
  phone?: string
  city?: string
}

export interface Patient extends PatientVanity {
  full_name: string
  first_name: string
  last_name: string
  initials: string
  avatar_url: string
  sex: string | null
  age: number | null
}

export interface GoldCase {
  case_id: string
  nota_id: string
  drug_id: string
  drug_class_label: string
  drug_icon: string
  drug_severity: string
  category_human: string
  description: string
  complexity: number
  expected_decision: Decision | string
  expected_status: string
  expected_route_to: string | null
  patient: Patient
  patient_data: Record<string, boolean | number | string | null>
  clinician_asserted: Record<string, unknown>
}

export interface CasesPayload {
  highlight_case_ids: string[]
  cases: GoldCase[]
  flag_catalog: Record<string, FlagMeta>
  rule_catalog: Record<string, RuleMeta>
}

// ---- Risposta /evaluate del rule engine ----
export interface Anchor {
  pdf_file: string
  page: number | string
  section: string
  excerpt: string
}

export interface BlockingRule {
  rule_id: string
  rule_type?: string
  truth_value?: string
  rule_evaluated_as?: string
  reason?: string
  anchor: Anchor
}

export interface PassedRule {
  rule_id: string
  anchor: Anchor
}

export interface UnknownRule {
  rule_id: string
  anchor?: Anchor
  missing_fields?: string[]
}

export interface ScoreRangeResult {
  score_name: string
  min_score: number
  max_score: number
  threshold: number | null
  eligible: 'TRUE' | 'FALSE' | 'UNKNOWN'
  missing_components: string[]
  anchor: Anchor
}

export interface RagPayload {
  blocking_rules: BlockingRule[]
  passed_rules: PassedRule[]
  unknown_rules: UnknownRule[]
  missing_fields: string[]
  clinical_context_summary?: string
  activated_rule_ids: string[]
  blocking_rule_ids: string[]
  computed_scores: Record<string, ScoreRangeResult>
  score_eligible?: string
  decision_text?: string
}

export interface CoverageTraceEntry {
  rule_id: string
  rule_type: string
  truth_value: 'TRUE' | 'FALSE' | 'UNKNOWN'
  outcome: string
  phase: number
  facts_used: Record<string, unknown>
  anchor: Anchor
  missing_fields: string[]
}

export interface EvaluateResponse {
  schema_version: string
  decision_status: string
  reimbursement_decision: Decision
  nota_evaluated: string
  drug_evaluated: string
  route_to: string | null
  route_reason: string | null
  clinical_flags: unknown[]
  missing_fields_coverage: string[]
  missing_fields_guidance: string[]
  rag_payload: RagPayload
  coverage_trace: CoverageTraceEntry[]
  engine_version?: string
  evaluation_timestamp?: string
}

// ---- CDSSResponse da /explain (orchestratore RAG + LLM) ----
export interface NormativeEvidence {
  evidence_id: string
  rule_id: string
  rule_type: string
  role: string
  reason: string
  pdf_file: string
  page: number
  section: string
  exact_text: string
  evidence_missing: boolean
}

export interface ValidationFlags {
  decision_consistent: boolean
  decision_contradicted: boolean
  citation_complete: boolean
  missing_citations: string[]
  suspected_hallucinations: string[]
  justification_complete: boolean
  missing_justification_rules: string[]
  missing_supporting_citations?: string[]
  ungrounded_citations?: string[]
}

export interface RetrievedChunk {
  chunk_id: string
  text: string
  pdf_file: string
  nota_id: string
  page: number
  section: string
  score: number
  retrieval_stage: string
}

export interface CDSSResponse {
  evaluation_result: EvaluateResponse
  retrieved_chunks: RetrievedChunk[]
  retrieval_strategy: string
  generated_explanation: string
  explanation_redacted: boolean
  llm_model: string
  prompt_tokens: number
  completion_tokens: number
  generation_timestamp: string
  validation: ValidationFlags | null
  normative_evidence: NormativeEvidence[]
}
