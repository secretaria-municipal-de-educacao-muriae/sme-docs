## Purpose

Reduz tempo e fricção do pipeline atual com cache, ambiente reprodutível e mensagens claras, sem alterar a saída do preset padrão.

## ADDED Requirements

### Requirement: Cache de fórmulas e assets
The system SHALL reaproveitar fórmulas renderizadas pelo Word e assets convertidos quando o `.docx` de origem não mudou (chave nome+tamanho+mtime).

#### Scenario: Segunda execução seguida
- **WHEN** operador gera o mesmo descritor duas vezes sem trocar o docx
- **THEN** a segunda execução pula a renderização Word (~12s) e completa em menos de 1s de extração+montagem

### Requirement: Ambiente Python reprodutível
The system SHALL documentar e instalar via `.venv` as dependências pinadas (`pydantic`, `jinja2`, `pillow`, `pywin32`, `pymupdf`, `typer`, `rich`, `python-docx`) com `smedocs.py --help` funcional.

#### Scenario: Instalação limpa
- **WHEN** operador cria `.venv` e instala as dependências documentadas
- **THEN** `smedocs.py --help` lista os 7 comandos e imports críticos passam

### Requirement: Regressão do preset
The system SHALL manter `imagens_no_bloco == imagens_no_HTML` nas 864 questões e as contagens do preset (868 questões, 647 gabaritos, 619 limpas).

#### Scenario: Validação pós-otimização
- **WHEN** otimização é aplicada
- **THEN** o relatório de conferência mantém as contagens e nenhuma imagem troca de questão
