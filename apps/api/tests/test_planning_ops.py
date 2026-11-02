from datetime import date


def test_login_and_me(client, auth_headers):
    me = client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.status_code == 200
    assert me.json()["email"] == "admin@fieldops.pt"
    assert "ADMINISTRADOR" in me.json()["roles"]


def test_planning_week_includes_absences_and_unassigned(client, auth_headers):
    res = client.get("/api/v1/planning/week?week_start=2026-11-02", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["unassigned_count"] >= 1
    assert any(a["absence_type"] == "FERIAS" and a["status"] == "APROVADO" for a in data["absences"])
    assert len(data["shifts"]) >= 1


def test_assign_unassigned_shift(client, auth_headers):
    week = client.get("/api/v1/planning/week?week_start=2026-11-02", headers=auth_headers).json()
    unassigned = next(s for s in week["shifts"] if not s["assignments"])
    ines = next(e for e in week["employees"] if e["full_name"] == "Inês Rocha")

    res = client.post(
        f"/api/v1/shifts/{unassigned['id']}/assign",
        headers=auth_headers,
        json={"employee_id": ines["id"], "set_as_stable_default": True},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["assignments"][0]["employee_id"] == ines["id"]
    assert body["status"] == "ATRIBUIDO"


def test_overlap_blocked(client, auth_headers):
    week = client.get("/api/v1/planning/week?week_start=2026-11-02", headers=auth_headers).json()
    # Ana already has Amadora Mon 09-12; Cascais also Mon 09-12 unassigned — assign Ana → overlap
    ana = next(e for e in week["employees"] if e["full_name"] == "Ana Sousa")
    cascais = next(
        s
        for s in week["shifts"]
        if not s["assignments"] and s["store_name"] and "Cascais" in s["store_name"] and s["planned_start"].startswith("2026-11-02")
    )
    res = client.post(
        f"/api/v1/shifts/{cascais['id']}/assign",
        headers=auth_headers,
        json={"employee_id": ana["id"]},
    )
    assert res.status_code == 409, res.text


def test_absence_blocks_assignment(client, auth_headers):
    week = client.get("/api/v1/planning/week?week_start=2026-11-02", headers=auth_headers).json()
    bruno = next(e for e in week["employees"] if e["full_name"] == "Bruno Martins")
    unassigned = next(s for s in week["shifts"] if not s["assignments"])
    res = client.post(
        f"/api/v1/shifts/{unassigned['id']}/assign",
        headers=auth_headers,
        json={"employee_id": bruno["id"]},
    )
    assert res.status_code == 400
    assert "ausência" in res.json()["detail"].lower()


def test_substitute_records_history(client, auth_headers):
    week = client.get("/api/v1/planning/week?week_start=2026-11-02", headers=auth_headers).json()
    assigned = next(s for s in week["shifts"] if s["assignments"] and s["assignments"][0]["employee_name"] == "Ana Sousa")
    ines = next(e for e in week["employees"] if e["full_name"] == "Inês Rocha")
    res = client.post(
        f"/api/v1/shifts/{assigned['id']}/substitute",
        headers=auth_headers,
        json={"substitute_employee_id": ines["id"], "reason": "Teste substituição"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["planned_employee_name"] == "Ana Sousa"
    assert body["executed_employee_name"] == "Inês Rocha"

    hist = client.get(f"/api/v1/substitutions?shift_id={assigned['id']}", headers=auth_headers)
    assert hist.status_code == 200
    assert len(hist.json()) >= 1


def test_absence_approve_flow(client, auth_headers):
    emps = client.get("/api/v1/employees", headers=auth_headers).json()
    carla = next(e for e in emps if e["full_name"] == "Carla Ferreira")
    created = client.post(
        "/api/v1/absences",
        headers=auth_headers,
        json={
            "employee_id": carla["id"],
            "absence_type": "FALTA",
            "start_date": "2026-11-10",
            "end_date": "2026-11-10",
            "reason": "Doença",
        },
    )
    assert created.status_code == 201
    absence_id = created.json()["id"]
    decided = client.post(
        f"/api/v1/absences/{absence_id}/decide",
        headers=auth_headers,
        json={"status": "APROVADO"},
    )
    assert decided.status_code == 200
    assert decided.json()["status"] == "APROVADO"


def test_alerts_include_docs_and_unassigned(client, auth_headers):
    res = client.get("/api/v1/alerts?week_start=2026-11-02", headers=auth_headers)
    assert res.status_code == 200
    kinds = {a["kind"] for a in res.json()}
    assert "UNASSIGNED_SHIFT" in kinds
    assert "DOC_EXPIRING" in kinds or "DOC_EXPIRED" in kinds


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"
