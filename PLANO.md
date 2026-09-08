# Plano de desenvolvimento — SMEDocs

Documento vivo. Atualizar ao fim de cada fase.

## Objetivo

Reduzir a diagramação de material pedagógico a três passos: subir o Word, conferir o
que a máquina não teve certeza, exportar o PDF.

## Escopo

Entra nesta primeira versão apenas **apostila de banco de questões**, que é o caso mais
difícil e o que já tem documento de referência real. Provas, relatórios e material
didático reaproveitam o mesmo pipeline depois — só muda o template de saída.

## Decisões técnicas

| Necessidade | Escolha | Motivo |
|---|---|---|
| Validação de dados | Pydantic v2 | Equivalente do Zod. Já instalado. Nativo no FastAPI |
| ORM e migrações | SQLModel + Alembic | Mesmo autor do FastAPI. É SQLAlchemy 2.0 com base Pydantic, então o mesmo modelo serve de tabela e de schema de API |
| Banco | SQLite no app, Postgres 17 no desenvolvimento | Ver nota abaixo |
| Leitura de `.docx` | Walker OOXML próprio | Docling descarta as 539 fórmulas WMF |
| Leitura de PDF/PPTX/HTML | Docling | Rápido e bom nesses formatos |
| Renderização de PDF | `webContents.printToPDF()` do Electron | O template de referência já foi feito assim. Zero dependência nova |
| Saída em DOCX | `python-docx` com estilos nomeados | Versão de trabalho, para ajuste manual. Estilo nomeado permite reformatar tudo de uma vez |
| Fontes | Embutidas no DOCX e servidas localmente no HTML | Baloo 2 e Nunito não estão instaladas nas máquinas; sem isso o Word substitui e o arquivo não lembra o template |
| CLI | `typer` + `rich` | Já instalados. Interativo sem argumento, direto com argumento — o padrão do opencode |
| Template | Jinja2 sobre CSS extraído do `.dc.html` | O fonte tem estilo inline, precisa ser componentizado |
| Empacotamento | PyInstaller onedir + electron-builder NSIS | Instalador único, máquina sem Python |

### Nota sobre o banco

O Postgres 17 na sua máquina serve bem para desenvolver. Mas o aplicativo final não
deve depender dele: exigiria instalar e manter um servidor Postgres em toda máquina que
rodar o app, o que transforma um instalador de desktop num projeto de infraestrutura.

SQLite resolve o caso real — um usuário por vez, leitura pesada, escrita leve. O banco
inteiro é um arquivo em `app.getPath('userData')`, e backup é copiar esse arquivo.

Como o SQLModel abstrai os dois, a decisão não é irreversível. Se um dia o setor quiser
o acervo compartilhado em rede, troca-se a string de conexão e roda-se a mesma migração
do Alembic contra o Postgres.

### Nota sobre inteligência artificial

Sem orçamento de API, nada no runtime pode chamar LLM. O parsing é 100% determinístico.

Isso não é uma perda grande, porque as regras cobrem bem: 864 questões segmentadas com
conferência cruzada exata, 74% dos gabaritos extraídos automaticamente pela marcação
vermelha. O resto vai para uma **tela de revisão** no Electron, onde você resolve em
lote — a interface mostra a questão renderizada e você clica na alternativa certa.

Assistência de IA continua disponível de graça pelo Claude Code, mas offline: rodar uma
sessão sobre o JSON intermediário para sugerir os 219 gabaritos faltantes, gerar
metadados, revisar. O resultado vira um arquivo que o app importa. O app nunca chama a
API sozinho.

## Arquitetura

```
Electron (janela + Chromium)
   │
   ├─ spawn ──> FastAPI  (PyInstaller onedir, 127.0.0.1 em porta aleatória)
   │               ├─ POST /ingest    recebe o .docx
   │               ├─ GET  /jobs/:id  progresso via SSE
   │               ├─ CRUD /bank      acervo de questões
   │               └─ POST /render    devolve HTML montado
   │
   └─ printToPDF() ──> arquivo final
```

Estado inteiro do lado do Python. O Electron não tem banco nem lógica de negócio —
é janela, upload, revisão e botão de exportar.

## Pipeline

Cinco estágios. Cada um grava seu artefato em disco antes de passar adiante, para que
depurar seja abrir um JSON e não recolocar `print` no meio do código.

**1. Extract** — `.docx` → IR (representação intermediária)

Percorre `word/document.xml` em ordem, emitindo blocos tipados: parágrafo, imagem,
objeto OLE, tabela. Guarda alinhamento, negrito, cor de fonte e `w:extent` em EMU.
A cor de fonte é o que carrega o gabarito, então não pode ser descartada.

Saída: `ir.json` + pasta `assets/`.

**2. Media** — normaliza as imagens

PNG e JPG copiados direto. WMF convertidos via Pillow a 300 DPI, com corte de borda
branca. A altura em EMU vira `em` no CSS, para a fórmula sentar na linha de base do
texto em vez de flutuar.

**3. Segment** — IR → questões

Duas regras combinadas, porque nenhuma funciona sozinha:

- corta em linha de asteriscos (`^\*{3,}$`)
- corta também quando a letra da alternativa reinicia em `A`

Juntas produzem 864 questões, número que bate exatamente com as 864 alternativas `A`
contadas de forma independente. Essa coincidência é a validação de que a segmentação
está correta.

Depois classifica dentro de cada questão: enunciado, origem, imagens, alternativas.
Gabarito sai do parágrafo vermelho que casa com o padrão de alternativa.

**4. Validate** — Pydantic

Regras duras. Toda questão precisa de enunciado não vazio, de 4 ou 5 alternativas com
letras únicas e sequenciais, e de todo asset citado existindo em disco. O que falhar
não é descartado nem corrigido no chute: é marcado `needs_review` e vai para a tela de
revisão.

**5. Render** — questões → PDF

Jinja2 monta o HTML com os componentes extraídos do template. O Electron imprime.

## Fases

### F0 — Prova de conceito · CONCLUÍDA

Sem Electron, sem banco, sem API. `python f0.py` gera `out/apostila.pdf`.

Resultado sobre os descritores 1, 2 e 10:

```
64 questões · 53 com gabarito automático (82%) · 52 sem pendência
46 fórmulas inline · 40 páginas · A4 · producer Skia/PDF m152
extração 0,4s · segmentação 0,1s · conversão de imagem ~60s (fica em cache)
```

O PDF sai com o mesmo `producer` e o mesmo tamanho de página do arquivo de referência,
o que confirma a escolha do Chromium como motor de impressão.

**O que a fase provou:** o extrator próprio recupera as fórmulas que a docling descarta,
e elas aparecem no PDF no lugar certo dentro da frase, inclusive dentro das alternativas.

**O que a fase reprovou e já foi corrigido:** a rasterização do WMF pelo GDI corrompia
as fórmulas com parênteses. Decidido usar o Word como renderizador — todos os PCs do
setor têm Office. Implementado em `wordmath.py`, com queda para o GDI quando o Word não
existe. As 539 fórmulas agora saem fiéis.

### Estado atual

`python smedocs.py gerar <n>` gera a apostila de um descritor. Sobre o documento inteiro:

```
31 descritores · 868 questões · 647 com gabarito (74%) · 619 sem nenhuma pendência
539 fórmulas renderizadas pelo Word (~12s, em cache)
```

Correções de segmentação aplicadas nesta rodada, com o efeito medido no total:

| Defeito | Antes | Depois |
|---|---|---|
| Alternativas empacotadas num parágrafo | 42 questões com 1 opção | resolvido |
| Alternativa A colada no enunciado | 33 letras fora de sequência | 26 |
| Questões coladas (`ABCDBCD`) | 7 letras repetidas | 5 |
| Enunciado sem quebra de parágrafo | títulos grudados na pergunta | resolvido |

Restam 62 questões (7%) com defeito estrutural e 219 sem gabarito. Amostradas, são em
boa parte defeitos do próprio original — destino da tela de revisão, não de mais regra.

### F0.5 — saída em DOCX e linha de comando · CONCLUÍDA

Duas adições fora do plano original, pedidas em uso:

- **Saída em `.docx`** com estilos nomeados do Word, para o material que ainda precisa
  de ajuste manual. Baloo 2 e Nunito vão embutidas dentro do arquivo, então ele abre
  igual em qualquer máquina sem instalar fonte nenhuma.
- **CLI** (`smedocs.py`) com `listar`, `gerar` e `conferir`, mais modo interativo quando
  chamado sem argumento. O `f0.py` foi substituído por ela.

O PDF também deixou de depender da rede: as fontes agora são servidas do próprio
projeto em vez do Google Fonts.

### F1 — Extrator

Walker OOXML completo mais pipeline de mídia. Roda sobre o documento inteiro.

Entrega: `ir.json`, pasta de assets, e um relatório de contagem — parágrafos, imagens
por tipo, objetos OLE, tudo conferindo com os números do `CLAUDE.md`.

### F2 — Parser, modelos e banco

Segmentação, classificação, Pydantic, SQLModel, Alembic. Ingestão dos 31 descritores.

Entrega: banco populado com 864 questões e um relatório do resíduo — quais questões
ficaram `needs_review` e por quê.

### F3 — Renderizador

Extrair os componentes do `.dc.html` para Jinja2 com folha de estilo própria: capa,
chip de seção, cabeçalho de descritor, bloco de questão, figura com legenda, callout,
caixa SAEB/BNCC. Fontes empacotadas localmente, porque o app roda offline.

Aqui entra a skill `impeccable` — uma vez, no design do template, não em runtime.

Entrega: apostila completa em PDF, comparável ao arquivo de referência.

### F4 — API

Endpoints, job assíncrono com progresso por SSE. 864 questões não cabem numa requisição
síncrona.

### F5 — Electron

Casca, spawn do sidecar em porta aleatória com handshake em `/health`, telas de upload,
revisão e exportação. A tela de revisão é onde os 219 gabaritos faltantes são resolvidos.

### F6 — Empacotamento

PyInstaller, electron-builder, instalador NSIS. Testar numa máquina sem Python instalado.

## Riscos

**Dessincronização de assets.** É a falha mais provável e a mais difícil de ver a olho
nu — uma imagem escorrega uma posição e a questão inteira fica errada sem parecer
errada. Blindagem: teste automático comparando contagem de imagens por bloco entre o IR
e o HTML gerado, nas 864 questões.

**Fórmula como imagem rasterizada.** Sem alternativa técnica: Equation 3.0 é OLE
binário. O material impresso fica correto, mas não é acessível a leitor de tela nem
refluível. Dívida registrada, não resolvível nesta arquitetura.

**Tamanho do instalador.** `docling-ibm-models` puxa o torch, o que pode levar o pacote
acima de 2 GB. Como o extrator de `.docx` é próprio, a docling vira opcional — se ela
sair do caminho crítico, o instalador cai para a casa dos 150 MB. Decidir em F1.

**Dependência de Windows.** A renderização de WMF usa GDI via Pillow. Trava o backend
fora do Windows caso um dia isso vire serviço em rede.

**Template de estilo inline.** O `.dc.html` não tem classes CSS. Componentizar é
trabalho de verdade, não recorte. Está dimensionado dentro da F3.

## Próximo passo

Executar a F0.
