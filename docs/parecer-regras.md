# Regras do parecer do engenheiro: R00, R02, R03, R05

Implementadas em `app/core/parecer/` (Dev B, 07/11), com os casos do parecer como
testes em `app/core/parecer/tests/`. Cada módulo expõe `avaliar(processo) ->
ResultadoRegra` completo, já com `alertas`, `premissas` e `evidencias` (campos
novos do contrato, commit 8ffde62). Nada em `app/core/regras.py` foi alterado.

| Regra | Módulo | O que decide |
|---|---|---|
| R00 | `r00_potencia.py` | Potência do inversor <= potência disponibilizada pelo disjuntor do padrão (tabela monofásica da Enel). Roda antes de R02 e R03. |
| R02 | `r02_cabo.py` | Ib <= In <= Iz corrigido (NBR 5410 Tab. 36, fatores de temperatura e agrupamento), restrições do manual, queda de tensão (>4% reprova, >2% alerta). |
| R03 | `r03_strings.py` | Voc no frio pelo β do datasheet (tabela em paralelo só alerta), Tmin por área, Isc por MPPT, janela do MPPT (alerta). |
| R05 | `r05_inmetro.py` | Cascata: consulta INMETRO por número -> catálogo verificado -> registro ativo sem tensão + datasheet (engenheiro confirma) -> inativo/modelo ausente reprova. |

## Integração (feita em 07/11, Dev B com aval do Pedro)

- `app/core/regras.py`: `avaliar_regras` usa as funções do parecer para R02, R03 e
  R05; `conferir` aplica R00 antes de R01-R08. Mantém os princípios do motor:
  erro interno vira INCERTA e aprovação com strings sugeridas vira INCERTA.
- `app/core/aprovacao.py`: R00 entra nas obrigatórias; premissas e alertas não
  bloqueiam; R05 incerta confirmada pelo engenheiro não bloqueia (`r05_inmetro.bloqueia`).
- `app/core/arranjo.py`: disjuntor por tabela com In >= Ib e bitola sugerida pelo
  mesmo Iz corrigido da R02 (senão o agente sugeriria cabo que a R02 reprova).
- `app/core/perguntas.py` e `app/main.py`: pergunta e resposta de `area_concessao`.
- Testes do Dev A que fixavam o critério antigo foram reescritos para o parecer
  (ex.: disjuntor igual à corrente agora aprova; 4 mm² com 25 A reprova).
- Testes não acessam a rede: `app/conftest.py` liga `INMETRO_CONSULTA=0`.

Clique do engenheiro: `POST /processos/{id}/regras/R05/confirmar` (form
`engenheiro=<nome>`). Uma nova conferência mantém a confirmação enquanto a
evidência (registro, modelo e hash da página do INMETRO) não mudar.

## Pendências humanas (não são código)

- **Catálogo verificado** (`app/core/parecer/inmetro_verificados.json`): conferir à
  mão o certificado de 2 ou 3 inversores mais vendidos e preencher `verificado_por`
  e `verificado_em`. Hoje só há uma candidata (Sungrow SG5.0RS-L), que não conta.
- **Kit da demo**: já usa o Sungrow SG5.0RS-L real (datasheet v14, 2025); a R05 cai
  no passo 3 e o engenheiro confirma. O módulo continua sintético.
- **Proveniência dos 220 V**: `tensao_saida_v` tem 220 como padrão no schema; o
  passo 3 não distingue "datasheet diz 220 V" de "não informado".
- **Vigência da tabela da R00** (CNC-OMBR-MAT-18-0124): a Enel está renomeando as
  normas; sai como premissa declarada até alguém confirmar.
- **Tabela 37 (XLPE)**: não validada; cabo XLPE fica INCERTA na R02.
