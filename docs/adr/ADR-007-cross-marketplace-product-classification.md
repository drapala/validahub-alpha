# ADR-007: Cross-Marketplace Product Classification

- **Status**: Proposed
- **Data**: 2025-08-29
- **Autor**: Architecture Decision Architect

## Contexto

Para gerar inteligência de marketplace significativa, ValidaHub precisa normalizar e classificar produtos consistentemente across marketplaces. Cada marketplace usa taxonomias próprias: Mercado Livre tem "Eletrônicos > Celulares > Smartphones", Magalu tem "Tecnologia > Telefonia > Celular".

Desafios identificados:
- Taxonomias de categoria incompatíveis entre marketplaces
- Produtos idênticos classificados diferentemente
- Nomes/títulos variados para mesmo produto (iPhone 15 vs iPhone15 vs iPhone 15 Pro)
- GTINs podem estar ausentes ou incorretos
- Benchmarking impossível sem classificação consistente

Oportunidades:
- Product matching permite insights cross-marketplace (preços, qualidade)
- Taxonomia unificada habilita análises por categoria real
- Base para recommendations ("produtos similares têm esses erros comuns")

## Alternativas Consideradas

### Opção A: Marketplace-Specific Classification
- **Prós**: Simples, sem mapeamento complexo
- **Contras**: Analytics fragmentados, sem cross-marketplace insights

### Opção B: Manual Category Mapping
- **Prós**: Precisão alta, controle total
- **Contras**: Não escala, manutenção insustentável

### Opção C: ML-Based Product Classification (escolhido)
- **Prós**: Escala automaticamente, melhora com dados
- **Contras**: Precisão inicial menor, requer training data

## Decisão

Implementar **ML-Based Product Classification** com taxonomia unificada:

### Canonical Taxonomy

```yaml
# Hierarchical Product Taxonomy (3 níveis máximo)
canonical_categories:
  electronics:
    name: "Eletrônicos"
    subcategories:
      smartphones:
        name: "Smartphones"
        attributes: [brand, model, storage_gb, color]
      computers:
        name: "Computadores"  
        subcategories:
          laptops: {name: "Notebooks", attributes: [brand, processor, ram_gb]}
          desktops: {name: "Desktops", attributes: [brand, processor, ram_gb]}
      
  home_garden:
    name: "Casa e Jardim"
    subcategories:
      furniture: {name: "Móveis", attributes: [material, color, dimensions]}
      kitchen: {name: "Cozinha", attributes: [brand, capacity, power_w]}

  # ... etc
```

### Product Matching Strategy

```python
# Multi-signal product classification
class ProductClassifier:
    def classify(self, product_data) -> ClassificationResult:
        signals = self._extract_signals(product_data)
        
        # Signal 1: GTIN lookup (highest confidence)
        if signals.gtin and signals.gtin in gtin_database:
            return self._classify_by_gtin(signals.gtin)
        
        # Signal 2: Title/brand ML classification  
        title_prediction = self.title_classifier.predict(signals.title)
        
        # Signal 3: Marketplace category mapping
        marketplace_hint = self._map_marketplace_category(
            product_data.marketplace, 
            product_data.original_category
        )
        
        # Signal 4: Price-based clustering
        price_category = self._infer_from_price_patterns(
            signals.price, title_prediction
        )
        
        # Ensemble prediction with confidence scores
        return self._ensemble_predict([
            (title_prediction, 0.4),
            (marketplace_hint, 0.3), 
            (price_category, 0.2),
            (self._fallback_heuristics(), 0.1)
        ])
    
    def _extract_signals(self, product) -> ProductSignals:
        return ProductSignals(
            gtin=clean_gtin(product.gtin),
            title=clean_title(product.title),
            brand=extract_brand(product.title, product.brand),
            price=product.price,
            marketplace=product.marketplace,
            original_category=product.category_path
        )
```

### Training Data Sources

```python
# Bootstrap training dataset
training_sources = [
    # High-confidence labeled data
    {"source": "gtin_database", "confidence": 0.95, "size": "~100K products"},
    {"source": "manual_labels", "confidence": 1.0, "size": "~5K products"},
    
    # Medium-confidence heuristic labels  
    {"source": "brand_keywords", "confidence": 0.8, "size": "~50K products"},
    {"source": "price_clustering", "confidence": 0.7, "size": "~200K products"},
    
    # Feedback loop
    {"source": "user_corrections", "confidence": 0.9, "size": "growing"}
]
```

## Rationale / Trade-offs

**Por que ML-Based:**
- Escala automaticamente com novos produtos/marketplaces
- Melhora continuamente com feedback
- Handles edge cases melhor que regras fixas
- Permite classification mesmo com dados incompletos

**Trade-offs aceitos:**
- Precisão inicial ~80% (vs 100% manual)
- Necessita ML expertise e infrastructure
- Model drift requer monitoramento
- False positives podem afetar analytics

## Scope & Boundaries

**In-scope:**
- Taxonomia canônica 3-level hierarchy
- ML classifier para títulos/descrições
- GTIN-based exact matching quando disponível
- Confidence scoring para classificações
- Feedback loop para model improvement

**Out-of-scope:**
- Image-based classification (só texto inicial)
- Real-time classification (batch processing OK)
- Fuzzy product matching (produtos "similares")
- Advanced NLP (embeddings, transformers) na v1

## Consequências

### Positivo
- Cross-marketplace benchmarking viável ("Eletrônicos no ML vs Magalu")
- Insights de categoria: "Smartphones têm 30% mais erros de título"
- Product-level analytics: preços, qualidade, trends
- Foundation para features avançadas (recommendations, alerts)
- Competitive intelligence capabilities

### Negativo
- ML model accuracy não é 100% (80-85% inicial)
- Classificações incorretas podem distorcer analytics
- Model training/serving infrastructure necessária
- Categorical schema evolution requer cuidado

### Neutro
- Não afeta core validation workflow (parallel processing)
- Clients podem ignorar classification data

## Tests & Quality Gates

**RED**: Accuracy e consistency requirements
- test_classification_accuracy_above_80_percent()
- test_cross_marketplace_category_consistency()  
- test_gtin_exact_match_when_available()
- test_confidence_scores_calibrated()

**GREEN**: MVP implementation
- Simple title-based classifier (keyword matching)
- Basic canonical taxonomy (top categories)
- GTIN lookup table (seed data)
- Confidence scoring framework

**REFACTOR**: ML sophistication
- Advanced NLP models (BERT-based)
- Active learning para human-in-the-loop labeling
- Multi-modal classification (text + images)
- Real-time classification pipeline

## DDD Anchors

**VO**: CanonicalCategory, ClassificationConfidence, ProductSignals
**Aggregate**: ClassifiedProduct, CategoryTaxonomy
**Service/Ports**: ProductClassifier, GTINDatabase, ClassificationFeedback

## Telemetry & Security

**Metrics/Events:**
- classification.accuracy.by_category, classification.confidence.distribution
- model.predictions.daily, model.feedback.corrections
- taxonomy.coverage.by_marketplace

**Threats/Mitigations:**
- Model poisoning → Training data validation + adversarial testing
- Classification bias → Regular accuracy audits by demographic
- Category drift → Monitoring for prediction distribution changes
- Performance degradation → Model performance regression tests

## Links

- PR: #TBD
- Commit: TBD
- Issue: #TBD  
- ML Model: TBD
- Training Dataset: TBD

---

_Supersedes:_ N/A
_Superseded by:_ N/A