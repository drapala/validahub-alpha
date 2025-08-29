# ValidaHub 🚀

> **The Bloomberg of Brazilian Marketplaces**  
> Transform CSV validation into marketplace intelligence that drives better decisions and higher sales.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![LGPD Compliant](https://img.shields.io/badge/LGPD-Compliant-green.svg)](docs/security/)
[![Architecture: DDD](https://img.shields.io/badge/Architecture-DDD%20%2B%20Event%20Sourcing-blue.svg)](docs/architecture/)
[![API: OpenAPI 3.1](https://img.shields.io/badge/API-OpenAPI%203.1-orange.svg)](docs/architecture/API.md)

---

## 🎯 Vision & Mission

**Mission**: Transform catalog errors into marketplace intelligence, helping sellers sell more and integrators operate with confidence.

**Vision**: Become Brazil's standard business intelligence for e-commerce in 3 years — the definitive platform where sellers, integrators, and marketplaces find competitive insights and predictions.

### Why ValidaHub Exists

- **Today**: Each seller suffers alone with different rules, repetitive errors, and lost sales
- **Tomorrow**: A central hub of validation + intelligence that auto-corrects, generates insights, and improves everyone's performance

---

## 🧠 Intelligence-First Architecture

ValidaHub isn't just another CSV validator. We're building the **intelligence layer** for Brazil's e-commerce ecosystem through event sourcing and network effects.

```mermaid
graph TB
    subgraph "Data Ingestion"
        CSV[CSV Upload]
        API[REST API]
        SDK[SDK/Widgets]
    end
    
    subgraph "Processing Layer"
        RULES[Rule Engine<br/>Marketplace Specific]
        VALIDATE[Validation Pipeline]
        CORRECT[Auto-Correction]
    end
    
    subgraph "Event Store"
        EVENTS[Event Sourcing<br/>Every change tracked]
        AUDIT[Audit Trail<br/>LGPD Compliant]
    end
    
    subgraph "Intelligence Engine"
        ANALYTICS[Real-time Analytics]
        BENCHMARK[Cross-tenant Benchmarking]
        PREDICT[ML Predictions]
        INSIGHTS[Actionable Insights]
    end
    
    subgraph "Output Channels"
        DASHBOARD[Analytics Dashboard]
        ALERTS[Smart Alerts]
        REPORTS[Benchmark Reports]
        APIOUT[Intelligence API]
    end
    
    CSV --> RULES
    API --> VALIDATE
    SDK --> CORRECT
    
    RULES --> EVENTS
    VALIDATE --> EVENTS
    CORRECT --> EVENTS
    
    EVENTS --> ANALYTICS
    EVENTS --> BENCHMARK
    EVENTS --> PREDICT
    EVENTS --> INSIGHTS
    
    ANALYTICS --> DASHBOARD
    BENCHMARK --> ALERTS
    PREDICT --> REPORTS
    INSIGHTS --> APIOUT
    
    classDef intelligence fill:#e1f5fe
    class ANALYTICS,BENCHMARK,PREDICT,INSIGHTS intelligence
```

---

## 💡 Key Features

### 🔥 Core Validation Engine
- **Multi-marketplace support**: Mercado Livre, Magalu, Amazon Brasil
- **Real-time processing**: SSE streams + webhooks for instant feedback  
- **Smart corrections**: Auto-fix common catalog errors
- **Rule versioning**: Shadow mode testing before rule changes

### 📊 Intelligence Platform
- **Personal Analytics**: Track your catalog health over time
- **Anonymous Benchmarking**: Compare against market segments (LGPD-compliant)
- **Predictive Insights**: Forecast catalog issues before they happen
- **Competitive Intelligence**: Market trends and opportunity identification

### 🏗️ Developer Experience
- **15-minute integration**: From signup to first job
- **SDKs in 3 languages**: JavaScript, Python, Java
- **OpenAPI 3.1**: Contract-first development
- **Drop-in widgets**: `<vh-uploader>` component

---

## 🏛️ Technology Stack

### Core Architecture
```mermaid
graph LR
    subgraph "Frontend"
        NEXT[Next.js 14<br/>React + Tailwind]
        WIDGET[Web Components<br/>Drop-in Widgets]
    end
    
    subgraph "Backend"
        API[FastAPI<br/>Python 3.11]
        DOMAIN[Domain Layer<br/>DDD + Clean Arch]
        EVENTS[Event Sourcing<br/>PostgreSQL + Redis]
    end
    
    subgraph "Intelligence"
        ANALYTICS[Analytics Pipeline<br/>dbt + PostgreSQL]
        ML[ML Models<br/>scikit-learn]
        BENCH[Benchmarking Engine<br/>Anonymous Aggregation]
    end
    
    subgraph "Infrastructure"
        POSTGRES[(PostgreSQL 15<br/>JSONB + Partitioning)]
        REDIS[(Redis<br/>Streams + Cache)]
        S3[(S3/MinIO<br/>File Storage)]
        OTEL[OpenTelemetry<br/>Observability]
    end
    
    NEXT --> API
    WIDGET --> API
    API --> DOMAIN
    DOMAIN --> EVENTS
    EVENTS --> POSTGRES
    EVENTS --> REDIS
    EVENTS --> ANALYTICS
    ANALYTICS --> ML
    ML --> BENCH
    
    API --> S3
    API --> OTEL
```

### Key Technologies
- **Backend**: FastAPI + Pydantic + SQLAlchemy + Alembic
- **Frontend**: Next.js 14 (App Router) + shadcn/ui
- **Database**: PostgreSQL 15 with JSONB and partitioning
- **Queue**: Redis Streams → Kafka (future scale)
- **Storage**: S3/MinIO with presigned URLs
- **Observability**: OpenTelemetry + Prometheus + Sentry
- **Security**: JWT + scopes, CORS, rate limiting, LGPD compliance

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Node.js 18+ (for frontend)
- Python 3.11+ (for backend)

### 5-Minute Setup

```bash
# Clone the repository
git clone https://github.com/validahub/validahub-alpha.git
cd validahub-alpha

# Start infrastructure services
make up

# Run database migrations
make db.migrate

# Generate API types from OpenAPI
make contracts.gen

# Start development servers
make dev

# Your ValidaHub instance is ready!
# API: http://localhost:8000
# Web Dashboard: http://localhost:3000
```

### First Job Submission

```python
import requests

# Submit a CSV for validation
response = requests.post('http://localhost:8000/jobs', 
    headers={
        'Authorization': 'Bearer your-jwt-token',
        'X-Tenant-Id': 'your-tenant-id',
        'Idempotency-Key': 'unique-operation-id'
    },
    json={
        'channel': 'mercado_livre',
        'seller_id': 'seller_123',
        'file_ref': 's3://bucket/products.csv'
    }
)

job = response.json()
print(f"Job created: {job['id']}")

# Monitor progress via Server-Sent Events
import sseclient

events = sseclient.SSEClient('http://localhost:8000/jobs/stream')
for event in events:
    print(f"Status update: {event.data}")
```

---

## 📡 API Overview

### Intelligence-Focused Endpoints

```yaml
# Core Validation
POST   /jobs              # Submit validation job (idempotent)
GET    /jobs/{id}          # Job status + correction details
POST   /jobs/{id}/retry    # Reprocess with latest rules
GET    /jobs/stream        # Real-time updates via SSE

# Intelligence APIs  
GET    /analytics/personal          # Your catalog health metrics
GET    /benchmarks/segment/{segment} # Anonymous market comparison
GET    /insights/predictions        # ML-powered forecasts
GET    /intelligence/trends         # Market intelligence feeds

# Developer Tools
GET    /rules/profiles             # Available marketplace rule sets
POST   /rules/simulate             # Test rules before applying
GET    /health                     # System health + metrics
```

### Event-Driven Architecture

Every action generates CloudEvents for downstream intelligence:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "specversion": "1.0",
  "source": "apps/api",
  "type": "job.succeeded",
  "time": "2025-08-29T15:30:00Z",
  "subject": "job:6c0e7b5a-4f3c-4d1e-9b8f-2a1c3d4e5f6g",
  "tenant_id": "tenant_123",
  "data": {
    "job_id": "6c0e7b5a-4f3c-4d1e-9b8f-2a1c3d4e5f6g",
    "counters": {"errors": 2, "warnings": 5, "total": 1200},
    "duration_ms": 3420,
    "corrections_applied": 15
  }
}
```

---

## 🌐 Network Effects & Intelligence

ValidaHub creates a **virtuous cycle** where more users generate better intelligence for everyone:

```mermaid
graph TB
    SELLERS[More Sellers<br/>Upload Catalogs]
    DATA[More Data<br/>Better Patterns]
    INTELLIGENCE[Smarter Intelligence<br/>Better Insights]
    VALUE[Higher Value<br/>Better Outcomes]
    GROWTH[Platform Growth<br/>Network Effects]
    
    SELLERS --> DATA
    DATA --> INTELLIGENCE
    INTELLIGENCE --> VALUE
    VALUE --> GROWTH
    GROWTH --> SELLERS
    
    classDef highlight fill:#f9fbe7
    class INTELLIGENCE,VALUE highlight
```

### How Network Effects Work

1. **Data Aggregation**: Each validation job contributes to collective intelligence
2. **Anonymous Benchmarking**: Compare your performance against market segments (LGPD-compliant)
3. **Pattern Recognition**: ML models improve with more diverse catalog data
4. **Market Insights**: Cross-marketplace trends become visible only at scale
5. **Competitive Moats**: First-mover advantage compounds over time

---

## 🔄 Data Flow & Intelligence Pipeline

```mermaid
flowchart TD
    subgraph "Input Sources"
        CSV[CSV Files]
        API[API Calls]
        BULK[Bulk Imports]
    end
    
    subgraph "Processing Pipeline"
        INGEST[Data Ingestion<br/>Validation & Parsing]
        RULES[Rule Application<br/>Marketplace-Specific]
        CORRECT[Auto-Correction<br/>ML-Powered Fixes]
        EVENT[Event Generation<br/>CloudEvents Standard]
    end
    
    subgraph "Event Store"
        SOURCING[Event Sourcing<br/>Immutable History]
        AUDIT[Audit Trail<br/>LGPD Compliance]
    end
    
    subgraph "Intelligence Layer"
        AGGREGATE[Data Aggregation<br/>Anonymous + Secure]
        ANALYZE[Pattern Analysis<br/>ML Models]
        BENCHMARK[Benchmarking<br/>Segment Comparison]
        PREDICT[Predictions<br/>Future Performance]
    end
    
    subgraph "Insights & Actions"
        DASHBOARD[Personal Dashboard<br/>Catalog Health]
        ALERTS[Smart Alerts<br/>Performance Drops]
        REPORTS[Market Reports<br/>Competitive Intel]
        RECOMMEND[Recommendations<br/>Optimization Paths]
    end
    
    CSV --> INGEST
    API --> INGEST  
    BULK --> INGEST
    
    INGEST --> RULES
    RULES --> CORRECT
    CORRECT --> EVENT
    EVENT --> SOURCING
    EVENT --> AUDIT
    
    SOURCING --> AGGREGATE
    AGGREGATE --> ANALYZE
    ANALYZE --> BENCHMARK
    ANALYZE --> PREDICT
    
    BENCHMARK --> DASHBOARD
    PREDICT --> ALERTS
    ANALYZE --> REPORTS
    BENCHMARK --> RECOMMEND
    
    classDef processing fill:#fff3e0
    classDef intelligence fill:#e8f5e8
    classDef insights fill:#e3f2fd
    
    class INGEST,RULES,CORRECT processing
    class AGGREGATE,ANALYZE,BENCHMARK,PREDICT intelligence
    class DASHBOARD,ALERTS,REPORTS,RECOMMEND insights
```

---

## 🏗️ Contributing

We're building ValidaHub as an **open intelligence platform**. Contributions welcome!

### Development Setup

```bash
# Install development dependencies
pip install -r requirements-dev.txt
npm install

# Run tests
make test                # All tests
make test.unit          # Unit tests only
make test.integration   # Integration tests
make check.arch         # Architecture compliance

# Code quality
make lint               # Ruff + ESLint
make type-check         # mypy + tsc
make format             # Auto-format code
```

### Architecture Principles

- **Domain-Driven Design**: Pure domain logic, ports & adapters
- **Event Sourcing**: Every change is an event, full audit trail
- **Contract-First**: OpenAPI 3.1 as single source of truth
- **Test-Driven**: RED → GREEN → REFACTOR cycle
- **Telemetry-First**: Structured logging, metrics, traces

### Contribution Guidelines

1. **Fork & Branch**: Create feature branches from `main`
2. **Conventional Commits**: `feat(domain): add catalog validation`
3. **Tests Required**: Unit + integration tests for new features  
4. **Architecture Tests**: Verify layer separation compliance
5. **Documentation**: Update ADRs for architectural decisions

---

## 📊 Roadmap & Intelligence Evolution

### Phase 1: Foundation Intelligence (Q1 2025)
**Theme**: "Your Catalog Health Dashboard"

- ✅ Personal analytics tracking
- ✅ Error pattern analysis  
- ✅ Processing time trends
- ✅ Basic improvement suggestions

### Phase 2: Competitive Intelligence (Q2-Q3 2025)
**Theme**: "How You Compare to Market"

- 🚧 Anonymous benchmarking system
- 📋 Market trend identification
- 📋 Segment performance comparison
- 📋 Best practices recommendations

### Phase 3: Predictive Intelligence (Q4 2025+)
**Theme**: "Your Marketplace Oracle"

- 📋 Catalog health forecasting
- 📋 Error prevention predictions
- 📋 Market trend predictions
- 📋 Optimization roadmaps

---

## 🔒 Privacy & Legal

### LGPD Compliance

ValidaHub is **privacy-first** and fully compliant with Brazil's LGPD (Lei Geral de Proteção de Dados):

- **Anonymous Benchmarking**: No PII in comparative analytics
- **Data Minimization**: Only collect what's necessary for intelligence
- **Consent Management**: Clear opt-in/opt-out for data usage
- **Right to Deletion**: Complete data removal on request
- **Audit Trails**: Immutable logs of all data access
- **Security by Design**: Encryption at rest and in transit

### Security Features

- **Idempotency Keys**: Prevent duplicate operations
- **Rate Limiting**: Per-tenant quotas and throttling
- **JWT + Scopes**: Fine-grained access control  
- **CSV Security**: Formula injection prevention
- **Audit Logging**: Complete operation trail
- **Correlation IDs**: Request tracing across services

---

## 📞 Support & Community

### Getting Help

- **Documentation**: [docs/](docs/) - Comprehensive guides and ADRs
- **API Reference**: [OpenAPI Spec](docs/architecture/API.md)
- **GitHub Issues**: Bug reports and feature requests
- **Discussions**: Architecture and product discussions

### Enterprise Support

For enterprises requiring SLAs, custom integrations, or dedicated support:

- **Email**: enterprise@validahub.com
- **Calendar**: [Book a demo](https://calendar.validahub.com)
- **Slack**: Join our partner channel

---

## 📄 License

ValidaHub is released under the [MIT License](LICENSE).

**Copyright © 2025 ValidaHub**  
*Transforming Brazilian e-commerce, one catalog at a time.*

---

<div align="center">

**[🚀 Get Started](https://app.validahub.com)** • 
**[📖 Documentation](docs/)** • 
**[💬 Community](https://github.com/validahub/validahub-alpha/discussions)** •
**[🐛 Issues](https://github.com/validahub/validahub-alpha/issues)**

*Built with ❤️ in São Paulo, Brazil*

</div>