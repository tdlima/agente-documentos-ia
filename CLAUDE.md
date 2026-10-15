# DocAgent — guia para o Claude Code

Agente que redige documentos empresariais (ofício, relatório, PDI, roteiro de
entrevista, avaliação de desempenho, ata, comunicado) e exporta em DOCX/PDF/MD.
Tem duas formas de uso que compartilham o mesmo código:

- **App Streamlit + API do Claude** (`app.py`, `src/docagent/agent.py`)
- **Skill do Claude** (`skill/docagent/`, empacotada por `scripts/empacotar_skill.py`)

## Comandos

```bash
python -m venv .venv && .venv\Scripts\activate     # Windows (Linux/macOS: source .venv/bin/activate)
pip install -e ".[dev]"
streamlit run app.py                                # app (sem ANTHROPIC_API_KEY abre em modo demonstração)
pytest -q                                           # testes; nenhum chama a API
ruff check . && ruff format --check .               # lint (o CI exige os dois)
python scripts/empacotar_skill.py                   # gera dist/docagent.zip
python scripts/exportar_exemplos.py                 # reexporta exemplos/*/ para DOCX/PDF/MD
```

## Arquitetura

- `src/docagent/models.py` — schema `Documento` (título, metadados, blocos, pendências).
  Todos os campos são obrigatórios de propósito: o schema vai para a API como
  *structured output* (`client.messages.parse(output_format=Documento)`), que tem
  limites para campos opcionais. Não adicione campos opcionais nem schemas recursivos.
- `src/docagent/templates/*.yaml` — um arquivo por tipo de documento (campos,
  estrutura, instruções). Novo tipo = novo YAML; nenhuma mudança em Python.
- `src/docagent/prompts.py` — prompt de sistema e montagem do pedido.
- `src/docagent/renderers/` — `markdown.py`, `docx.py`, `pdf.py`; identidade visual
  em `tema.py` (paleta Marinho `#1F2A44` & Latão `#B08D57`).
- `skill/docagent/` — SKILL.md e scripts da skill. O pacote `src/docagent` é copiado
  para dentro dela só no empacotamento; não duplique código em `skill/`.

## Convenções

- Código, nomes e mensagens em português do Brasil.
- `exemplos/*/prompt.md` é comparado com o prompt gerado pelo código
  (`tests/test_exemplos.py`). Se mudar `prompts.py` ou um YAML usado nos exemplos,
  regenere esses arquivos e confira se as respostas de exemplo continuam coerentes.
- No DOCX, elementos OOXML precisam respeitar a ordem do schema (veja `_APOS_PBDR`
  em `renderers/docx.py`); confira o resultado abrindo o arquivo, não só pelos testes.
- Antes de concluir: `pytest -q` e `ruff check . && ruff format --check .` passando.
