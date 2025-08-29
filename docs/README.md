# ValidaHub Documentation

Este diretório contém toda a documentação do projeto ValidaHub, organizada por categoria para facilitar navegação e manutenção.

## 📁 Estrutura

### `/product/` - Documentação de Produto
- **[visao_de_produto.md](product/visao_de_produto.md)** - Visão estratégica e roadmap do produto
- **[backlog-executavel.md](product/backlog-executavel.md)** - Backlog executável com priorização

### `/architecture/` - Arquitetura e Design
- **[strategic-epics.md](architecture/strategic-epics.md)** - Épicos estratégicos e features principais
- **[API.md](architecture/API.md)** - Especificação da API e política de idempotência

### `/security/` - Segurança e Compliance
- **[IDEMPOTENCY_KEY_SECURITY_AUDIT.md](security/IDEMPOTENCY_KEY_SECURITY_AUDIT.md)** - Auditoria de segurança das chaves de idempotência
- **[LGPD_COMPLIANCE_TESTS_SUMMARY.md](security/LGPD_COMPLIANCE_TESTS_SUMMARY.md)** - Resumo dos testes de compliance LGPD
- **[SECURITY_TEST_IMPLEMENTATION_REPORT.md](security/SECURITY_TEST_IMPLEMENTATION_REPORT.md)** - Relatório de implementação de testes de segurança

### `/domain/` - Modelagem de Domínio
- **[job-aggregate-design.md](domain/job-aggregate-design.md)** - Design do agregado Job

### `/backlog/` - Gestão de Produto
- **[product-roadmap.md](backlog/product-roadmap.md)** - Roadmap detalhado do produto

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