---
name: docagent
description: Redige documentos empresariais (ofício, relatório, PDI, roteiro de entrevista, avaliação de desempenho, ata, comunicado) e exporta em Word, PDF e Markdown com a identidade da organização.
dependencies: python>=3.10, pydantic>=2.7, python-docx>=1.1, reportlab>=4.0, PyYAML>=6.0
---

# DocAgent — redação de documentos empresariais

Use esta skill quando o usuário pedir para criar, redigir, montar ou revisar um
**ofício, relatório, PDI (plano de desenvolvimento individual), roteiro de
entrevista, avaliação de desempenho, ata de reunião ou comunicado interno**,
ou outro documento corporativo que se encaixe em um desses modelos.

Você é o redator: transforma as informações (muitas vezes soltas, em tópicos)
em um documento completo, estruturado e pronto para uso. Os scripts cuidam
apenas da validação e da formatação dos arquivos.

Todos os comandos abaixo partem da pasta desta skill.

## Fluxo de trabalho

### 1. Identifique o modelo

```bash
python scripts/modelo.py --listar
```

Escolha o modelo pelo pedido do usuário (ex.: "pedido à prefeitura" → `oficio`;
"plano de carreira do colaborador" → `pdi`). Se nenhum servir, use o mais
próximo e adapte a estrutura, avisando o usuário.

### 2. Leia o guia do modelo

```bash
python scripts/modelo.py <id>
```

O guia traz as informações necessárias (`*` = obrigatória), a estrutura esperada
e as instruções específicas (normas, boas práticas). Leia também, uma vez,
`referencias/regras_de_redacao.md`: são as mesmas regras do agente no aplicativo.

### 3. Confira se há informação suficiente

- Faltando uma informação **obrigatória** que muda o documento (ex.: o assunto
  do ofício, os dados do relatório), pergunte ao usuário em uma única mensagem,
  listando tudo o que falta.
- Faltando detalhes secundários (endereço, número do ofício, nome do
  entrevistador), **não pergunte**: siga com um marcador `[assim]` e registre
  em `pendencias`.
- **Organização emissora:** use os dados que o usuário já informou ou um
  `organizacao.json` anexado. Se não houver nenhum, pergunte o nome da
  organização, quem assina e o cargo, ou siga sem cabeçalho se o usuário preferir.
  Se ele anexar um logo, use-o com `--logo`.

### 4. Redija o documento em JSON

Escreva o arquivo `documento.json` no formato de
`referencias/formato_documento.md`, seguindo a estrutura e as instruções do
modelo. Regras essenciais:

- Não invente fatos, números, nomes, datas ou compromissos. Organizar, resumir,
  calcular a partir dos dados e propor boas práticas é esperado.
- Confira as contas (variações, percentuais, totais) com Python antes de
  escrever; não faça contas de cabeça.
- Datas por extenso a partir da data de hoje; tratamento e fecho conforme o modelo.
- O cabeçalho institucional (logo, nome, CNPJ, endereço) é inserido pelo
  exportador: não o repita no corpo.

### 5. Exporte

```bash
python scripts/exportar.py documento.json --org organizacao.json --logo logo.png \
    --formatos docx pdf --saida <pasta de saída>
```

- `--org` e `--logo` são opcionais. Para criar `organizacao.json`, use o formato
  descrito no fim de `referencias/formato_documento.md`.
- Use os formatos que o usuário pedir; o padrão é Word + PDF. `md` gera Markdown.
- Se o script apontar **ERRO**, corrija o JSON e rode de novo. **AVISOS** indicam
  problemas de qualidade que também devem ser corrigidos.
- Salve os arquivos onde o usuário possa baixá-los (a pasta de saída do
  ambiente, quando houver).

### 6. Entregue

- Entregue os arquivos com uma frase curta sobre o documento.
- Liste as **pendências** que o script exibiu: é o que o usuário precisa
  conferir antes de usar.
- Ofereça ajustes. Para revisar, edite o `documento.json` existente (não
  recomece do zero), mantenha o que não foi pedido para mudar e exporte de novo.

## Dependências

Se `pydantic`, `python-docx`, `reportlab` ou `PyYAML` não estiverem instalados:

```bash
pip install pydantic python-docx reportlab PyYAML
```

(Use `--break-system-packages` se o ambiente exigir.)

## Novos tipos de documento

Os modelos ficam em `scripts/docagent/templates/*.yaml`. Para um novo tipo,
copie um YAML existente, ajuste `id`, `nome`, `campos`, `estrutura` e
`instrucoes`, e ele aparece em `modelo.py --listar`.
