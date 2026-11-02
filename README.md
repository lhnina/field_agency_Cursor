# FieldOps — Field Operations SaaS

Produto provisório **FieldOps** (Q36 aberto) · UI em **PT-PT** · identidade **Atlantic Ops**.

Monólito modular: React + TypeScript + Tailwind (web) · FastAPI + PostgreSQL (API).

## O que este PR inclui (PR1 foundation)

- Scaffold `apps/web` + `apps/api` + `docker-compose` (Postgres)
- Auth JWT + stub RBAC com **7 perfis** seedados
- CRUD mínimo: Organization, Client, Brand, RetailChain/Store, Collaborator
- Contratos tipados (`REPOSICAO|PROMOCAO|LOGISTICA|EQUIPAS_FIXAS`) + linhas + versionamento stub
- ServicePlan + geração de turnos (stub) + vista semanal de planeamento
- Modelo das **7 horas** no domínio (`time_entries` + `time_state_history`)
- Tokens Atlantic Ops aplicados na UI
- Seed demo PT (semana 45 · 2–8 nov 2026)

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
