boa — o que você quer é um **ritual rápido** que garanta que cada interação com o Claude seja produtiva e não vire retrabalho. segue um **checklist prático** para colar no topo do seu `claude.md` ou deixar como lembrete no terminal:

---

# ✅ Checklist Pré-Prompt — ValidaHub

### 1. **Objetivo claro**

* [ ] Sei exatamente **o que quero como saída** (ex.: “código completo do caso de uso X”, “teste unitário que cobre Y”, “texto de hero section”).
* [ ] Consigo resumir em **1 frase de ação** → “implementar”, “refatorar”, “gerar doc”, “escrever teste”.

### 2. **Contexto mínimo**

* [ ] Nome da feature/épico (ex.: `SubmitJob`, `Épico 2 – Webhooks`).
* [ ] Arquivos relevantes (caminho no repo).
* [ ] Trecho do **claude.md** ou design anterior (se houver).
* [ ] Decidi se vou colar **artefato anterior** (design, implementação, etc.) ou apenas referenciar arquivo.

### 3. **Formato esperado**

* [ ] Vou pedir saída em formato específico (ex.: “diff + conteúdo completo”, “markdown estruturado”, “lista de bullets com tags”).
* [ ] Sei se quero **output aplicável direto** (código pronto) ou **exploratório** (ideias, brainstorming).

### 4. **Scope controlado**

* [ ] O pedido cobre **1 alvo por vez** (não misturar “crie o caso de uso e o frontend junto”).
* [ ] Se a tarefa é grande, já quebrei em **subtarefas** (design → backend → QA → docs).

### 5. **Telemetria mental**

* [ ] Qual métrica ou regra do playbook isso toca? (idempotência, tenant\_id, golden test, etc.)
* [ ] Sei como vou validar depois (pytest, CI, golden snapshot, leitura humana).

### 6. **Agente certo**

* [ ] Escolhi o agent adequado (architect, backend-dev, qa-engineer, copy-writer, etc.).
* [ ] Se estou em dúvida → começo pelo **master** para roteamento.

### 7. **Saída pronta para reuso**

* [ ] Decidi se vou salvar a saída em `.vh/steps/` (design.md, impl.md, tests.md).
* [ ] Sei qual será o **próximo agent** que vai consumir essa saída.

---

### 🧠 Dica de ouro (mentalidade TDD)

> Pergunte a si mesmo: *“O que vou pedir agora é testável/aplicável em ≤ 30 minutos?”*
> Se não for → quebre em subtarefa antes de mandar pro Claude.


🎯 Objetivo:
[O que eu quero que seja feito — ex.: “implementar caso de uso SubmitJob”]

📂 Contexto:
[Arquivos/caminhos ou artefatos relevantes — ex.: packages/domain/job.py, .vh/steps/job_design.md]

📑 Formato esperado:
[Ex.: diff + conteúdo completo, markdown estruturado, lista de bullets, código pronto]

📏 Escopo:
[Uma única ação — ex.: só backend, só teste, só docs. Se for maior, diga que é a parte 1/3]

🧪 Validação:
[Como vou testar/verificar — ex.: pytest, golden test, CI lint, leitura de copy]

👤 Agent alvo:
[architect | backend-dev | qa-engineer | copy-writer | etc.]

➡️ Próximo passo:
[Quem vai consumir essa saída depois — ex.: backend-dev vai implementar com base nesse design]
