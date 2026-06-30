# Limitazioni note — AIFA CDSS

Questo documento elenca apertamente le scelte di scope e i limiti tecnici
del prototipo. Tutti i punti qui sotto sono **intenzionali** e dichiarati
sia in fase di progettazione (con il relatore) sia nel manoscritto di tesi.

## Scope del progetto

Il brief concordato con il relatore copre **3 Note AIFA primarie**:

| Nota | Argomento                              | Stato      |
|------|----------------------------------------|------------|
| 97   | Anticoagulanti orali in FANV           | Primaria   |
| 1    | Gastroprotettori (PPI, misoprostolo)   | Primaria   |
| 13   | Ipolipemizzanti (statine, ezetimibe…)  | Primaria   |
| 66   | FANS (antinfiammatori non steroidei)   | Bonus      |

La Nota 66 è inclusa per copertura aggiuntiva ma non era richiesta dallo
scope iniziale. Le altre Note AIFA non rientrano nel progetto triennale —
estensioni future potrebbero seguire lo stesso pattern (rules.yaml +
catalog + cases.json + PDF anchors).

## Limitazioni dichiarate

### 1. Allegato 3 della Nota 97 (gestione perioperatoria) — NOT IMPLEMENTED

`aifa_rule_engine/rules/nota_97/_catalog.yaml` registra l'Allegato 3 come
`not_implemented_in_scope: true`. La gestione perioperatoria di DOAC
(sospensione/ripresa pre- e post-intervento) richiederebbe un set di
variabili cliniche aggiuntive (`procedura_chirurgica_prevista`,
`livello_rischio_emorragico_intervento`, `data_intervento_programmata`)
e un set di regole `GUIDANCE_WARN` dedicate. È esplicitamente fuori scope.
I chunk RAG dell'Allegato 3 restano disponibili per consultazione ma non
attivano regole.

### 2. Modello LLM quantizzato (Llama 3.1 8B Q4_K_M)

Il backend di default è Ollama con **Llama 3.1 8B Q4_K_M** (4.9 GB VRAM su
RTX 3060). La quantizzazione Q4 è un compromesso hardware: modelli
frontier di fascia superiore produrrebbero spiegazioni di qualità
superiore ma sono fuori scope (vincolo costo/locale) e non cambierebbero
le decisioni — quelle sono **deterministiche** e provengono dal rule
engine. Il backend OpenAI (`OPENAI_API_KEY`) è supportato per replica con
modello frontier opzionale.

### 3. M3 (NLI faithfulness) — lower-bound conservativo

`MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` è un modello NLI multilingua
generico, non fine-tuned su normativa italiana. I valori di entailment
prodotti sono interpretati come **stima conservativa lower-bound** della
faithfulness. Il proxy operativo primario è `faithfulness_verbatim`
(3-gram coverage); M3 è secondario nel composite `EvidenceSupport`
(refactor 5.3). Caveat ribadito nel `OVERNIGHT_SUMMARY_v2.md`.

### 4. RAGAS su subset stratificato n=20

La full RAGAS run sui 122 casi richiede ~10 h con LLM Q4_K_M come judge.
Il default operativo (`Makefile:eval-ragas-subset`, `RAGAS_SUBSET=20`) è
una **scelta metodologica dichiarata**, non un workaround: copre tutte le
4 Note e tutte le classi di decisione, ed è sufficiente per validare il
segnale di faithfulness/relevancy parallelamente alle metriche
deterministiche (M1, verbatim 3-gram, M3 NLI). Il target full è
disponibile come `make eval-ragas`.

### 5. Test set sintetico (122 casi)

Il gold standard è composto da **scenari clinici sintetici** scritti
dall'autore con scope coverage:
RIMBORSABILE 69 (56.6%), NON_RIMBORSABILE 39 (32%), NON_DETERMINABILE 9
(7.4%), ROUTED 5 (4.1%). Non sono casi clinici reali (GDPR + brief
relatore). Il sistema NON è validato su dataset clinico reale.

### 6. `requires_passed` dichiarativo, non enforced a runtime

Il campo `BaseRule.requires_passed` (Pydantic) è ammesso nello schema
YAML ma **NON** viene enforcato dall'evaluator. La pipeline 10-fasi
fail-fast garantisce l'ordering implicito tramite `evaluation_order`/
`rule_type`. `rule_loader` Phase S3 emette WARNING a startup se YAML
contiene `requires_passed` non vuoti. Promozione a enforcement strict è
"future work".

### 7. N13_EXCEPT_002 non drug-aware

L'eccezione N13_EXCEPT_002 (categoria_rischio "molto_alto") in N13
attualmente non distingue per farmaco. Documentato come future work.

### 8. Audit trail in-memory (non persistente)

L'audit trail è generato per request e ritornato nella response. Non è
persistito su SQLite/database. Promozione a audit-store persistente è
future work, soprattutto rilevante per trial clinici.

### 9. Cross-encoder reranker italiano `nickprock/cross-encoder-italian-bert-stsb`

Il default (`retriever.py:_DEFAULT_RERANKER_MODEL`) è italian-specific
ma fine-tuned su STSB (similarità semantica) non su domain-specific
AIFA/clinical. Per il triennale è il miglior trade-off tra performance e
disponibilità open. Modelli fine-tuned su clinico italiano non sono
pubblicamente disponibili al 2026-Q2.

**Recall@5 osservato = 0.632** (cleanroom 2026-05-05). Lo Stage A
anchor-guided (78.54% del retrieval) è 100% precision per costruzione
ma può mancare quando l'anchor della regola non coincide con la pagina
del chunk gold; lo Stage B semantic+rerank recupera il restante 21.46%
ma è limitato dalla domain-specificity del cross-encoder STSB. Migliorare
ulteriormente Recall@5 oltre 0.70 richiederebbe un reranker fine-tuned
sul corpus AIFA — fuori scope triennale.

### 10. Eval umana clinica esterna — NON eseguita

Una valutazione qualitativa cieca da farmacista o MMG su un sub-campione
delle spiegazioni non è inclusa nello scope triennale. Il manoscritto
discute la qualità delle spiegazioni esclusivamente tramite metriche
oggettive (M1..M7 + RAGAS). Promozione a human eval è future work.

## Cosa NON è dichiarato come limitazione (perché funziona)

Per chiarezza: i seguenti aspetti **non** sono limiti, sono garanzie del
sistema:

- **Determinismo della decisione**: il rule engine produce sempre la
  stessa decisione per gli stessi input. Verificato da `idempotency.py`
  (20 casi × 3 run = bit-exact).
- **Tracciabilità verbatim**: ogni `--- PROVA NORMATIVA ---` riporta
  `(pdf, page, line_range, char_range, sha256)` ed è verificabile da
  uno script terzo che rilegge il PDF.
- **Faithfulness 3-gram**: `faithfulness_verbatim` ≈ 0.99 sul corpus.
- **Anti-allucinazione**: la decisione dell'LLM è iniettata
  deterministicamente nel prompt come §2 "DECISIONE DETERMINISTICA — NON
  CONTRADDIRE", e la sezione `5. FONTI` è riscritta post-generation
  dall'orchestrator con i metadati ChromaDB (no LLM-prose).

---

Per dettagli implementativi sui singoli punti, vedere:
- `aifa_rule_engine/README.md`
- `REFACTOR_V2_SUMMARY.md`
- `audit/REPORT_FINALE.md`
