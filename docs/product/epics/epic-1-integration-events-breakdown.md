# Epic 1: Sistema de Integração Desacoplada - User Stories

**Epic RICE Score:** 84 (Alta Prioridade)  
**Meta de Negócio:** Reduzir 70% dos problemas de acoplamento em integrações B2B  
**Valor Estimado:** R$ 3.5M+ em mitigação de riscos de integração

---

## US-1.1: CloudEvents Schema para Integração Externa 
**Story Points: 3** | **Prioridade: P0** | **Sprint: 1**

> **Como** desenvolvedor integrando com ValidaHub,  
> **Eu quero** receber eventos padronizados no formato CloudEvents 1.0,  
> **Para que** eu possa integrar de forma confiável sem conhecer detalhes internos do sistema.

### Valor de Negócio
Padronização reduz tempo de integração de 2 semanas para 3 dias, eliminando 60% das dúvidas técnicas e incompatibilidades.

### Critérios de Aceite
- [ ] **Schema CloudEvents 1.0:** Todos eventos seguem especificação oficial (specversion, type, source, id, time, data)
- [ ] **Eventos de integração definidos:** `job.submitted`, `job.started`, `job.completed`, `job.failed`  
- [ ] **Metadados obrigatórios:** `tenant_id`, `correlation_id`, `version` em todos eventos
- [ ] **Versionamento semântico:** Schema events com v1.0, v1.1, etc. para evolução controlada
- [ ] **Validação JSON Schema:** Todos eventos validados contra schema formal
- [ ] **Documentação OpenAPI:** Schema disponível via `/api/v1/events/schema` endpoint
- [ ] **Payload mínimo:** Apenas dados essenciais para integração (não vazar detalhes internos)

### Critérios de Sucesso
- Validação de schema: 100% dos eventos passam na validação
- Compatibilidade: Events funcionam com ferramentas CloudEvents padrão
- Documentação: Score 9/10 em avaliação de clareza por desenvolvedores
- Performance: Serialização ≤ 10ms P95

### Dependências
- Domain events existentes (`src/domain/events.py`)
- JSON Schema validation library
- CloudEvents specification research

---

## US-1.2: Transformação de Eventos Domínio → Integração
**Story Points: 4** | **Prioridade: P0** | **Sprint: 1**  

> **Como** arquiteto de sistema,  
> **Eu quero** separar eventos de domínio dos eventos de integração,  
> **Para que** mudanças internas não quebrem integrações externas.

### Valor de Negócio  
Desacopla evolução interna do sistema das APIs públicas, reduzindo breaking changes em 80%.

### Critérios de Aceite
- [ ] **Event Transformer Service:** Converte domain events para integration events
- [ ] **Mapeamento configurável:** Rules para transformação JobCreatedEvent → job.submitted
- [ ] **Enrichment de dados:** Adiciona metadados necessários para integração (tenant info, timestamps)
- [ ] **Filtering por tenant:** Apenas eventos relevantes para cada tenant são processados
- [ ] **Error handling:** Falhas na transformação não afetam domain event processing
- [ ] **Schema evolution:** Suporte para múltiplas versões de integration events
- [ ] **Performance:** Transformação assíncrona para não bloquear domain operations

### Critérios de Sucesso
- Breaking changes: 0 breaking changes em mudanças de domain events
- Throughput: 1000+ eventos/segundo processados
- Latência: P95 ≤ 100ms para transformação
- Reliability: 99.9% de eventos transformados com sucesso

### Dependências  
- US-1.1 (CloudEvents Schema)
- Existing EventBus port
- Domain events infrastructure

---

## US-1.3: Sistema de Delivery com Webhooks 
**Story Points: 5** | **Prioridade: P0** | **Sprint: 2**

> **Como** marketplace manager,  
> **Eu quero** receber notificações automáticas de mudanças nos jobs,  
> **Para que** meu sistema possa reagir imediatamente sem polling.

### Valor de Negócio
Elimina 90% das consultas desnecessárias por polling, reduzindo carga do sistema e melhorando experiência.

### Critérios de Aceite  
- [ ] **Webhook configuration:** Tenants configuram endpoints via API `/api/v1/tenants/{id}/webhooks`
- [ ] **HTTP delivery:** POST requests com CloudEvents payload  
- [ ] **Signature verification:** HMAC-SHA256 para autenticidade (header `X-ValidaHub-Signature`)
- [ ] **Retry policy:** 3 tentativas com backoff exponencial (1s, 4s, 16s)
- [ ] **Circuit breaker:** Webhook disabled após 10 falhas consecutivas  
- [ ] **Timeout:** 30 segundos timeout por request
- [ ] **Status tracking:** Logs de delivery success/failure por webhook
- [ ] **Multi-tenant isolation:** Webhooks isolados por tenant_id

### Critérios de Sucesso
- Delivery success rate: 99.5% dos webhooks entregues com sucesso
- Latência P95: ≤ 2 segundos do evento até delivery
- Zero cross-tenant webhook deliveries em testes de segurança  
- Customer satisfaction: 95%+ satisfaction com reliability

### Dependências
- US-1.2 (Event Transformation)  
- HTTP client with retry/circuit breaker
- Webhook management API endpoints

---

## US-1.4: Configuração de Webhooks por Tenant
**Story Points: 3** | **Prioridade: P1** | **Sprint: 2**

> **Como** desenvolvedor de marketplace,  
> **Eu quero** configurar múltiplos webhooks com filtros específicos,  
> **Para que** diferentes sistemas recebam apenas os eventos relevantes.

### Valor de Negócio
Reduz ruído em 85% e permite arquiteturas microservices onde cada serviço recebe apenas eventos necessários.

### Critérios de Aceite
- [ ] **CRUD API:** Endpoints completos para webhook management  
- [ ] **Event filtering:** Tenants escolhem quais event types receber (`job.*`, `job.completed`, etc.)
- [ ] **Multiple endpoints:** Até 10 webhooks por tenant com configs independentes  
- [ ] **Authentication config:** Support para Bearer token, Basic Auth, ou custom headers
- [ ] **Environment separation:** Webhooks diferentes para staging/prod
- [ ] **Test webhook:** Endpoint para testar configuração com sample event
- [ ] **Audit trail:** Logs de todas mudanças em webhook configuration

### Critérios de Sucesso  
- Configuration time: ≤ 5 minutos para setup completo
- Test success rate: 100% dos test webhooks funcionam corretamente
- Support tickets: ≤ 2 tickets/mês relacionados a webhook config
- Adoption rate: 80% dos enterprise customers configuram webhooks

### Dependências
- US-1.3 (Webhook Delivery System)
- Tenant management system  
- API authentication middleware

---

## US-1.5: Event Replay para Recovery
**Story Points: 4** | **Prioridade: P1** | **Sprint: 3**

> **Como** DevOps engineer de um marketplace,  
> **Eu quero** replay eventos perdidos durante downtime,  
> **Para que** meu sistema possa se recuperar sem perda de dados.

### Valor de Negócio
Elimina 100% das perdas de dados durante incidents, evitando inconsistências críticas e retrabalho manual.

### Critérios de Aceite
- [ ] **Event store:** Todos integration events salvos com TTL de 30 dias
- [ ] **Replay API:** Endpoint `POST /api/v1/events/replay` com time range filtering  
- [ ] **Batch replay:** Até 1000 eventos por request com rate limiting
- [ ] **Status tracking:** Progress indicator e completion notification
- [ ] **Duplicate prevention:** Replay events marcados com `replayed: true` no metadata
- [ ] **Access control:** Apenas tenant owners podem fazer replay dos próprios eventos
- [ ] **Audit logging:** Todos replays logados para compliance

### Critérios de Sucesso
- Recovery time: ≤ 15 minutos para replay de 1 dia de eventos
- Accuracy: 100% dos eventos replayados são idênticos aos originais  
- Zero data loss: Nenhum evento perdido durante replay process
- Customer satisfaction: 100% dos customers conseguem recover após incidents

### Dependências  
- US-1.3 (Webhook Delivery)
- Event storage infrastructure (PostgreSQL + indexes)
- Rate limiting service

---

## US-1.6: Monitoramento e Alertas de Delivery
**Story Points: 3** | **Prioridade: P1** | **Sprint: 3**

> **Como** SRE do ValidaHub,  
> **Eu quero** visibilidade completa da saúde dos webhooks,  
> **Para que** eu possa identificar problemas antes de afetar customers.

### Valor de Negócio  
Reduz MTTR de incidents de 2 horas para 15 minutos através de detecção proativa e alertas precisos.

### Critérios de Aceite
- [ ] **Métricas Prometheus:** Success rate, latency, error count por webhook endpoint
- [ ] **Dashboard Grafana:** Real-time visibility de webhook health por tenant
- [ ] **Alerting rules:** Slack alerts quando success rate < 95% ou latency > 5s
- [ ] **Health checks:** Automated testing de webhook endpoints (daily)
- [ ] **Customer-facing status:** Webhook status disponível em tenant dashboard  
- [ ] **Historical reporting:** Weekly reports com statistics e trends
- [ ] **Circuit breaker alerts:** Notifications quando webhooks são disabled

### Critérios de Sucesso
- Mean Detection Time: ≤ 2 minutos para identificar webhook failures
- False positive rate: ≤ 5% dos alerts são false positives
- Customer awareness: 90% dos webhook issues detectados antes de customer report
- SLA compliance: 99.9% uptime visibility através de monitoring

### Dependências
- US-1.3 (Webhook Delivery System)  
- Prometheus + Grafana stack
- Alerting infrastructure (Slack/PagerDuty)

---

## US-1.7: Rate Limiting e Throttling Inteligente  
**Story Points: 4** | **Prioridade: P1** | **Sprint: 4**

> **Como** platform reliability engineer,  
> **Eu quero** rate limiting inteligente baseado em tenant tier e webhook performance,  
> **Para que** webhooks lentos não afetem a performance geral do sistema.

### Valor de Negócio
Protege plataforma contra webhook endpoints problemáticos, mantendo P95 latency ≤ 2s mesmo com integrações lentas.

### Critérios de Aceite  
- [ ] **Tier-based limits:** Basic (10/min), Pro (100/min), Enterprise (1000/min)
- [ ] **Adaptive throttling:** Rate reduzido automaticamente se webhook P95 > 10s
- [ ] **Queue management:** Separate queues por tenant tier com priority scheduling
- [ ] **Backpressure handling:** Elegant degradation quando queues ficam cheias
- [ ] **Burst allowance:** Permits short bursts 2x normal rate para event spikes  
- [ ] **Customer notifications:** Emails quando rate limiting é ativado
- [ ] **Override capability:** Support pode temporariamente aumentar limits

### Critérios de Sucesso
- Platform stability: 99.9% uptime mesmo com problematic webhooks
- Fair resource usage: Nenhum tenant consome > 20% dos webhook resources  
- Customer satisfaction: ≤ 3 complaints/mês sobre rate limiting
- Performance maintenance: P95 webhook processing latency ≤ 2s

### Dependências  
- US-1.3 (Webhook Delivery)
- Redis for rate limiting counters
- Queue infrastructure (Redis/RabbitMQ)

---

## Sequência de Implementação

### Sprint 1 (Semanas 1-2): **Foundation**
- US-1.1: CloudEvents Schema ✅
- US-1.2: Event Transformation ✅

**Valor entregue:** 40% da redução de coupling - eventos padronizados e desacoplados

### Sprint 2 (Semanas 3-4): **Core Delivery**  
- US-1.3: Webhook Delivery System ✅
- US-1.4: Webhook Configuration ✅  

**Valor entregue:** 70% da redução de coupling - delivery reliability completo

### Sprint 3 (Semanas 5-6): **Operational Excellence**
- US-1.5: Event Replay ✅
- US-1.6: Monitoring & Alerting ✅

**Valor entregue:** 85% da redução de coupling - recovery e visibilidade

### Sprint 4 (Semanas 7-8): **Enterprise Grade**  
- US-1.7: Rate Limiting & Throttling ✅

**Valor entregue:** 95% da redução de coupling - proteção e fairness

## Métricas de Sucesso do Epic

### Redução de Coupling (Meta: 70%)
- **Baseline atual:** 15 horas médias para integração B2B
- **Meta Sprint 2:** 4.5 horas médias (70% redução)
- **Meta Sprint 4:** 2.25 horas médias (85% redução)

### Reliability 
- **Webhook delivery success rate:** >99.5%
- **Event replay success rate:** 100%  
- **Zero data loss:** Durante incidents ou maintenance

### Developer Experience
- **Integration time:** ≤ 4 horas para setup completo
- **Documentation clarity:** Score >9/10  
- **Support tickets:** ≤ 5 tickets/mês integration-related

### Business Impact
- **Customer satisfaction:** >95% com reliability
- **Revenue risk mitigation:** R$ 3.5M+ através de integrations estáveis
- **Competitive advantage:** 80% faster onboarding vs competitors