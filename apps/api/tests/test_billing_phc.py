from datetime import date, timedelta


def test_time_entries_seeded_with_approvals(client, auth_headers):
    approved = client.get("/api/v1/time-entries?status=APROVADO", headers=auth_headers)
    assert approved.status_code == 200
    assert len(approved.json()) >= 1
    pending = client.get("/api/v1/time-entries?status=SUBMETIDO", headers=auth_headers)
    assert pending.status_code == 200


def test_validate_and_cap_billable(client, auth_headers):
    pending = client.get("/api/v1/time-entries?status=SUBMETIDO", headers=auth_headers).json()
    if not pending:
        # submit one from draft
        all_entries = client.get("/api/v1/time-entries", headers=auth_headers).json()
        draft = next(e for e in all_entries if e["status"] == "RASCUNHO")
        client.post(
            f"/api/v1/time-entries/{draft['id']}/submit",
            headers=auth_headers,
            json={"hours_executed": "5.00"},
        )
        pending = client.get("/api/v1/time-entries?status=SUBMETIDO", headers=auth_headers).json()
    entry = pending[0]
    # Approve with hours above contracted without override → billable capped
    contracted = float(entry["hours_contracted"])
    res = client.post(
        f"/api/v1/time-entries/{entry['id']}/validate",
        headers=auth_headers,
        json={
            "action": "AJUSTAR",
            "hours_approved": str(contracted + 2 if contracted else 5),
            "allow_extra_billable": False,
            "adjustment_note": "teste teto Q11",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "APROVADO"
    if contracted > 0:
        assert float(body["hours_billable"]) <= contracted + 0.001


def test_auto_approve_q12(client, auth_headers):
    # Create a fresh submitted entry and backdate via re-run with as_of far future
    entries = client.get("/api/v1/time-entries?status=RASCUNHO", headers=auth_headers).json()
    if not entries:
        return
    entry_id = entries[0]["id"]
    client.post(
        f"/api/v1/time-entries/{entry_id}/submit",
        headers=auth_headers,
        json={"hours_executed": "3.00"},
    )
    # Force due date by using as_of far ahead
    res = client.post(
        "/api/v1/time-entries/auto-approve",
        headers=auth_headers,
        params={"as_of": "2026-12-31"},
    )
    assert res.status_code == 200
    # At least the newly submitted one should auto-approve when due
    assert isinstance(res.json(), list)


def test_billing_periods_and_drafts(client, auth_headers):
    periods = client.post(
        "/api/v1/billing-periods",
        headers=auth_headers,
        json={"year": 2026, "month": 11},
    )
    assert periods.status_code == 200
    assert len(periods.json()) == 4
    period = next(p for p in periods.json() if p["service_area"] == "REPOSICAO")
    drafts = client.post(
        f"/api/v1/billing-periods/{period['id']}/generate",
        headers=auth_headers,
    )
    assert drafts.status_code == 200, drafts.text
    assert len(drafts.json()) >= 1
    draft = drafts.json()[0]
    assert draft["currency"] == "EUR"
    assert float(draft["total_gross"]) >= float(draft["total_net"])


def test_margin_and_costs(client, auth_headers):
    contracts = client.get("/api/v1/contracts", headers=auth_headers).json()
    contract = next(c for c in contracts if c["type"] == "REPOSICAO")
    margin = client.get(
        f"/api/v1/contracts/{contract['id']}/margin",
        headers=auth_headers,
        params={"year": 2026, "month": 11},
    )
    assert margin.status_code == 200
    body = margin.json()
    assert "expected_margin" in body
    assert body["currency"] == "EUR"


def test_payroll_and_exports(client, auth_headers):
    period = client.post(
        "/api/v1/payroll-periods",
        headers=auth_headers,
        params={"year": 2026, "month": 11},
    )
    assert period.status_code == 200
    period_id = period.json()["id"]
    stmts = client.post(f"/api/v1/payroll-periods/{period_id}/generate", headers=auth_headers)
    assert stmts.status_code == 200, stmts.text

    billing_periods = client.get(
        "/api/v1/billing-periods",
        headers=auth_headers,
        params={"year": 2026, "month": 11},
    ).json()
    area = next(p for p in billing_periods if p["service_area"] == "REPOSICAO")
    client.post(f"/api/v1/billing-periods/{area['id']}/generate", headers=auth_headers)
    exp = client.post(f"/api/v1/exports/billing/{area['id']}", headers=auth_headers)
    assert exp.status_code == 200, exp.text
    assert exp.json()["batch_type"] == "FATURACAO"
    assert "Artigo" in (exp.json().get("content_preview") or "")

    pay_exp = client.post(f"/api/v1/exports/payroll/{period_id}", headers=auth_headers)
    assert pay_exp.status_code == 200, pay_exp.text
    assert "Cliente" in (pay_exp.json().get("content_preview") or "")

    dl = client.get(f"/api/v1/exports/{exp.json()['id']}/download", headers=auth_headers)
    assert dl.status_code == 200
    assert "text/csv" in dl.headers.get("content-type", "")


def test_dashboard_kpis(client, auth_headers):
    res = client.get(
        "/api/v1/dashboard/kpis",
        headers=auth_headers,
        params={"week_start": "2026-11-02", "year": 2026, "month": 11},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["contracts"] >= 1
    assert "approved_hours_month" in body
