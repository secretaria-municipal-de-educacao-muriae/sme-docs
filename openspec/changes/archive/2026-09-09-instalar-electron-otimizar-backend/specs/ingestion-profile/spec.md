## Purpose

Permite diagramar qualquer `.docx` pedagógico configurando as regras de parsing, mantendo o banco Muriaé como preset padrão reprodutível.

## ADDED Requirements

### Requirement: Perfil de ingestão parametrizado
The system SHALL parse o `.docx` a partir de um `IngestionProfile` (delimitador, cabeçalho descritor/seção, padrões de alternativa inline e de bloco, origem, cores de gabarito, limpeza) em vez de constantes fixas.

#### Scenario: Parse com preset padrão
- **WHEN** usuário roda `listar`/`gerar` sem `--perfil`
- **THEN** o sistema usa `profiles/banco-muriae.json` e produz saída idêntica à atual (31 descritores, 868 questões, 647 gabaritos)

#### Scenario: Regex inválido rejeitado
- **WHEN** usuário fornece perfil com regex inválido
- **THEN** o sistema rejeita com mensagem indicando o campo e não inicia a extração

### Requirement: Diagnóstico de ingestão
The system SHALL exibir por regra quantos blocos casaram (separadores, descritores, alternativas A–E) e quais questões cairiam em `needs_review` com o motivo.

#### Scenario: Analisar docx novo
- **WHEN** usuário roda `analisar novo.docx --perfil X`
- **THEN** o sistema mostra contagens por regra e a validação cruzada (nº de `A` vs nº de questões)

### Requirement: Preset versionado
The system SHALL versionar `profiles/*.json` no repositório e ignorar `reference/` e `out/`.

#### Scenario: Reprodutibilidade
- **WHEN** outro operador usa o mesmo perfil + mesmo docx
- **THEN** obtém as mesmas questões e contagens
