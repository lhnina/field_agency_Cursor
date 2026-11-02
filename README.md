# FieldOps — Field Operations SaaS

Produto provisório **FieldOps** (Q36 aberto) · UI em **PT-PT** · identidade **Atlantic Ops**.

Monólito modular: React + TypeScript + Tailwind (web) · FastAPI + PostgreSQL (API).

## PRs

- **PR1** — foundation (scaffold, auth/RBAC, cadastro, contratos, planeamento shell, 7 horas, seed)
- **PR2** — planning ops (afetação estável, overlap, ausências, substituições, alertas docs, CI)

### PR2 (planning ops)

- Afetação estável no plano + UI lista/atribuir (Q04 / Q30)
- Overlap hard-block na afetação + alertas de serviços sem recurso
- Ausências (pedido + aprovação) com bloqueio visual no calendário
- Substituições com histórico previsto vs executado
- Alertas de documentos a expirar / expirados
- CI GitHub Actions (pytest API + build web)

## Pré-requisitos

- Node.js 20+
- Python 3.11+
- Docker (para Postgres) **ou** Postgres 16 local

## Arranque rápido

### 1. Base de dados

```bash
docker compose up -d db
# credenciais: fieldops / fieldops · DB: fieldops · porta 5432
```

### 2. API

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# opcional: alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Seed automático no startup (`SEED_ON_STARTUP=true` por omissão).

- OpenAPI: http://127.0.0.1:8000/docs  
- Health: http://127.0.0.1:8000/health  

Login demo:

| Email | Password | Perfil |
|---|---|---|
| `admin@fieldops.pt` | `fieldops` | Administrador |
| `gestor@fieldops.pt` | `fieldops` | Gestor operacional |

(Também: `direcao@`, `supervisor@`, `rh@`, `fin@`, `ana.sousa@demo.` — password `fieldops`)

### 3. Web

```bash
cd apps/web
npm install
npm run dev
```

Abrir http://127.0.0.1:5173 (proxy `/api` → API).

Variáveis opcionais:

```bash
# apps/api
DATABASE_URL=postgresql+psycopg2://fieldops:fieldops@localhost:5432/fieldops
SECRET_KEY=fieldops-dev-secret-change-me
CORS_ORIGINS=http://localhost:5173

# apps/web
VITE_API_BASE=/api/v1
```

## Decisões honradas neste PR

- Plataforma = master operacional; PHC export mais tarde (Q01)
- Afetação estável ao nível do planeamento / ServicePlan (Q04)
- Equipas fixas: faturação mensal + ausências; **sem** turnos diários (Q06)
- Defaults de faturação Q10–Q12 nos settings/modelo
- CT = alertas apenas (Q20) — sem bloqueios legais

## Fora de âmbito (PR1)

PHC export completo, fecho financeiro, PWA, IA, UI multi-tenant, epics MVP restantes.

## Estrutura

```
apps/
  api/          FastAPI + SQLAlchemy + Alembic
  web/          Vite + React + Tailwind (tokens Atlantic Ops)
docker-compose.yml
```
