# Smart Rules Engine - Agent Prompts

## Feature Overview
Sistema inteligente de regras que aprende com correções manuais e melhora automaticamente as validações do ValidaHub, permitindo criar/editar regras via interface visual, logging estruturado de correções, e sugestões automáticas baseadas em padrões.

---

## 1. DDD Architect Agent

**Contexto:** Precisamos desenhar a arquitetura do Smart Rules Engine seguindo os princípios de Domain-Driven Design e Clean Architecture já estabelecidos no ValidaHub.

**Tarefa:** Projete a arquitetura do Smart Rules Engine considerando:
- Definir os agregados e value objects do domínio de regras (Rule, RuleSet, RuleVersion, CorrectionLog)
- Modelar o ciclo de vida de uma regra (draft → published → deprecated)
- Criar eventos de domínio para mudanças de regras e correções aplicadas
- Definir os bounded contexts entre o engine de regras e o sistema de jobs existente
- Garantir que o domínio de regras permaneça puro sem dependências de framework
- Integração com o sistema existente de JobAggregate e multi-tenancy
- Considerar versionamento semântico das regras e retrocompatibilidade

**Entregáveis esperados:**
- Diagrama de agregados e seus relacionamentos
- Definição de eventos de domínio (RuleCreated, RulePublished, CorrectionLogged)
- Interfaces dos ports necessários (RuleRepository, RuleCompiler, SuggestionEngine)
- Estratégia de versionamento e migração de regras

---

## 2. Backend Dev Agent

**Contexto:** Implementar o backend do Smart Rules Engine com FastAPI, incluindo endpoints para gerenciamento de regras, sistema de logs de correções, e engine de sugestões.

**Tarefa:** Desenvolva a implementação backend considerando:
- Endpoints RESTful para CRUD de regras com idempotência
- Sistema de armazenamento de regras YAML versionadas
- API para logging estruturado de correções manuais com contexto completo
- Endpoint de sugestões baseado em análise de frequência
- Implementação de cache para regras compiladas (Redis)
- Sistema de validação de regras antes da publicação
- Webhook para notificar mudanças de regras
- Rate limiting específico para operações de regras
- Integração com o sistema de jobs existente para aplicar regras

**Entregáveis esperados:**
- Endpoints: POST/GET/PUT /rules, POST /corrections/log, GET /suggestions
- Use cases: CreateRule, PublishRule, LogCorrection, GetSuggestions
- Repository implementations com SQLAlchemy
- Sistema de compilação de YAML para formato executável
- Testes de integração com coverage >80%

---

## 3. Frontend Dev Agent

**Contexto:** Criar interface visual para edição de regras YAML usando Monaco Editor no Next.js 15, com preview em tempo real e validação instantânea.

**Tarefa:** Implemente o editor visual de regras considerando:
- Integração do Monaco Editor com syntax highlighting para YAML
- Preview em tempo real das regras sendo editadas
- Validação instantânea com feedback visual de erros
- Interface drag-and-drop para construção de regras sem código
- Sistema de templates de regras pré-definidas por marketplace
- Histórico de versões com diff visual entre versões
- Dashboard de métricas de efetividade das regras com Chart.js
- Interface para revisar e aplicar sugestões automáticas
- Componentes shadcn/ui para consistência visual
- SSE para atualizações em tempo real de métricas

**Entregáveis esperados:**
- Página /rules/editor com Monaco Editor configurado
- Componente RuleBuilder com interface visual drag-and-drop
- Dashboard /rules/analytics com gráficos de efetividade
- Sistema de notificações para sugestões de regras
- Testes E2E com Playwright

---

## 4. Rule Engine Specialist Agent

**Contexto:** Implementar o sistema de compilação e execução de regras YAML, incluindo o Canonical CSV Model (CCM) e a engine de transformação.

**Tarefa:** Desenvolva o engine de regras considerando:
- Parser YAML robusto com validação de schema
- Compilador de YAML para Intermediate Representation (IR) otimizada
- Sistema de execução de regras com order de precedência
- Implementação do Canonical CSV Model para normalização
- Engine de pattern matching para identificar correções frequentes
- Sistema de versionamento SemVer para rule packs
- Mecanismo de rollback para versões anteriores de regras
- Golden tests para garantir consistência de transformações
- Performance optimization para processar 50k linhas em <3 segundos
- Sistema de A/B testing para comparar efetividade de regras

**Entregáveis esperados:**
- Compilador YAML → IR com otimizações
- Runtime engine com suporte a hot-reload
- Sistema de benchmarking de regras
- Suite de golden tests por marketplace
- Documentação técnica do formato de regras

---

## 5. Database Specialist Agent

**Contexto:** Otimizar o armazenamento e consulta de logs de correções em JSONB no PostgreSQL, garantindo performance para análises de padrões.

**Tarefa:** Projete e otimize o schema de banco considerando:
- Tabela de logs de correções com JSONB para flexibilidade
- Índices GIN/GiST para queries eficientes em JSONB
- Particionamento por tenant_id e data para escalabilidade
- Views materializadas para agregações de frequência
- Estratégia de retenção e arquivamento de logs antigos
- Schema para versionamento de regras com soft delete
- Otimização de queries para análise de padrões (window functions)
- Backup strategy específica para dados de regras
- Migration plan sem downtime

**Entregáveis esperados:**
- Schema otimizado com migrations Alembic
- Índices e constraints apropriados
- Stored procedures para análises complexas
- Documentação de performance tuning
- Scripts de manutenção e vacuum

---

## 6. Telemetry Architect Agent

**Contexto:** Estruturar o sistema de observabilidade para o Smart Rules Engine, incluindo métricas de efetividade, logs estruturados, e eventos para análise.

**Tarefa:** Implemente a telemetria completa considerando:
- Eventos CloudEvents para cada aplicação de regra
- Métricas de efetividade por regra (precision, recall, F1-score)
- Distributed tracing para debug de execução de regras
- Logs estruturados de todas as correções com contexto completo
- Dashboard no Grafana para visualização de métricas
- Alertas para regras com baixa efetividade
- Pipeline de dados para análise offline (Kafka → ClickHouse)
- Instrumentação OpenTelemetry do engine
- Métricas de performance (P50, P95, P99 latency)
- Sistema de feedback loop para melhoria contínua

**Entregáveis esperados:**
- Schema de eventos para rule engine
- Dashboards Grafana configurados
- Alertas Prometheus definidos
- Pipeline de ingestão de eventos
- Documentação de métricas e SLIs

---

## 7. TDD Engineer Agent

**Contexto:** Garantir qualidade e confiabilidade do Smart Rules Engine através de Test-Driven Development e cobertura abrangente de testes.

**Tarefa:** Implemente a estratégia de testes considerando:
- Unit tests para parser e compilador de regras (RED→GREEN→REFACTOR)
- Integration tests para fluxo completo de aplicação de regras
- Contract tests entre rule engine e job processor
- Golden tests para cada marketplace suportado
- Property-based testing para validar invariantes
- Performance tests para garantir SLOs (<3s para 50k linhas)
- Mutation testing para validar qualidade dos testes
- Chaos engineering para resiliência do sistema
- Testes de regressão automatizados para cada release
- Mock strategies para isolar componentes

**Entregáveis esperados:**
- Suite completa de testes com >90% coverage
- Golden test fixtures por marketplace
- Performance benchmarks automatizados
- CI/CD pipeline com gates de qualidade
- Documentação de estratégia de testes

---

## Métricas de Sucesso

### Technical KPIs
- Tempo de compilação de regras: <100ms
- Throughput de processamento: 50k linhas em <3s
- Disponibilidade do engine: 99.9% uptime
- Latência P95 de sugestões: <500ms

### Business KPIs
- Taxa de adoção de sugestões: >60%
- Redução de correções manuais: 40% em 30 dias
- Regras customizadas por cliente: >5
- Tempo médio de criação de regra: <10 minutos

### Quality KPIs
- Code coverage: >85%
- Bugs em produção: <2 por sprint
- MTTR (Mean Time To Recovery): <30 minutos
- Taxa de rollback: <5%