## Why

Operadores do setor pedagógico e diagramadores hoje dependem do terminal (`smedocs.py` com 7 comandos) para todo o fluxo. A janela Electron abre, mas só tem cards de teste — ela não opera o backend atual. Para tirar o CLI do caminho sem mexer no backend, a janela precisa expor as funções que já existem com UX operável por não-técnicos.

## What Changes

- A janela vira o app operável: navegação lateral (Início, Gerar, Conferir, Gabarito) com um painel principal por seção; fluxos rodam inline na seção, sem modais (só os diálogos nativos de arquivo que já existem).
- A ponte `main.js` deixa de ser "teste" e vira o modo de operação: novos handlers IPC para `conferir`, `analisar` (com diagnóstico por regra), `pendencias` (exportar lote) e `gabarito` (importar respostas), todos chamando o CLI atual como subprocesso.
- O renderer atual (cards de teste com estilo inline) é substituído pelas 4 seções, usando os tokens do template (Baloo 2 / Nunito locais, cores `#1B56C4` / `#123E8F` / `#E63946` / `#3FA34D`) — sem dependência nova, tudo offline.
- O painel `dev` do CLI vira a seção Início (acervo + a fazer + tabela de descritores); o modo interativo do CLI continua intacto.
- **Non-goals (explicitamente fora):** tela de revisão questão-a-questão (F5 completa), Alembic / SQLModel / SQLite, FastAPI / sidecar HTTP, prova-assembly, qualquer mudança no pipeline ou nos comandos do CLI.

## Capabilities

### New Capabilities

- `gui-operacao`: telas de operação da janela sobre as funções CLI existentes (selecionar docx + dashboard do acervo, gerar apostila, conferir/analisar, ciclo pendências→gabarito), com progresso e erro explícitos.

### Modified Capabilities

- `electron-shell`: a ponte CLI vira modo de operação de primeira classe (não placeholder de teste) — o requisito de handshake passa a cobrir operação plena via subprocesso `smedocs.py` mesmo sem o FastAPI da F4.

## Impact

- `electron/main.js` (novos handlers IPC), `electron/preload.js` (novas exposições), `electron/renderer/` (reescrita das seções).
- `backend/` intocado: consumo só via subprocesso; o contrato `listar -f json` / `gerar -q` (feito para a UI) precisa continuar estável.
- Sem dependências novas; app continua offline e Windows-only.
