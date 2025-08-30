# Architecture Decision Records (ADR)

Este diretório contém todas as decisões arquiteturais do ValidaHub.

## Índice de ADRs

| ADR | Título | Status | Data |
|-----|--------|--------|------|
| [001](ADR-001-banco-de-dados-principal.md) | Banco de Dados Principal | Proposed | 2025-08-29 |
| [002](ADR-002-filas.md) | Sistema de Filas | Proposed | 2025-08-29 |
| [003](ADR-003-logs-imutaveis.md) | Logs Imutáveis | Proposed | 2025-08-29 |
| [004](ADR-004-event-sourcing-architecture.md) | Event Sourcing Architecture | Proposed | 2025-08-29 |
| [005](ADR-005-data-taxonomy-pii-classification.md) | Data Taxonomy and PII Classification | Proposed | 2025-08-29 |
| [006](ADR-006-analytics-data-schema.md) | Analytics Data Schema (Star Schema) | Proposed | 2025-08-29 |
| [007](ADR-007-cross-marketplace-product-classification.md) | Cross-Marketplace Product Classification | Proposed | 2025-08-29 |
| [008](ADR-008-sdk-development-strategy.md) | SDK Development Strategy | Proposed | 2025-08-29 |
| [009](ADR-009-smart-rules-engine-architecture.md) | Smart Rules Engine Architecture | Accepted | 2025-08-30 |

## Status Possíveis

- **Proposed**: Decisão em discussão
- **Accepted**: Decisão aprovada e implementada
- **Superseded**: Decisão substituída por outra mais recente

## Como Usar

1. Toda decisão arquitetural deve virar um ADR
2. ADRs aceitos são imutáveis - mudanças criam novos ADRs
3. Sempre incluir contexto, decisão, consequências e alternativas
4. Manter este README atualizado com novos ADRs