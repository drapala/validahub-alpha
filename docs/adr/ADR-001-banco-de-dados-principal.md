# ADR-001: Banco de Dados Principal

- **Status**: Proposed
- **Data**: 2025-08-29
- **Autor**: PM/BI Visionário

## Contexto

O ValidaHub precisa de um banco de dados robusto para armazenar:
- Jobs de validação com metadados (tenant_id, status, counters)
- Regras de validação por marketplace
- Audit logs imutáveis
- Dados multi-tenant com isolamento seguro

Requisitos:
- Multi-tenancy seguro
- Suporte a JSONB para metadados flexíveis
- Transações ACID para consistência
- Extensibilidade para analytics futuro

## Decisão

Adotar **PostgreSQL 15+** como banco principal com:
- JSONB para metadados e configurações flexíveis
- Particionamento por tenant_id para isolamento
- Row Level Security (RLS) opcional para segurança extra
- Índices GIN para queries JSONB eficientes

## Consequências

### Positivo
- Ecossistema maduro com SQLAlchemy/Alembic
- JSONB oferece flexibilidade sem perder performance
- Suporte nativo a multi-tenancy
- Analytics ready com extensões (pg_stat_statements)
- Baixo custo operacional inicial

### Negativo
- Não escala horizontalmente nativamente
- Requer expertise em tuning para alta escala
- JSONB pode mascarar problemas de schema mal definido

## Alternativas Consideradas

### MySQL
- **Prós**: Familiar, bom para read-heavy
- **Contras**: JSON support inferior, menos extensível

### MongoDB
- **Prós**: Schema flexível, escala horizontal
- **Contras**: Eventual consistency, menos maduro para transações

### DynamoDB
- **Prós**: Serverless, auto-scaling
- **Contras**: Lock-in AWS, queries limitadas, custo imprevisível