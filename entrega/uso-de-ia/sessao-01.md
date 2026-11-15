# Sessão 01 — log consolidado de prompts e respostas

- **Ferramenta:** Claude (app Claude, modo agente) · **Modelo:** Claude Opus 5.5
- **Data:** 14/11/2026 (horário de Brasília)
- **Formato:** prompts do usuário na íntegra; respostas e ações da IA resumidas, com os comandos e resultados relevantes.

---

## Contexto anterior na mesma conversa

**Prompt 1 (usuário):**

> https://recruta.onfly.com.br/
>
> Faça um estudo profundo sobre o processo seletivo da Onfly.

**Resposta (IA):** pesquisa sobre o programa Recruta Onfly 2026 (etapas, requisitos, cultura e contexto da empresa) entregue como documento à parte. Não envolveu código deste desafio.

---

## O desafio

**Prompt 2 (usuário):**

> Atue como um software enginner senior com uma ampla visão de negócios e dados.
>
> adicionei a pasta agora, ela é o desafio do processo seletivo. Quero que com de acordo com o estudo feito, você me ajude a resolver esse desafio.

### 1. Reconhecimento

- Listou a pasta e leu `README.md`, `pyproject.toml`, todo o `src/` e todo o `tests/`.
- Percebeu que a pasta não é um repositório git e que a máquina tinha Python 3.10. Criou um ambiente 3.11 à parte (`uv venv --python 3.11`) com `pytest==8.3.4` e `ruff==0.8.4`.

### 2. Baseline (antes de qualquer mudança)

```
$ pytest -q
FAILED tests/test_currency.py::test_currency_conversion_to_brl
FAILED tests/test_nights.py::test_nights_across_month_boundary - assert -28 == 3
FAILED tests/test_regression_report.py::test_regression_report_on_sample
FAILED tests/test_status_rules.py::test_status_rules_exclude_cancelled_and_no_show
FAILED tests/test_top_hotels.py::test_top_hotels_are_ranked_descending
5 failed

$ python -m onfly_report --input data/exemplo-validacao.csv ...
Reservas: 12 | Confirmadas: 9 | Noites: -33 | Total BRL: 5962.41

$ python -m onfly_report --input data/reservas_hoteis.csv ...
Reservas: 200 | Confirmadas: 153 | Noites: -1393 | Total BRL: 193218.53
```

Leitura: a amostra esperava 28 noites e R$ 7.566,00. O hotel H05 (`NO_SHOW`) aparecia no top 5. O dataset tem 300 linhas, mas só 200 eram lidas.

### 3. Perfil dos dados

- 300 reservas: 235 `CONFIRMED`, 31 `CANCELLED`, 34 `NO_SHOW`.
- Moedas BRL, USD e EUR, todas com taxa; 93 confirmadas em moeda estrangeira.
- 93 estadias cruzam o mês e 16 cruzam o ano; nenhum `checkout <= checkin`.
- Um nome por `hotel_id`, sem IDs duplicados, valores com 2 casas, sem negativos e sem BOM.

### 4. Defeitos encontrados na leitura do código

| # | Arquivo | Trecho original | Problema |
|---|---|---|---|
| D1 | `csv_reservation_repository.py` | `if len(rows) == 200: break` | Corta a leitura em 200 linhas |
| D2 | `stay_calculator.py` | `(checkout.day - checkin.day) * rooms` | Ignora mês e ano |
| D3 | `currency_converter.py` | `Decimal(str(float(amount) / float(rate)))` | Divide em vez de multiplicar, e usa `float` |
| D4 | `status_policy.py` | `return status != "CANCELLED"` | `NO_SHOW` vira faturável |
| D5 | `report_builder.py` | `key=lambda item: (item[1]["amount"], item[0])` | Ordem crescente |

### 5. Correções

Uma correção mínima por defeito: remoção do limite; `(checkout - checkin).days * rooms`; `amount * rate` em `Decimal`; lista de permissão `{"CONFIRMED"}`; chave `(-amount, hotel_id)`.

Robustez extra:

- `MissingExchangeRateError(InputFileError)` para moeda sem taxa, com código 2 e a linha na mensagem.
- Moeda em maiúsculas no parser.
- Log de contagens no stderr.

```
$ pytest -q
.....
5 passed
```

### 6. Validação independente

- Escreveu um oráculo que recalcula o relatório direto do CSV, sem importar o pacote. O resultado foi igual ao do CLI no dataset real e na amostra.
- Reintroduziu os 5 defeitos no oráculo, um por vez e todos juntos. Os 5 juntos reproduziram exatamente o relatório quebrado (200 / −1393 / 193218.53 / 0.00), o que descarta um sexto defeito nos totais.
- Mediu o impacto isolado de cada defeito: D1 −37,0% no total; D3 −40,2%; D4 +16,1%; D2 noites negativas e média 0,00; D5 ranking invertido.

### 7. Testes novos e mutação

- Criou `test_services_unit.py`, `test_cli_contract.py` e `test_reference_data.py`. Este último lê as tabelas da amostra direto do README e compara o dataset real com o oráculo.
- No teste de mutação (cada defeito reintroduzido numa cópia do projeto), todos foram detectados, exceto "câmbio em float multiplicando". Uma busca achou USD 0,75 × 5,42 = 4,065 exato (4,07), que em `float` vira 4,0649999… (4,06). O caso foi adicionado como teste e a mutação passou a ser detectada.

```
$ pytest -q
.......................................................                  [100%]
55 passed in 0.96s
$ ruff check src tests
All checks passed!
```

### 8. Entrega

- Escreveu `entrega/README-ENTREGA.md` com defeitos, causa raiz, investigação, impacto no negócio, como validar e o resultado do pytest.
- Escreveu esta pasta `uso-de-ia/` (declaração e este log).
- Deixou a criação do repositório público e o envio do link para o usuário, que tem as credenciais do GitHub.
