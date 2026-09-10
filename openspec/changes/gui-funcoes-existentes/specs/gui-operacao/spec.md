## Purpose

Expõe as funções atuais do backend (listar, gerar, conferir, analisar, pendências, gabarito) em telas operáveis por não-técnicos, sem mudar nenhum comportamento do pipeline ou do CLI.

## ADDED Requirements

### Requirement: Seleção do documento e painel do acervo
The system SHALL permitir escolher o `.docx` de origem via diálogo nativo e exibir o painel do acervo: totais (descritores, questões, com gabarito, fórmulas), a fila do que falta e a tabela de descritores com questões, percentual de gabarito e pendências.

#### Scenario: Abrir com o documento padrão
- **WHEN** operador abre o app com o banco Muriaé em `reference/`
- **THEN** o painel mostra 31 descritores, 868 questões e 74% de gabarito sem exigir nenhuma escolha

#### Scenario: Escolher outro documento
- **WHEN** operador escolhe um `.docx` qualquer pelo diálogo
- **THEN** o painel recarrega para esse arquivo, mantendo o anterior selecionável

#### Scenario: Documento sem descritor reconhecido
- **WHEN** o `.docx` não casa nenhum padrão de cabeçalho
- **THEN** a janela informa que nenhum descritor foi reconhecido e orienta a seção Conferir para diagnóstico

### Requirement: Geração da apostila
The system SHALL gerar a apostila dos descritores escolhidos (um, vários ou todos) em PDF e/ou DOCX, com ou sem gabarito (versão do aluno), e oferecer a abertura de cada arquivo gerado.

#### Scenario: Gerar um descritor em PDF
- **WHEN** operador escolhe o descritor 10 em PDF com gabarito
- **THEN** o sistema gera `out/descritor-10.pdf` e oferece abrir o arquivo

#### Scenario: Gerar tudo nos dois formatos sem gabarito
- **WHEN** operador marca todos os descritores, PDF + DOCX, versão do aluno
- **THEN** o sistema gera os dois arquivos por descritor sem as respostas marcadas

#### Scenario: Falha de geração
- **WHEN** a geração falha por qualquer motivo
- **THEN** a janela exibe mensagem legível com o motivo em vez de travar ou fechar

### Requirement: Conferência e análise de documento novo
The system SHALL exibir o relatório de pendências de um ou mais descritores sem gerar arquivo, e SHALL analisar um `.docx` novo mostrando contagens por regra (separadores, descritores, alternativas A–E, blocos vermelhos) e a validação cruzada, com opção de adotá-lo em `reference/`.

#### Scenario: Conferir sem gerar
- **WHEN** operador confere o descritor 10
- **THEN** a janela mostra o painel de resultado e a tabela de problemas (questão, motivo, início do enunciado)

#### Scenario: Analisar documento novo válido
- **WHEN** operador analisa um `.docx` que segue os padrões do perfil
- **THEN** a janela mostra descritores, questões e o diagnóstico por regra com validação cruzada confirmada

#### Scenario: Adotar documento novo
- **WHEN** operador confirma a adoção após a análise
- **THEN** o arquivo é copiado para `reference/` e passa a ser o documento corrente

### Requirement: Ciclo de gabarito assistido
The system SHALL exportar o lote de questões sem gabarito (texto legível + molde de respostas) e importar o JSON preenchido, mostrando quantas respostas novas entraram e o total acumulado.

#### Scenario: Exportar lote
- **WHEN** operador exporta 20 pendências
- **THEN** a janela informa a quantidade do lote e oferece abrir o texto e o molde

#### Scenario: Importar respostas
- **WHEN** operador importa o JSON preenchido
- **THEN** a janela mostra respostas novas, total antes/depois e confirma o destino versionado

#### Scenario: Nenhuma pendência
- **WHEN** todas as questões têm gabarito
- **THEN** a janela informa que não há pendência em vez de gerar lote vazio

### Requirement: Progresso, erro e operação offline
The system SHALL indicar progresso durante operações longas sem travar a janela, SHALL exibir erros do backend em linguagem legível e SHALL funcionar plenamente sem rede.

#### Scenario: Primeira análise longa
- **WHEN** operador analisa o banco cheio pela primeira vez (renderização das fórmulas)
- **THEN** a janela mostra progresso ("analisando…") e permanece responsiva até concluir

#### Scenario: Falha do backend
- **WHEN** uma operação do backend falha
- **THEN** a janela exibe o motivo de forma legível e mantém o estado anterior selecionável

#### Scenario: Operação sem rede
- **WHEN** operador usa o app sem internet
- **THEN** todas as seções funcionam, com fontes e estilos servidos localmente
