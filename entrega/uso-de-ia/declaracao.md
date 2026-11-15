# Declaração de uso de IA

> **Augusto: revise este arquivo antes de enviar.** Os itens marcados com [confirmar] descrevem o que você fez e só você pode confirmar. Ajuste o texto ao que realmente aconteceu.

## Ferramenta e modelo

- **Ferramenta:** Claude (app Claude, modo agente), com acesso à pasta local do projeto pelo app desktop.
- **Modelo:** Claude Opus 5.5 (`claude-opus-5-5`).
- **Ambiente de execução:** Python 3.11.17, pytest 8.3.4 e ruff 0.8.4, num ambiente virtual criado só para rodar os testes.

## O que a IA fez

- Leu o README, o código e os testes, e rodou o baseline (pytest e CLI) antes de qualquer mudança.
- Fez o perfil dos dados de `data/` para ver quais regras eram exercitadas.
- Identificou os 5 defeitos e aplicou uma correção mínima para cada um.
- Propôs e implementou as melhorias de robustez: moeda sem taxa com código 2, moeda em maiúsculas e log no stderr.
- Escreveu os 50 testes novos, o oráculo independente e o teste de mutação.
- Mediu o impacto de cada defeito no dataset real.
- Redigiu o `README-ENTREGA.md`, esta declaração e o log da sessão.

## O que eu fiz

- Defini o objetivo e o papel da IA (engenheiro sênior com visão de negócio e dados) e disponibilizei a pasta do desafio.
- [confirmar] Revisei cada correção e conferi que a causa raiz faz sentido.
- [confirmar] Rodei `pytest -q` e os comandos do README na minha máquina.
- [confirmar] Revisei e ajustei o texto do `README-ENTREGA.md`.
- [confirmar] Criei o repositório público no GitHub e enviei o link pelo formulário.

## Como a sessão foi registrada

O log está em `sessao-01.md`. É um log consolidado de prompts e respostas: traz os prompts na íntegra e as ações, comandos e resultados de cada etapa. [confirmar] Se a ferramenta permitir exportar a conversa no formato nativo, adicione essa exportação nesta pasta também.
