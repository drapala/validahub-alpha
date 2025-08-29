# PDR-002: Pricing Inicial

- **Status**: Superseded
- **Data**: 2025-08-29
- **Autor**: PM/BI Visionário

## Contexto

ValidaHub precisa definir modelo de pricing que:
- Seja simples de entender e implementar no MVP
- Permita escalabilidade com diferentes perfis de uso
- Capture valor baseado no volume processado  
- Seja competitivo vs soluções manuais/internas

**ATUALIZAÇÃO 2025-08-29**: Com a evolução para plataforma de inteligência, pricing baseado apenas em volume não captura o valor diferenciado de intelligence features. Este PDR foi **SUPERSEDED** por PDR-005.

Benchmarks do mercado (original):
- Ferramentas de validação: R$ 0,10-0,50 por 1000 linhas
- Tempo manual: 1 hora para 500 linhas = R$ 50/hora
- Soluções enterprise: R$ 2000-5000/mês flat

## Decisão (ORIGINAL - SUPERSEDED)

**~~Pricing por Volume (pay-as-you-use)~~** ← SUPERSEDED por Value-Tiered Model:

### ~~Tiers Iniciais~~ (SUPERSEDED)
- ~~**Starter**: Até 10k linhas/mês - **Gratuito**~~
- ~~**Growth**: Até 100k linhas/mês - **R$ 0,20 por 1k linhas**~~
- ~~**Scale**: 100k+ linhas/mês - **R$ 0,15 por 1k linhas**~~

### ~~Valor Agregado~~ (SUPERSEDED)
- ~~Correções automáticas incluídas~~
- ~~Relatórios detalhados~~
- ~~API access + webhooks~~
- ~~Suporte por email~~

## Nova Direção (Ver PDR-005)

**Value-Tiered Freemium Model**:
- **FREE**: Fix My Catalog (validation-only, 1K products/month)
- **PRO**: Optimize Performance (R$ 49/month, unlimited + benchmarking)  
- **ENTERPRISE**: Strategic Intelligence (R$ 299+/month, predictive analytics)

### Rationale da Mudança
- Volume-based pricing não captura valor de intelligence features
- Network effects criam valor diferenciado que justifica tiers
- Freemium model acelera adoption e cria network data
- Intelligence = premium value proposition vs commodity validation

## Consequências

### Positivo
- Barreira de entrada baixa (tier gratuito)
- Revenue escalável com uso do cliente
- Modelo transparente e previsível
- Competitivo vs soluções manuais (10x+ economia)

### Negativo
- Revenue imprevisível nos primeiros meses
- Clientes podem otimizar uso para pagar menos
- Necessita telemetria precisa de uso

## Alternativas Consideradas

### Flat fee mensal
- **Prós**: Revenue previsível
- **Contras**: Barreira alta, difícil precificar diferentes perfis

### Por projeto/upload
- **Prós**: Simples de entender
- **Contras**: Não captura diferença entre 100 vs 10k linhas

### Freemium com features pagas ← ESCOLHIDO em PDR-005
- **Prós**: Adoção rápida, network effects, valor diferenciado
- **Contras**: Complexidade inicial, cold start para intelligence

---

**Status**: SUPERSEDED por PDR-005 (Value-Tiered Freemium Model)
**Razão**: Volume-based pricing inadequado para plataforma de inteligência