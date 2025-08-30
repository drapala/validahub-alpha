# ValidaHub Documentation

Este diretório contém toda a documentação do projeto ValidaHub, organizada por categoria para facilitar navegação e manutenção.

## 📁 Estrutura

### `/adr/` - Architecture Decision Records
Decisões técnicas de arquitetura com impacto de longo prazo no sistema.

### `/architecture/` - Arquitetura e Design
- **[API.md](architecture/API.md)** - Especificação da API e política de idempotência
- **[LOGGING_IMPLEMENTATION.md](architecture/LOGGING_IMPLEMENTATION.md)** - Implementação de logging
- **[LOGGING_STANDARDS.md](architecture/LOGGING_STANDARDS.md)** - Padrões de logging
- **[MULTI_TENANCY_ASSESSMENT.md](architecture/MULTI_TENANCY_ASSESSMENT.md)** - Avaliação multi-tenancy
- **[TELEMETRY_IMPLEMENTATION_GUIDE.md](architecture/TELEMETRY_IMPLEMENTATION_GUIDE.md)** - Guia de telemetria
- **[strategic-epics.md](architecture/strategic-epics.md)** - Épicos estratégicos

### `/compliance/` - Compliance e Regulatório
- **[LGPD_COMPLIANCE_REPORT.md](compliance/LGPD_COMPLIANCE_REPORT.md)** - Relatório de compliance LGPD
- **[LGPD_IMPLEMENTATION_PLAN.md](compliance/LGPD_IMPLEMENTATION_PLAN.md)** - Plano de implementação LGPD

### `/domain/` - Modelagem de Domínio
- **[job-aggregate-design.md](domain/job-aggregate-design.md)** - Design do agregado Job

### `/pdr/` - Product Decision Records
Decisões de estratégia de produto que afetam direção de negócio e experiência do usuário.

### `/product/` - Documentação de Produto
- **[visao_de_produto.md](product/visao_de_produto.md)** - Visão estratégica do produto
- **[product-roadmap.md](product/product-roadmap.md)** - Roadmap detalhado
- **`backlogs/`** - Backlogs de produto
  - **[PRODUCT_BACKLOG_CONSOLIDATED.md](product/backlogs/PRODUCT_BACKLOG_CONSOLIDATED.md)** - Backlog consolidado
  - **[PRODUCT_BACKLOG_LGPD.md](product/backlogs/PRODUCT_BACKLOG_LGPD.md)** - Backlog LGPD
  - **[PRODUCT_BACKLOG_MULTI_TENANCY.md](product/backlogs/PRODUCT_BACKLOG_MULTI_TENANCY.md)** - Backlog multi-tenancy
  - **[backlog-executavel.md](product/backlogs/backlog-executavel.md)** - Backlog executável
- **`epics/`** - Detalhamento de épicos
  - **[epic-1-integration-events-breakdown.md](product/epics/epic-1-integration-events-breakdown.md)** - Epic de eventos de integração

### `/security/` - Segurança
- **[IDEMPOTENCY_KEY_SECURITY_AUDIT.md](security/IDEMPOTENCY_KEY_SECURITY_AUDIT.md)** - Auditoria de segurança
- **[LGPD_COMPLIANCE_TESTS_SUMMARY.md](security/LGPD_COMPLIANCE_TESTS_SUMMARY.md)** - Testes de compliance
- **[SECURITY_FIXES.md](security/SECURITY_FIXES.md)** - Correções de segurança
- **[SECURITY_TEST_IMPLEMENTATION_REPORT.md](security/SECURITY_TEST_IMPLEMENTATION_REPORT.md)** - Relatório de testes

## 📋 Outros Documentos

- **[TECH_DEBT.md](TECH_DEBT.md)** - Registro e tracking de dívida técnica

## 🔗 Navegação Rápida

### Para Desenvolvedores
- [API Specification](architecture/API.md) - Como usar as APIs
- [Security Guidelines](security/) - Padrões de segurança
- [Tech Debt](TECH_DEBT.md) - Itens pendentes

### Para Product Owners
- [Product Vision](product/visao_de_produto.md) - Visão do produto
- [Executable Backlog](product/backlog-executavel.md) - Backlog executável
- [Strategic Epics](architecture/strategic-epics.md) - Épicos estratégicos

### Para Arquitetos
- [Domain Design](domain/) - Modelagem de domínio
- [Architecture Docs](architecture/) - Decisões arquiteturais

## 📝 Convenções

- **Formato**: Markdown (.md) para consistência
- **Idioma**: Português para docs de produto, Inglês para docs técnicos
- **Estrutura**: Cada documento deve ter sumário e seções bem definidas
- **Versionamento**: Docs são versionados junto com o código no Git

## 🔄 Manutenção

Esta documentação deve ser atualizada sempre que:
- Novos features são implementados
- Decisões arquiteturais são tomadas
- Políticas de segurança são alteradas
- Requisitos de compliance são modificados

---

**Última atualização**: 2025-08-29  
**Responsável**: Equipe ValidaHub