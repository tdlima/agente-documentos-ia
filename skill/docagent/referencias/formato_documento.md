# Formato do documento (JSON)

Todo documento é um objeto com título, metadados e uma lista de **blocos**. O mesmo
formato serve para qualquer tipo de documento; `scripts/exportar.py` transforma o
JSON em Word, PDF e Markdown com o cabeçalho da organização.

```json
{
  "titulo": "Ofício nº 045/2026/ADM",
  "subtitulo": "",
  "metadados": [
    {"rotulo": "Local e data", "valor": "Montes Claros, 15 de outubro de 2026."},
    {"rotulo": "Assunto", "valor": "Cessão do Ginásio Municipal"}
  ],
  "blocos": [
    {"tipo": "paragrafo", "texto": "Senhora Secretária,"},
    {"tipo": "titulo", "texto": "Resultados"},
    {"tipo": "paragrafo", "texto": "Texto com **negrito** quando necessário."},
    {"tipo": "lista", "itens": ["Primeiro item", "Segundo item"]},
    {"tipo": "lista_numerada", "itens": ["Passo um", "Passo dois"]},
    {"tipo": "tabela", "colunas": ["Indicador", "Julho", "Agosto"],
     "linhas": [["Clientes", "412", "430 (+4,4%)"]]},
    {"tipo": "destaque", "texto": "Observação importante e curta."},
    {"tipo": "assinatura", "texto": "João Lima", "itens": ["Diretor Administrativo"]}
  ],
  "pendencias": ["Informar o endereço do destinatário."]
}
```

## Campos

| Campo | Uso |
|---|---|
| `titulo` | Título principal (obrigatório). |
| `subtitulo` | Linha de referência abaixo do título; pode ficar vazio. |
| `metadados` | Pares `rotulo`/`valor` de identificação: data, número, destinatário, período, participantes... |
| `blocos` | Corpo do documento, na ordem (obrigatório). |
| `pendencias` | O que o usuário precisa conferir ou completar. **Não sai no arquivo**; é mostrado ao usuário. |

## Tipos de bloco

| `tipo` | Campos usados | Observações |
|---|---|---|
| `titulo` | `texto` | Nome de seção. Não numere, a menos que o modelo peça (ex.: etapas com tempo). |
| `paragrafo` | `texto` | Um parágrafo por bloco. Justificado no Word/PDF. |
| `lista` | `itens` | Marcadores. |
| `lista_numerada` | `itens` | Numeração automática. |
| `tabela` | `colunas`, `linhas` | Cada linha com o mesmo nº de células das colunas. Larguras são calculadas automaticamente. |
| `destaque` | `texto` | Caixa com fundo e borda dourada. Use no máximo 1 ou 2 por documento. |
| `assinatura` | `texto` (nome), `itens[0]` (cargo) | Assinaturas consecutivas ficam lado a lado. |

Formatação de texto: apenas `**negrito**`. Não use `#`, `_itálico_`, links ou outro Markdown.
Os caracteres `R$ 1.000` não quebram dentro de tabelas.

## Organização (arquivo opcional `--org`)

```json
{
  "nome": "Empresa Exemplo Ltda.",
  "cnpj": "00.000.000/0001-00",
  "endereco": "Rua das Flores, 100 – Centro",
  "cidade_uf": "Montes Claros/MG",
  "telefone": "(38) 3000-0000",
  "email": "contato@exemplo.com.br",
  "site": "",
  "responsavel": "João Lima",
  "cargo_responsavel": "Diretor Administrativo",
  "segmento": "Serviços"
}
```

Todos os campos são opcionais. Sem `nome` nem logo, o arquivo sai sem cabeçalho institucional.
