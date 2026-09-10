## Context

Ver proposta (`proposal.md`, Why) e specs (`specs/gui-operacao/spec.md`, `specs/electron-shell/spec.md`). Estado atual que molda o desenho: `electron/main.js` já tem a ponte `runCli` (subprocesso `smedocs.py`, `PYTHONIOENCODING=utf-8`, saída em `UI_OUT` no temp) com `pick-docx`, `analyze-docx` (`listar -f json`) e `generate` (`gerar -q`); `preload.js` expõe 7 funções com `contextIsolation`; o renderer tem 3 cards de teste com CSS inline. `backend/` não muda neste change.

## Goals / Non-Goals

**Goals:**
- 4 seções operando de ponta a ponta via ponte CLI, com a janela responsiva durante operações longas.
- Estrutura visual e de navegação decidida (resposta ao pedido: sidebar + seções, sem modais de fluxo).

**Non-Goals:**
- FastAPI/sidecar HTTP, persistência, progresso percentual real (só a F4 destrava isso).
- Flags `-f json` novas no CLI — a ponte consome o que já existe.

## Decisions

### 1. Sidebar fixa + uma seção visível (não modais, não tela única empilhada)
Janela 1200×800 com barra lateral (Início, Gerar, Conferir, Gabarito) e um painel por seção; documento corrente sempre visível no topo. Alternativas: (a) um modal por função — rejeitado porque esconde o progresso de operações de ~60s e empilha estado; (b) tudo empilhado numa rolagem — rejeitado porque os 4 fluxos têm estados distintos e viraria ruído. Só os diálogos nativos de arquivo (já existentes) interrompem; confirmações (ex.: adotar em `reference/`) são inline na seção.

### 2. Estender `runCli`, não criar API
Novos handlers seguem o padrão existente (um IPC por operação, subprocesso por chamada, erro com `código + últimos 500 chars do stderr`). Alternativa — subir FastAPI agora — rejeitada: o pedido é zero backend novo, e `listar -f json` / `gerar -q` já foram feitos para consumo da UI.

### 3. Ponte consome saída existente com parse tolerante + fallback bruto
`listar` e `gerar` já devolvem máquina-legível (JSON / paths em `-q`). Para `conferir`, `analisar`, `pendencias` e `gabarito` (saída humana via rich), a ponte extrai fatos por âncoras estáveis (caminhos após `✓`, `+N novas`, contagens) e, se o parse falhar, mostra a saída bruta em "ver detalhes" em vez de quebrar. Alternativa — novas flags JSON no CLI — rejeitada neste change por tocar o backend; vira follow-up natural da F4, quando tudo será HTTP tipado.

### 4. Renderer sem framework, CSS com variáveis e fontes locais
Seções como funções de render em JS puro (sem React/Vite: peso e build offline injustificáveis para 4 seções); `<style>` inline vira stylesheet com variáveis dos tokens do template; Baloo 2 / Nunito via `@font-face` local (mesmos arquivos de `backend/smedocs/fonts/`). O refinamento visual roda via `/impeccable shape gui-operacao` no início do apply — pode ajustar aparência, não os requisitos.

### 5. Estado em memória, sem persistência
Documento corrente + seção atual vivem no renderer; nada é salvo (sem banco ainda). Concorrência: botões da seção desabilitam durante a operação (um subprocesso por vez no mesmo `UI_OUT`).

## Risks / Trade-offs

- [Parse tolerante quebra se o texto do CLI mudar] → âncoras em marcadores estáveis + fallback "ver detalhes" + checklist manual por seção nos tasks.
- [Subprocesso opaco: sem % real nem cancelamento hoje] → estado indeterminado com tempo esperado ("primeira vez ~1 min"); `main.js` guarda o handle do child para matar em "cancelar" (detalhe no apply).
- [Regressão silenciosa dos contratos `listar -f json` / `gerar -q`] → são do mesmo repo e intocados aqui; verificação manual cobre os 4 fluxos.
- [Dívida assumida] → ponte por subprocesso some na F4; nada dela é reaproveitado além das seções visuais.

## Migration Plan

Substituição única do renderer (sem usuários em prod); rollback é `git revert`. Sem migração de dados, sem mudança de empacotamento.

## Open Questions

- Refinos do `/impeccable shape gui-operacao` (hierarquia, chips de pendência, densidade da tabela) — respondidos no apply, sem mudar specs.
