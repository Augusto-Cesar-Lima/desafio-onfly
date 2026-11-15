# Entrega — Consolidador de reservas de hotel

O CLI tinha **5 defeitos**. Juntos, eles faziam o relatório do cliente mostrar **R$ 193.218,53** em vez de **R$ 396.170,00** de gasto com hotel (−51%), **−1.393** noites em vez de **1.347**, diária média `"0.00"` e um ranking de hotéis invertido. Os 5 foram corrigidos, os 5 testes fornecidos passam sem alteração, e há 50 testes novos.

## Defeitos corrigidos

| # | Defeito | Onde | Causa raiz (uma frase) | Correção |
|---|---|---|---|---|
| D1 | Só as 200 primeiras reservas eram lidas | `repositories/csv_reservation_repository.py` | Um limite fixo (`if len(rows) == 200: break`) interrompia a leitura do CSV. | Remoção do limite: o repositório lê o arquivo inteiro. |
| D2 | Noites erradas, inclusive negativas, na virada de mês/ano | `services/stay_calculator.py` | O cálculo subtraía o dia do mês (`checkout.day - checkin.day`) em vez das datas. | `(checkout - checkin).days * rooms`. |
| D3 | Câmbio invertido e calculado em `float` | `services/currency_converter.py` | A conversão dividia pela taxa em vez de multiplicar e passava por `float`, contrariando a regra de `Decimal`. | `amount * rate` em `Decimal`, sem arredondamento intermediário. |
| D4 | `NO_SHOW` entrava em noites, valores, `by_month` e `top_hotels` | `services/status_policy.py` | A regra era uma lista de exclusão (`status != "CANCELLED"`), então tudo que não fosse `CANCELLED` era faturado. | Lista de permissão: só `CONFIRMED` é faturável. |
| D5 | `top_hotels` mostrava os hotéis de **menor** gasto | `services/report_builder.py` | A ordenação usava o valor em ordem crescente. | Chave `(-total_brl, hotel_id)`: valor decrescente, empate por `hotel_id` crescente. |

### Impacto de cada defeito no dataset real (`data/reservas_hoteis.csv`)

Cada linha reintroduz **um** defeito isolado sobre o código correto e mede o efeito. Isso mostra o que estava em jogo para o cliente, não só para o teste.

| Defeito | Reservas | Noites | Total BRL | Diária média | Top 5 |
|---|---|---|---|---|---|
| Correto | 300 | 1.347 | 396.170,00 | 294,11 | H06, H10, H12, H07, H11 |
| D1 (200 linhas) | 200 | 909 | 249.543,79 (−37,0%) | 274,53 | H10, H06, H12, H08, H03 |
| D2 (dia do mês) | 300 | −1.639 | 396.170,00 | 0,00 | correto |
| D3 (câmbio) | 300 | 1.347 | 237.031,25 (−40,2%) | 175,97 | H10, H09, H12, H07, H11 |
| D4 (NO_SHOW) | 300 | 1.554 | 460.058,83 (+16,1%) | 296,05 | H06, H11, H10, H07, H12 |
| D5 (ordenação) | 300 | 1.347 | 396.170,00 | 294,11 | H05, H04, H03, H01, H02 |
| **Os 5 juntos** | **200** | **−1.393** | **193.218,53 (−51,2%)** | **0,00** | **H04, H05, H02, H08, H12** |

A última linha reproduz **exatamente** o relatório que o CLI original gerava. É a evidência de que esses 5 defeitos explicam todo o erro dos totais e de que não há um sexto escondido.

Por que isso importa no negócio: o total em BRL é a base do faturamento e da conversa sobre economia com o cliente; a diária média é o número que se compara com a política de viagens; e o `top_hotels` é exatamente a lista que um time de negociação usaria para escolher com quais hotéis negociar tarifa. Com o ranking invertido, a negociação começaria pelos hotéis menos relevantes.

### Melhorias de robustez (fora dos testes fornecidos)

- **Moeda sem taxa agora é entrada inválida (código 2).** Antes, um `KeyError` caía no `except Exception` e saía com código 1, "erro inesperado". Agora `MissingExchangeRateError` (subclasse de `InputFileError`) informa a linha e a moeda: `linha 2: moeda sem taxa de câmbio: 'GBP'`.
- **Moeda normalizada em maiúsculas no parser**, como a tabela de câmbio já fazia. Evita que `usd` e `USD` se desencontrem.
- **Log de diagnóstico no stderr**: reservas lidas, contagem por status e quantas são faturáveis. O stdout continua só com a linha de resumo do contrato.

Nada mudou no comando, nos argumentos, no schema do relatório nem nos arquivos de `data/`.

## Como investiguei

1. **README como especificação.** Mapeei cada regra (status, noites, câmbio, exatidão, ordenação, contrato) para o módulo responsável, seguindo o pipeline `ler → converter tipos → contar status → filtrar CONFIRMED → agregar`.
2. **Baseline antes de tocar no código.** `pytest -q` com 5/5 falhando, e o CLI rodado na amostra e no dataset real, com as saídas guardadas. A amostra já denunciava 3 defeitos: noites −33 (esperado 28), total 5.962,41 (esperado 7.566,00) e o hotel H05, que era `NO_SHOW`, no top 5.
3. **Perfil dos dados.** O dataset tem 300 reservas, 3 status, 3 moedas, 93 estadias que cruzam o mês (16 cruzam o ano) e 93 confirmadas em USD/EUR. Isso mostrou que as regras de noites e câmbio afetam muitas linhas, e que o corte em 200 linhas afetava este arquivo.
4. **Leitura do código módulo a módulo** e uma correção mínima por defeito, sem refatorar o que funcionava.
5. **Oráculo independente.** Uma implementação mínima das regras do README, sem importar o pacote, recalcula o relatório direto do CSV. O CLI corrigido bate com ela campo a campo, com `--top` 1, 5, 12 e 50.
6. **Prova inversa.** Reintroduzir os 5 defeitos juntos no oráculo reproduz o relatório quebrado original (tabela acima).
7. **Teste de mutação.** Reintroduzi cada defeito, um por vez, e confirmei que os testes novos falham. Os testes novos sozinhos detectam:

| Mutação reintroduzida | Testes novos que falham |
|---|---|
| D1 corte em 200 linhas | 7 |
| D2 subtração do dia do mês | 12 |
| D3 divisão pela taxa | 9 |
| D3 conta em `float` (mesmo multiplicando) | 2 |
| D4 `NO_SHOW` faturável | 12 |
| D5 ordem crescente | 9 |
| D5 sem desempate por `hotel_id` | 1 |
| Arredondar cada linha antes de somar | 6 |
| Arredondamento bancário (half-even) | 4 |
| Moeda sem taxa saindo com código 1 | 2 |

A mutação do `float` passou despercebida na primeira rodada: `str(float(...))` costuma mascarar o erro. Procurei um valor em que o `float` erra de fato (USD 0,75 × 5,42 = 4,065 exato, que vira 4,0649999… e arredonda para 4,06) e transformei-o em teste.

## Testes adicionados

| Arquivo | Testes | O que cobre |
|---|---|---|
| `tests/test_services_unit.py` | 23 | Noites (mês, ano, bissexto, quartos), câmbio exato em `Decimal`, moeda sem taxa, política de status, arredondamento half-up, leitura acima de 200 linhas |
| `tests/test_cli_contract.py` | 21 | Schema e tipos, formato do dinheiro, `generated_at` em `-03:00`, `by_month` pelo mês do check-in, ranking com desempate, `--top` padrão e limite, arredondamento só na serialização, códigos de saída 0 e 2 |
| `tests/test_reference_data.py` | 6 | Amostra de validação comparada com as tabelas lidas do próprio README, e dataset real comparado com o oráculo e com os números-chave |

Os testes fornecidos não foram alterados.

## Como validar

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

pytest -q

PYTHONPATH=src python -m onfly_report \
  --input data/reservas_hoteis.csv \
  --rates data/taxas_cambio.csv \
  --output output/report.json
# Reservas: 300 | Confirmadas: 235 | Noites: 1347 | Total BRL: 396170.00

PYTHONPATH=src python -m onfly_report \
  --input data/exemplo-validacao.csv \
  --rates data/taxas_cambio.csv \
  --output output/exemplo.json
# Reservas: 12 | Confirmadas: 9 | Noites: 28 | Total BRL: 7566.00

ruff check src tests
```

Relatório do dataset real, depois da correção:

| Campo | Antes | Depois |
|---|---|---|
| `total_reservations` | 200 | 300 |
| `confirmed_reservations` | 153 | 235 |
| `cancelled_reservations` | 22 | 31 |
| `no_show_reservations` | 25 | 34 |
| `total_room_nights` | −1393 | 1347 |
| `total_amount_brl` | 193218.53 | 396170.00 |
| `average_nightly_rate_brl` | 0.00 | 294.11 |
| `top_hotels` | H04, H05, H02, H08, H12 | H06, H10, H12, H07, H11 |

## Resultado do `pytest`

Rodado com Python 3.11.17 e pytest 8.3.4:

```
$ pytest -q
.......................................................                  [100%]
55 passed in 0.96s
```

Só os testes fornecidos:

```
$ pytest -q tests/test_currency.py tests/test_nights.py tests/test_regression_report.py tests/test_status_rules.py tests/test_top_hotels.py
.....                                                                    [100%]
5 passed in 0.15s
```

`ruff check src tests`: sem apontamentos.

## Decisões e pontos em aberto

- **Status fora dos três conhecidos** (ex.: `PENDING`) conta em `total_reservations`, mas não em nenhum contador por status nem nos totais. O README não define esse caso; com a lista de permissão, o padrão seguro é não faturar. Vale alinhar com produto se deveria virar erro de entrada.
- **`checkout` igual ou anterior ao `checkin`** não é validado, porque o README garante dados consistentes. Num cenário de produção, eu validaria isso no parser e devolveria código 2.
- **Formatação:** `ruff format --check` aponta quebras de linha que já existiam em `report_builder.py`. Não reformatei o arquivo para manter o diff focado nos defeitos.
- **Uso de IA:** detalhado em `uso-de-ia/declaracao.md`.

## Arquivos alterados

- `src/onfly_report/repositories/csv_reservation_repository.py` (D1)
- `src/onfly_report/services/stay_calculator.py` (D2)
- `src/onfly_report/services/currency_converter.py` (D3 e moeda sem taxa)
- `src/onfly_report/services/status_policy.py` (D4)
- `src/onfly_report/services/report_builder.py` (D5, log e linha no erro de câmbio)
- `src/onfly_report/services/row_parser.py` (moeda em maiúsculas)
- `src/onfly_report/exceptions.py` (`MissingExchangeRateError`)
- `tests/test_services_unit.py`, `tests/test_cli_contract.py`, `tests/test_reference_data.py` (novos)
