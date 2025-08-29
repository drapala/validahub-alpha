# ADR-002: Sistema de Filas

- **Status**: Proposed
- **Data**: 2025-08-29
- **Autor**: PM/BI Visionário

## Contexto

O ValidaHub precisa processar jobs de validação de forma assíncrona:
- Upload de CSV → processamento em background
- Retry de jobs falhados
- Rate limiting por tenant
- Observabilidade de throughput e latência

Requisitos MVP:
- Processamento assíncrono confiável
- Dead letter queue para jobs falhados
- Observabilidade básica
- Baixa complexidade operacional

## Decisão

**Fase 1 (MVP)**: Redis Streams
- Simplicidade operacional
- Consumer groups para paralelização
- Built-in acknowledgment e retry
- Observabilidade via Redis monitoring

**Fase 2 (Escala)**: Migração para Kafka
- Maior throughput e durabilidade
- Particionamento por tenant
- Melhor integração com analytics

## Consequências

### Positivo
- Redis Streams: setup simples, latência baixa
- Evolução gradual Redis → Kafka
- Experiência do time com Redis
- Monitoring integrado ao stack atual

### Negativo
- Redis Streams: durabilidade limitada vs Kafka
- Necessidade de migração futura
- Potencial duplicação de mensagens

## Alternativas Consideradas

### Apache Kafka (direto)
- **Prós**: Durabilidade, throughput, analytics ready
- **Contras**: Complexidade operacional alta para MVP

### RabbitMQ
- **Prós**: Feature-rich, dead letter queues
- **Contras**: Single point of failure, menos familiar

### AWS SQS
- **Prós**: Serverless, confiável
- **Contras**: Lock-in, latência alta, custo por mensagem