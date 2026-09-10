## MODIFIED Requirements

### Requirement: Handshake com sidecar
The system SHALL sortear porta livre em `127.0.0.1`, expor `getApi` via preload e emitir `smedocs:api-ready` quando o backend responder `/health`; enquanto o FastAPI da F4 não existe, a janela opera plenamente via ponte com o CLI Python (`smedocs.py listar/gerar/conferir/analisar/pendencias/gabarito` como subprocesso).

#### Scenario: Backend ausente (F4 pendente)
- **WHEN** o sidecar ainda não existe
- **THEN** a janela abre normalmente e todas as seções operam via ponte CLI em vez de travar ou indicar API indisponível
