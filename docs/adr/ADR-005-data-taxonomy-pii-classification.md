# ADR-005: Data Taxonomy and PII Classification

- **Status**: Proposed
- **Data**: 2025-08-29
- **Autor**: Architecture Decision Architect

## Contexto

Para transformar ValidaHub em plataforma de inteligência de marketplace, precisamos classificar e anonimizar dados para permitir benchmarking cross-tenant legalmente. Brasil tem LGPD rigorosa, e dados de produtos podem conter informações sensíveis ou identificadores únicos.

Desafios identificados:
- SKUs e GTINs podem identificar sellers específicos
- Títulos e descrições podem conter marcas registradas
- Preços são competitivamente sensíveis
- Dados agregados devem ser úteis mas não identificáveis
- Compliance LGPD + possível expansão internacional (GDPR)

## Alternativas Consideradas

### Opção A: No Data Collection
- **Prós**: Zero compliance risk, simples
- **Contras**: Perde oportunidade de inteligência, sem benchmarking

### Opção B: Full Anonymization 
- **Prós**: Máxima privacidade, compliance garantida
- **Contras**: Dados menos úteis, analytics limitado

### Opção C: Smart Pseudonymization (escolhido)
- **Prós**: Balance privacidade/utilidade, analytics robusto
- **Contras**: Complexidade técnica, requer auditoria regular

## Decisão

Implementar **Smart Pseudonymization** com taxonomia de dados estruturada:

### Data Taxonomy

```yaml
# Data Classification Levels
PUBLIC:          # Pode ser compartilhado sem restrições
  - category_path, marketplace_name, file_format
  - quality_scores, validation_rules_applied

BUSINESS_SENSITIVE: # Agregado OK, individual pseudonimizado  
  - prices, stock_quantities, sales_velocity
  - error_patterns, improvement_metrics

IDENTIFYING:     # Sempre pseudonimizado ou removido
  - sku, gtin, seller_id, brand_specific_terms
  - product_titles (exceto palavras-chave genéricas)

TENANT_SPECIFIC: # Nunca compartilhado cross-tenant
  - tenant_id, job_id, file_names, timestamps específicos
  - contact_info, internal_references
```

### Pseudonymization Strategy

```python
# Consistent hashing para permitir correlação
def pseudonymize_product(product_data, tenant_salt):
    return {
        'product_hash': stable_hash(sku + gtin + tenant_salt),
        'category_l1': product_data.category.split('/')[0],  # "Eletrônicos"
        'price_band': price_to_percentile_band(product_data.price),  # P25-P50
        'quality_indicators': extract_quality_metrics(product_data),
        'marketplace': product_data.channel
    }

# Aggregation thresholds (k-anonymity)
MIN_GROUP_SIZE = 5  # Grupos com <5 products são filtrados
```

## Rationale / Trade-offs

**Por que Smart Pseudonymization:**
- Permite analytics úteis mantendo privacidade
- K-anonymity garante que indivíduos não sejam identificáveis
- Consistent hashing permite correlação temporal sem exposição
- Compliance LGPD com base legal de "interesse legítimo" para analytics agregados

**Trade-offs aceitos:**
- Complexidade técnica da pipeline de anonimização
- Storage overhead para versões pseudonimizadas
- Risco residual de re-identificação em datasets pequenos
- Necessidade de auditoria regular dos dados

## Scope & Boundaries

**In-scope:**
- Classification schema para todos os dados de produto
- Pseudonymization automática na pipeline ETL  
- K-anonymity enforcement (min 5 products por grupo)
- LGPD compliance framework
- Audit trail de decisões de anonimização

**Out-of-scope:**
- GDPR compliance específico (foco inicial Brasil)
- Real-time pseudonymization (batch processing OK)
- Advanced techniques (differential privacy, homomorphic encryption)

## Consequências

### Positivo
- Benchmarking cross-tenant legalmente viável
- Marketplace intelligence sem riscos de compliance
- Base para features premium de insights de mercado
- Confiança de clientes empresariais (data governance)
- Modelo escalável para expansão internacional

### Negativo  
- Pipeline ETL mais complexa (~40% código adicional)
- Storage overhead para dados pseudonimizados
- Potential analytics blind spots em datasets pequenos
- Necessita expertise legal/compliance

### Neutro
- Performance transacional não afetada (batch processing)
- Client APIs permanecem inalteradas

## Tests & Quality Gates

**RED**: Testes de compliance e segurança
- test_pii_never_leaked_to_anonymous_dataset()
- test_k_anonymity_enforced_min_group_size()
- test_pseudonymization_consistent_across_jobs()
- test_lgpd_data_rights_respected() (delete, access, portability)

**GREEN**: Implementação mínima  
- Data classification tags em schemas
- Basic pseudonymization functions
- K-anonymity filter (min_group_size=5)
- LGPD consent management básico

**REFACTOR**: Melhorias futuras
- Advanced anonymization techniques  
- GDPR compliance framework
- Data retention policies automáticas
- Privacy-preserving analytics (differential privacy)

## DDD Anchors

**VO**: DataClassification, PseudonymizedProductId, PrivacyLevel
**Aggregate**: AnonymousProduct, PrivacyAuditLog  
**Service/Ports**: PseudonymizationService, ComplianceAuditService, ConsentManager

## Telemetry & Security

**Metrics/Events:**
- anonymization.products.processed, anonymization.pii.detected
- compliance.audit.violations, consent.requests.processed
- analytics.queries.privacy_safe_only

**Threats/Mitigations:**
- Re-identification attack → K-anonymity + regular audits
- Data leakage → Automated PII detection + schema validation  
- Compliance violation → Legal review + audit trail
- Cross-tenant correlation → Tenant-specific salts + access controls

## Links

- PR: #TBD
- Commit: TBD  
- Issue: #TBD
- Legal Review: TBD

---

_Supersedes:_ N/A
_Superseded by:_ N/A