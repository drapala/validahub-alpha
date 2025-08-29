**TL;DR:** Organizei toda a discussão em um `claude.md` estruturado com 12 seções cobrindo arquitetura, stack, regras de engenharia, telemetria e integração plug-and-play. Pronto para colar no repo e começar o vibecoding.

---

# claude.md - ValidaHub Engineering Playbook

## 1. Visão e Arquitetura

### Princípios Fundamentais
- **DDD + Ports & Adapters**: Domínio puro, casos de uso orquestrando portas, adapters plugáveis
- **Contratos únicos**: OpenAPI 3.1 como fonte da verdade, tipos gerados automaticamente
- **Multi-tenant by design**: `tenant_id` em dados, logs, métricas e traces
- **Telemetria-first**: Eventos padronizados (CloudEvents) para BI desde o MVP
- **Segurança by default**: Idempotência, rate limiting, audit log, CSV hardening
- **Observabilidade completa**: OpenTelemetry (logs/metrics/traces), correlation IDs

### Estrutura do Repositório
```
validahub/
├── apps/
│   ├── api/          # FastAPI expõe casos de uso via ports
│   └── web/          # Next.js 14 (dashboard + landing)
├── packages/
│   ├── contracts/    # OpenAPI, schemas, eventos CloudEvents
│   ├── domain/       # Entidades, VOs, agregados, eventos puros
│   ├── application/  # Casos de uso + ports (interfaces)
│   ├── infra/        # Adapters: Postgres, Redis, S3, SSE
│   ├── rules/        # YAMLs de mapeamento e regras por marketplace
│   ├── shared/       # Telemetria SDK, utils, errors
│   └── analytics/    # dbt models, métricas, fatos e dimensões
├── tests/
│   ├── unit/         # pytest + golden tests
│   ├── integration/  # API/contracts/DB
│   └── architecture/ # Testes de camadas
├── docker/           # compose para dev (pg, redis, minio, otel)
├── .github/workflows/
├── .editorconfig
├── README.md
└── claude.md         # ESTE ARQUIVO
```

## 2. Stack Tecnológica

### Core
- **Backend**: FastAPI + Pydantic + SQLAlchemy + Alembic
- **Frontend**: Next.js 14 (App Router) + React + Tailwind + shadcn/ui
- **DB**: PostgreSQL 15 (JSONB, particionamento, RLS opcional)
- **Queue**: Redis Streams → Kafka (escala futura)
- **Storage**: S3/MinIO com presigned URLs
- **Contracts**: OpenAPI 3.1 → openapi-typescript → ts-rest

### DevOps & Observabilidade
- **Infra**: Docker Compose (dev), Terraform (prod)
- **CI/CD**: GitHub Actions
- **Secrets**: Doppler/Vault (NUNCA .env no repo)
- **Observability**: OpenTelemetry, Prometheus, Sentry
- **Security**: JWT + scopes, CORS restritivo, rate limiting

## 3. Modelo de Domínio

### Entidades Core
```python
Job:
  id: UUID
  tenant_id: str
  seller_id: str
  channel: str
  type: str
  status: JobStatus
  file_ref: str
  counters: {errors: int, warnings: int, total: int}
  idempotency_key: Optional[str]
  rules_profile_id: str  # ex: "ml@1.2.3"
  created_at: datetime
  updated_at: datetime

JobStatus: queued | running | succeeded | failed | cancelled | expired | retrying
```

### Eventos de Domínio (CloudEvents)
```json
{
  "id": "uuid",
  "specversion": "1.0",
  "source": "apps/api",
  "type": "job.succeeded",
  "time": "2025-08-28T23:10:00Z",
  "subject": "job:6c0e...",
  "trace_id": "...",
  "tenant_id": "t_123",
  "actor_id": "seller_456",
  "schema_version": "1",
  "data": {
    "job_id": "6c0e...",
    "counters": {"errors": 2, "warnings": 3, "total": 120},
    "duration_ms": 8423
  }
}
```

## 4. Regras de Engenharia

### Camadas (Obrigatório)
- `domain/` não importa NADA de framework
- `application/` não importa `infra/*`
- `infra/` pode importar `application/` e `domain/`
- Testes de arquitetura no CI validam essas regras

### SOLID Pragmático
- **SRP**: Cada caso de uso faz uma coisa
- **DIP**: Tudo que conversa com o mundo externo é Port
- **ISP**: Interfaces pequenas e focadas
- **OCP/LSP**: Apenas quando há variação real

### Object Calisthenics (Subset)
- Métodos ≤ 25 linhas, classes ≤ 200 linhas
- Value Objects para conceitos do domínio (imutáveis)
- Evitar boolean params, preferir enums
- Máximo 1 nível de indentação em casos de uso

### Segurança Mandatória
- `Idempotency-Key` obrigatório em POSTs que criam recursos
- Rate limiting por tenant via Redis
- CSV hardening: bloquear fórmulas (`^[=+\-@]`)
- Audit log imutável com `who, when, what, request_id`
- Secrets via Doppler/Vault

## 5. Regras de PR e Commits

### Conventional Commits
```
type(scope)!: mensagem curta

Types: feat, fix, chore, refactor, docs, test, perf, build, ci, revert, rules, contracts, telemetry
Scopes: domain, application, infra, api, web, contracts, rules, analytics, ops
```

### Branching
```
feat/<scope>-<slug>
fix/<scope>-<slug>
chore/<scope>-<slug>
refactor/<scope>-<slug>
```

### Limites de PR
- Soft: ≤ 200 linhas alteradas
- Hard: ≤ 400 linhas (CI falha acima disso)
- Exceção: label `size/override` com justificativa

### Checklist de PR
- [ ] Título segue Conventional Commits
- [ ] OpenAPI atualizado se contrato mudou
- [ ] Testes adicionados/ajustados
- [ ] Respeita camadas de arquitetura
- [ ] Logs com `tenant_id` e `request_id`
- [ ] Migração DB reversível

## 6. Sistema de Regras Agnóstico

### Canonical CSV Model (CCM)
```
sku, title, description, brand, gtin, ncm,
price_brl, currency, stock,
weight_kg, length_cm, width_cm, height_cm,
category_path, images[],
attributes: {key: value}
```

### Estrutura de Rule Packs
```
packages/rules/
  marketplace/
    mercado_livre/1.0/
      mapping.yaml     # marketplace → canônico
      ruleset.yaml     # validações e correções
    magalu/1.0/
      mapping.yaml
      ruleset.yaml
```

### Versionamento de Regras
- **SemVer**: major.minor.patch
- **Auto-apply**: patch sempre, minor com shadow period
- **Major changes**: opt-in com simulador de impacto
- **Job tracking**: cada job grava `rules_profile_id@version`

## 7. Telemetria e BI-Ready

### Event Outbox Pattern
```sql
CREATE TABLE event_outbox (
  id uuid PRIMARY KEY,
  tenant_id text NOT NULL,
  type text NOT NULL,
  occurred_at timestamptz NOT NULL DEFAULT now(),
  payload jsonb NOT NULL,
  dispatched_at timestamptz,
  attempt int NOT NULL DEFAULT 0
);
```

### Storage de Eventos
```
s3://validahub-events/{env}/type=job.succeeded/dt=YYYY-MM-DD/tenant_id=.../*.ndjson
```

### Métricas Core (SLOs)
- Taxa de sucesso: `jobs_succeeded / jobs_total` (SLO: ≥ 99%)
- P95 latency: `submitted → succeeded` (SLO: ≤ 30s)
- Erro por canal: média de erros por job
- ROI estimado: minutos economizados × valor/hora

## 8. Integração Plug & Play

### TTFV < 15 minutos
1. Quickstart 5 passos + Postman collection
2. SDKs oficiais (JS, Python, Java)
3. Webhooks com HMAC + replay
4. Widget `<vh-uploader>` drop-in
5. Partner Console com logs
6. Suite de conformidade CLI

### Endpoints Core
```
POST /jobs              # Idempotency-Key required
GET  /jobs/{id}         # Status + counters
POST /jobs/{id}/retry   # Reprocessamento
GET  /jobs/stream       # SSE por tenant
GET  /jobs/{id}/download # Presigned URL
```

## 9. Prompts Claude CLI

### A. Criar OpenAPI inicial
```
Crie packages/contracts/openapi.yaml com:
- Security: Bearer JWT com scopes (jobs:read, jobs:write)
- Headers: X-Tenant-Id, X-Request-Id, Idempotency-Key
- Schemas: JobStatus enum, Job, SubmitJobRequest/Response
- Paths: POST /jobs, GET /jobs/{id}, POST /jobs/{id}/retry, GET /jobs/stream (SSE)
- Exemplos em todas as responses
```

### B. Domínio puro
```
Em packages/domain, crie:
- value_objects.py: JobId, TenantId, SellerId, Channel, IdempotencyKey
- enums.py: JobStatus (queued, running, succeeded, failed, cancelled, expired, retrying)
- events.py: JobSubmitted, JobStarted, JobSucceeded, JobFailed (CloudEvents)
- job.py: agregado Job com invariantes e transições de estado
Inclua testes unitários cobrindo transições válidas e inválidas
```

### C. Casos de uso
```
Em packages/application:
- ports.py: JobRepository, EventBus, ObjectStorage, RateLimiter
- use_cases/submit_job.py: valida rate limit, cria Job, persiste, publica evento
- use_cases/retry_job.py: valida status elegível, cria novo Job
Escreva testes com mocks das ports
```

### D. Adapters de infraestrutura
```
Em packages/infra:
- SQLAlchemy models com UNIQUE(tenant_id, idempotency_key)
- Redis EventBus via Streams
- S3/MinIO ObjectStorage com presigned URLs
- RateLimiter com token bucket Redis
Inclua docker-compose.yml com postgres, redis, minio
```

### E. API FastAPI
```
Crie apps/api com:
- Carregamento do OpenAPI de packages/contracts
- Middlewares: X-Request-Id, logs JSON, JWT auth
- Endpoint SSE /jobs/stream com keep-alive 20s
- Health/readiness endpoints
- Testes de contrato validando responses contra OpenAPI
```

### F. Frontend Next.js
```
Crie apps/web com:
- shadcn/ui + Tailwind configurados
- Client fetch tipado dos types gerados
- Tabela de Jobs com status badges
- Hook SSE para toasts de notificação
- Upload com presigned URL
```

### G. Golden tests
```
Crie tests/unit/golden/test_corrections.py:
- Para cada CSV em tests/fixtures/input/*.csv
- Roda pipeline e compara com tests/fixtures/expected/*.csv
- Bloqueia mudanças não intencionais no formato
```

### H. Telemetria SDK
```
Em packages/shared/telemetry:
- envelope.py: builder CloudEvents com trace/tenant
- sinks.py: ConsoleSink, RedisSink, S3Sink
- emitter.py: emit_event, metric, span
- validators.py: validação contra JSON Schema
```

### I. Rule pack compiler
```
Crie packages/rules/compiler:
- compile_mapping.py: YAML → IR para mapeamento
- compile_ruleset.py: YAML → IR para regras
- validate.py: valida YAMLs contra schemas
CI deve compilar e cachear IR
```

### J. CI/CD completo
```
Configure .github/workflows/ci.yml:
- Matrix build (api, web)
- Lint (ruff/eslint), type-check (mypy/tsc)
- Testes unitários e de contrato
- Validação de arquitetura (camadas)
- Compilação de rule packs
- Size check de PR (≤400 linhas)
```

## 10. Bootstrap Commands

```bash
make up                 # Sobe docker-compose
make db.migrate         # Roda Alembic migrations
make contracts.gen      # Gera tipos do OpenAPI
make rules.compile      # Compila YAMLs → IR
make test               # Roda todos os testes
make check.arch         # Valida dependências entre camadas
```

## 11. Enforcement & Quality Gates

### pyproject.toml
```toml
[tool.ruff]
line-length = 100
target-version = "py311"
select = ["E","F","I","C90","B","UP","PL"]

[tool.ruff.lint.mccabe]
max-complexity = 10

[tool.mypy]
python_version = "3.11"
strict = true
disallow_untyped_defs = true
```

### Pre-commit hooks
```yaml
repos:
  - repo: local
    hooks:
      - id: check-contracts
        name: Check OpenAPI sync
        entry: make contracts.check
      - id: check-architecture
        name: Check layer dependencies
        entry: make check.arch
```

## 13. Métricas de Uso dos Agents

### Telemetria de Agents
Trackear para otimização do workflow:

```python
# packages/shared/telemetry/agent_metrics.py
AGENT_METRICS = {
    "agent_calls_total": Counter("agent", "command"),
    "delegation_chain_length": Histogram(),
    "fallback_rate": Gauge(),
    "most_used_pairs": Counter("from_agent", "to_agent")
}