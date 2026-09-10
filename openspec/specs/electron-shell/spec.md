## Purpose

Entrega a janela desktop instalável do SMEDocs com impressão PDF fiel ao template Chromium e pronta para o sidecar Python.

## Requirements

### Requirement: Janela Electron reprodutível
The system SHALL abrir via `npm start` em `electron/` uma janela (1200x800) carregando `renderer/index.html` com `contextIsolation` ativo e sem `nodeIntegration`.

#### Scenario: Abrir app em dev
- **WHEN** operador roda `npm install` seguido de `npm start`
- **THEN** a janela abre sem erro de módulo e exibe o estado da API

### Requirement: Impressão PDF pelo Chromium
The system SHALL gerar PDF A4 via `webContents.printToPDF()` com margens 0.55in e fundo impresso.

#### Scenario: Exportar PDF de teste
- **WHEN** operador clica em imprimir e escolhe o destino
- **THEN** o sistema salva o PDF no caminho escolhido e informa o caminho, ou retorna cancelado sem erro

### Requirement: Handshake com sidecar
The system SHALL sortear porta livre em `127.0.0.1`, expor `getApi` via preload e emitir `smedocs:api-ready` quando o backend responder `/health`.

#### Scenario: Backend ausente (F4 pendente)
- **WHEN** o sidecar ainda não existe
- **THEN** a janela abre normalmente indicando API indisponível em vez de travar
