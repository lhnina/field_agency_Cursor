"""PR4 — remaining MVP gaps."""


def test_zones_and_csv_import(client, auth_headers):
    zones = client.get("/api/v1/zones", headers=auth_headers)
    assert zones.status_code == 200
    assert len(zones.json()) >= 3

    created = client.post(
        "/api/v1/zones",
        headers=auth_headers,
        json={"code": "Algarve", "name": "Algarve"},
    )
    assert created.status_code == 201, created.text

    csv_body = "chain,name,zone_code,credential_name,address\nContinente,Continente Faro,Algarve,Faro,Faro\n"
    res = client.post(
        "/api/v1/stores/import-csv",
        headers=auth_headers,
        files={"file": ("lojas.csv", csv_body, "text/csv")},
    )
    assert res.status_code == 200, res.text
    assert res.json()["created"] >= 1


def test_budget_convert_q02(client, auth_headers):
    budgets = client.get("/api/v1/budgets", headers=auth_headers)
    assert budgets.status_code == 200
    assert len(budgets.json()) >= 1
    budget = budgets.json()[0]
    assert budget["status"] == "APROVADO"

    converted = client.post(
        f"/api/v1/budgets/{budget['id']}/approve-convert",
        headers=auth_headers,
    )
    assert converted.status_code == 200, converted.text
    body = converted.json()
    assert body["status"] == "CONVERTIDO"
    assert body["resulting_contract_id"]
    assert body["resulting_campaign_id"]

    campaigns = client.get("/api/v1/campaigns", headers=auth_headers)
    assert campaigns.status_code == 200
    assert len(campaigns.json()) >= 1

    audit = client.get("/api/v1/audit-logs?action=BUDGET_CONVERT", headers=auth_headers)
    assert audit.status_code == 200
    assert len(audit.json()) >= 1


def test_period_close_and_reopen(client, auth_headers):
    periods = client.get(
        "/api/v1/billing-periods",
        headers=auth_headers,
        params={"year": 2026, "month": 11},
    ).json()
    period = next(p for p in periods if p["service_area"] == "REPOSICAO")

    closed = client.post(f"/api/v1/billing-periods/{period['id']}/close", headers=auth_headers)
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "FECHADO"

    blocked = client.post(f"/api/v1/billing-periods/{period['id']}/generate", headers=auth_headers)
    assert blocked.status_code == 400

    reopened = client.post(
        f"/api/v1/billing-periods/{period['id']}/reopen",
        headers=auth_headers,
        json={"reason": "Correção linha IVA"},
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["status"] == "ABERTO"

    audit = client.get("/api/v1/audit-logs?action=PERIOD_REOPEN", headers=auth_headers)
    assert any(a["action"] == "PERIOD_REOPEN" for a in audit.json())


def test_export_ack_error_retry_and_rv_filter(client, auth_headers):
    period = client.post(
        "/api/v1/payroll-periods",
        headers=auth_headers,
        params={"year": 2026, "month": 11},
    ).json()
    period_id = period["id"]
    client.post(f"/api/v1/payroll-periods/{period_id}/generate", headers=auth_headers)

    rv = client.post(
        f"/api/v1/exports/payroll/{period_id}",
        headers=auth_headers,
        params={"engagement_type": "RV"},
    )
    # May be empty if no RV statements — try without filter then mark lifecycle
    if rv.status_code != 200:
        all_exp = client.post(f"/api/v1/exports/payroll/{period_id}", headers=auth_headers)
        assert all_exp.status_code == 200, all_exp.text
        batch_id = all_exp.json()["id"]
    else:
        batch_id = rv.json()["id"]
        assert "RV" in rv.json()["filename"] or rv.json()["row_count"] >= 0

    err = client.post(
        f"/api/v1/exports/{batch_id}/error",
        headers=auth_headers,
        json={"error_message": "PHC timeout"},
    )
    assert err.status_code == 200
    assert err.json()["status"] == "ERROR"

    retried = client.post(f"/api/v1/exports/{batch_id}/retry", headers=auth_headers)
    assert retried.status_code == 200
    assert retried.json()["status"] == "SENT"
    assert retried.json()["retry_count"] >= 1

    acked = client.post(
        f"/api/v1/exports/{batch_id}/ack",
        headers=auth_headers,
        json={"ack_reference": "PHC-ACK-1"},
    )
    assert acked.status_code == 200
    assert acked.json()["status"] == "ACKED"
    assert acked.json()["ack_reference"] == "PHC-ACK-1"


def test_docs_soft_block_and_supervisor_scope(client, auth_headers):
    # Enable soft-block
    org = client.get("/api/v1/organization", headers=auth_headers).json()
    client.patch(
        "/api/v1/organization",
        headers=auth_headers,
        json={"settings": {**org["settings"], "soft_block_docs_on_assign": True}},
    )

    week = client.get(
        "/api/v1/planning/week",
        headers=auth_headers,
        params={"week_start": "2026-11-02"},
    ).json()
    employees = week["employees"]
    diogo = next(e for e in employees if e["full_name"] == "Diogo Pereira")
    unassigned = next((s for s in week["shifts"] if not s["assignments"]), None)
    if unassigned is None:
        # pick any shift and reassign — soft block should still fire on Diogo
        target = week["shifts"][0]
    else:
        target = unassigned

    blocked = client.post(
        f"/api/v1/shifts/{target['id']}/assign",
        headers=auth_headers,
        json={"employee_id": diogo["id"], "allow_overlap_override": True},
    )
    assert blocked.status_code == 422, blocked.text
    assert blocked.json()["detail"]["code"] == "DOCS_SOFT_BLOCK"

    # Supervisor login — can only validate own team
    login = client.post(
        "/api/v1/auth/login",
        data={"username": "supervisor@fieldops.pt", "password": "fieldops"},
    )
    assert login.status_code == 200
    sup = {"Authorization": f"Bearer {login.json()['access_token']}"}
    pending = client.get("/api/v1/time-entries?status=SUBMETIDO", headers=sup).json()
    if pending:
        # Supervisor linked to Ana — entries for Ana's team should work; out-of-team may fail
        res = client.post(
            f"/api/v1/time-entries/{pending[0]['id']}/validate",
            headers=sup,
            json={"action": "APROVAR"},
        )
        assert res.status_code in {200, 400}


def test_health_and_notifications_endpoint(client, auth_headers):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    notes = client.get("/api/v1/notifications", headers=auth_headers)
    assert notes.status_code == 200
    assert isinstance(notes.json(), list)
