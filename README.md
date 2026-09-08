# SMEDocs

Converte documentos Word desorganizados enviados pelo setor pedagógico em material
diagramado — provas, apostilas, relatórios e material didático.

Secretaria Municipal de Educação de Muriaé.

## Situação

Fase F0 concluída: script Python que lê o banco de questões em `.docx` e gera a
apostila de um descritor em PDF, com a diagramação do template oficial.

Ainda **não** existe interface. Electron, banco de dados e API estão planejados nas
fases seguintes — ver [PLANO.md](PLANO.md).

```
31 descritores · 868 questões · 647 com gabarito automático (74%)
619 questões sem nenhuma pendência · 539 fórmulas de matemática renderizadas
```

## Requisitos

- Windows (o pipeline usa GDI e automação COM do Word)
- Python 3.13
- Microsoft Word — renderiza as fórmulas de matemática com fidelidade
- Google Chrome ou Microsoft Edge — imprime o PDF

```bash
pip install pydantic jinja2 pillow pywin32 pymupdf
```

## Uso

Os documentos de origem não estão versionados. Coloque-os em `reference/`:

```
reference/
  APOSTILA BANCO DE QUESTÕES POR DESCRITOR ATE 31.docx
```

Depois:

```bash
python f0.py            # descritor 1
python f0.py 10         # descritor 10
python f0.py 1 2 10     # os três no mesmo PDF
```

A saída vai para `out/descritor-<n>.pdf`.

Na primeira execução o Word é chamado uma vez para renderizar as 547 fórmulas; leva
cerca de 12 segundos e fica em cache. As execuções seguintes levam menos de 1 segundo.

## Como funciona

```
.docx ──> extract ──> media ──> segment ──> validate ──> render ──> .pdf
          │           │         │           │            │
          │           │         │           │            └ Jinja2 + Chromium
          │           │         │           └ Pydantic
          │           │         └ descritores, questões, alternativas, gabarito
          │           └ WMF/OLE via Word, PNG e JPG direto
          └ percorre word/document.xml na ordem do documento
```

| Módulo | Papel |
|---|---|
| `backend/smedocs/extract.py` | Lê o `.docx` para uma representação intermediária |
| `backend/smedocs/wordmath.py` | Renderiza as fórmulas OLE usando o Word |
| `backend/smedocs/media.py` | Normaliza imagens para PNG |
| `backend/smedocs/segment.py` | Recupera a estrutura que o Word não tem |
| `backend/smedocs/models.py` | Contratos e validação em Pydantic |
| `backend/smedocs/render.py` | Monta o HTML e imprime o PDF |

## Duas decisões que não são óbvias

**A docling não é usada para `.docx`.** Ela converte o arquivo em 15 segundos, mas o
backend DOCX dela não percorre `w:object` nem `v:imagedata` e descarta em silêncio as
539 fórmulas de matemática, deixando 369 parágrafos com buraco no meio da frase. Por
isso o extrator é próprio.

**As fórmulas são renderizadas pelo Word, não pelo Windows.** O `.docx` guarda uma
prévia em WMF de cada fórmula, e rasterizar essa prévia com o GDI empilha os glifos de
toda fórmula que tenha parênteses. O Word desenha a partir do objeto OLE e acerta.

Os detalhes de ambas, com as medições, estão em [CLAUDE.md](CLAUDE.md).
