"""
Integration tests for the Rule Engine FastAPI surface.

Audit gap (Fase 4): the unit-test layer calls `evaluate()` directly. These
tests exercise the full HTTP serialization round-trip — request validation,
schema rejection, drug normalization, and the public response shape.

The lifespan handler loads the on-disk rule corpus, so these tests are fast
(no LLM, no ChromaDB) and are run alongside the regular unit-test suite.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from aifa_rule_engine.api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    """One TestClient per module — TestClient triggers FastAPI lifespan
    which loads the YAML rule corpus once."""
    with TestClient(app) as c:
        yield c


def _payload(
    *,
    note_id: str = "97",
    drug_id: str = "apixaban",
    patient_data: dict | None = None,
    clinician_asserted: dict | None = None,
    schema_version: str = "3.3",
) -> dict:
    return {
        "schema_version": schema_version,
        "note_id": note_id,
        "drug_id": drug_id,
        "patient_data": patient_data or {},
        "clinician_asserted": clinician_asserted or {},
    }


# ── /health ─────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_ok_after_startup(self, client: TestClient) -> None:
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["engine_version"] == "3.4.0"
        assert body["rules_loaded"] >= 30  # at least 30 rules across the 4 Note


# ── /evaluate happy paths ──────────────────────────────────────────────────

class TestEvaluateHappyPaths:

    # Payload sourced from gold-standard case N97-001 (RIMBORSABILE).
    _RIMB_PATIENT = {
        "diagnosi_fanv": True,
        "ecg_confermato": True,
        "valutazione_clinica_eseguita": True,
        "paziente_sesso": "M",
        "paziente_eta": 72,
        "scompenso_cardiaco": True,
        "ipertensione_arteriosa": True,
        "diabete_mellito": True,
        "pregresso_ictus_tia_te": False,
        "vasculopatia": False,
        "protesi_valvolari_meccaniche": False,
        "fa_valvolare": False,
        "vfg_cockroft_gault": 85.0,
        "paziente_peso_kg": 75.0,
        "creatinina_sierica": 0.9,
        "emorragia_maggiore_in_atto": False,
        "diatesi_emorragica_congenita": False,
        "gravidanza": False,
        "ipersensibilita_farmaco": False,
    }

    def test_n97_apixaban_complete_eligible_returns_rimborsabile(
        self, client: TestClient
    ) -> None:
        payload = _payload(
            note_id="97",
            drug_id="apixaban",
            patient_data=self._RIMB_PATIENT,
        )
        r = client.post("/evaluate", json=payload)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["nota_evaluated"] == "97"
        assert body["drug_evaluated"] == "apixaban"
        assert body["reimbursement_decision"] == "RIMBORSABILE"
        assert body["decision_status"] == "FINAL"
        # Structured RagPayload fields (refactor RE-M3) must be populated.
        assert body["rag_payload"]["decision_text"] == "RIMBORSABILE"
        assert body["rag_payload"]["score_eligible"] in {"TRUE", "FALSE", "UNKNOWN"}
        assert isinstance(body["rag_payload"]["activated_rule_ids"], list)

    def test_n97_protesi_meccanica_returns_non_rimborsabile(
        self, client: TestClient
    ) -> None:
        # Same eligible patient but with a hard contraindication asserted.
        patient = dict(self._RIMB_PATIENT)
        patient["fa_valvolare"] = True
        patient["protesi_valvolari_meccaniche"] = True
        payload = _payload(note_id="97", drug_id="apixaban", patient_data=patient)
        r = client.post("/evaluate", json=payload)
        assert r.status_code == 200
        body = r.json()
        assert body["reimbursement_decision"] == "NON_RIMBORSABILE"
        assert body["rag_payload"]["blocking_rule_ids"], (
            "structured field blocking_rule_ids must be populated when denial fires"
        )

    def test_missing_critical_data_returns_non_determinabile(
        self, client: TestClient
    ) -> None:
        payload = _payload(
            note_id="97",
            drug_id="apixaban",
            # diagnosi_fanv NOT provided → SCOPE returns UNKNOWN
            patient_data={},
        )
        r = client.post("/evaluate", json=payload)
        assert r.status_code == 200
        body = r.json()
        assert body["reimbursement_decision"] == "NON_DETERMINABILE"
        # decisive missing fields must be reported
        assert body["missing_fields_coverage"], (
            "missing_fields_coverage must list fields that drove NON_DETERMINABILE"
        )


# ── /evaluate validation failures ──────────────────────────────────────────

class TestEvaluateValidation:

    def test_unknown_note_id_returns_422(self, client: TestClient) -> None:
        r = client.post("/evaluate", json=_payload(note_id="99"))
        assert r.status_code == 422
        assert "note_id" in r.text.lower()

    def test_unsupported_schema_version_returns_422(
        self, client: TestClient
    ) -> None:
        r = client.post("/evaluate", json=_payload(schema_version="9.99"))
        assert r.status_code == 422
        assert "schema_version" in r.text.lower()

    def test_unknown_drug_returns_422(self, client: TestClient) -> None:
        r = client.post(
            "/evaluate",
            json=_payload(drug_id="not_a_real_drug_xyz_123"),
        )
        assert r.status_code == 422

    def test_malformed_json_returns_422(self, client: TestClient) -> None:
        r = client.post(
            "/evaluate",
            content=b"{not valid json",
            headers={"content-type": "application/json"},
        )
        assert r.status_code == 422

    def test_drug_alias_normalization_round_trip(self, client: TestClient) -> None:
        # Brand name should be normalized to the canonical INN.
        payload = _payload(
            drug_id="Eliquis",  # apixaban brand
            patient_data={"diagnosi_fanv": True, "protesi_valvolari_meccaniche": True},
        )
        r = client.post("/evaluate", json=payload)
        assert r.status_code == 200
        body = r.json()
        assert body["drug_evaluated"] == "apixaban"


# ── Determinism contract ───────────────────────────────────────────────────

class TestDeterminism:
    def test_identical_request_yields_identical_decision_and_blocking_ids(
        self, client: TestClient
    ) -> None:
        payload = _payload(
            note_id="97",
            drug_id="apixaban",
            patient_data={"diagnosi_fanv": True, "protesi_valvolari_meccaniche": True},
        )
        out1 = client.post("/evaluate", json=payload).json()
        out2 = client.post("/evaluate", json=payload).json()
        assert out1["reimbursement_decision"] == out2["reimbursement_decision"]
        assert (
            out1["rag_payload"]["blocking_rule_ids"]
            == out2["rag_payload"]["blocking_rule_ids"]
        )
        # Ignore evaluation_timestamp (wall clock) when comparing structures.
        out1.pop("evaluation_timestamp", None)
        out2.pop("evaluation_timestamp", None)
        assert json.dumps(out1, sort_keys=True) == json.dumps(out2, sort_keys=True)


class TestWhitelistInputFieldsV4:
    """Audit V4 2026-05-12: patient_data and clinician_asserted are
    whitelisted against FIELD_REGISTRY to prevent injection of pre-computed
    derived variables (e.g. cha2ds2vasc_range) that would bypass the
    engine's own computation."""

    def test_rejects_extra_keys_in_patient_data(self, client: TestClient) -> None:
        # Use a name guaranteed not to be in FIELD_REGISTRY (derived fields like
        # cha2ds2vasc_range ARE registered and overwritten by
        # compute_derived_variables; the whitelist's role is to block typos and
        # unknown attack-vector keys).
        payload = _payload(
            patient_data={"totally_unknown_key": True},
        )
        r = client.post("/evaluate", json=payload)
        assert r.status_code == 422
        body = r.json()
        assert any(
            "unrecognised keys" in d.get("msg", "")
            and "totally_unknown_key" in d.get("msg", "")
            for d in body["detail"]
        )

    def test_rejects_extra_keys_in_clinician_asserted(
        self, client: TestClient,
    ) -> None:
        payload = _payload()
        payload["clinician_asserted"] = {"made_up_flag": True}
        r = client.post("/evaluate", json=payload)
        assert r.status_code == 422
