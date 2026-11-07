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

## Integração em `conferir` (Dev A)

```python
from app.core.parecer import REGRAS_PARECER  # {"R00": ..., "R02": ..., "R03": ..., "R05": ...}

def conferir(processo):
    resultados = [REGRAS_PARECER["R00"](processo)]          # primeiro
    for regra in REGRAS:
        if regra.id in REGRAS_PARECER:
            resultados.append(REGRAS_PARECER[regra.id](processo))
        else:
            resultados.append(_aplicar(regra, processo))     # R01, R04, R06-R08 como hoje
    return resultados
```

Essas funções não usam `Regra.a_validar`: o parecer fechou as premissas que
deixavam R02 e R03 incertas. O que continua sem dado vira premissa declarada
(aprovada, com o texto "Aprovado com premissa assumida: ...") ou INCERTA quando o
parecer manda (comprimento do cabo, área de concessão, cabo XLPE, R05 sem prova).

## Política de aprovação (`app/core/aprovacao.py`)

1. Incluir `R00` nas obrigatórias (reprovação bloqueia; INCERTA também).
2. Premissas e alertas não bloqueiam: aparecem na revisão.
3. R05 INCERTA confirmada pelo engenheiro não bloqueia. Usar
   `app.core.parecer.r05_inmetro.bloqueia(resultado)` para a R05.

O clique do engenheiro já tem rota: `POST /processos/{id}/regras/R05/confirmar`
(form `engenheiro=<nome>`), que grava `confirmado_por` e `confirmado_em`. Uma nova
conferência mantém a confirmação enquanto a evidência (registro, modelo e hash
da página do INMETRO) não mudar.

## Perguntas novas para `perguntas_pendentes`

- `area_concessao` (R03): "ceara", "sao_paulo", "rj_serra", "rj_sul_fluminense", "rj_demais".
- `distancia_inversor_quadro_m` passa a ser obrigatório (R02, queda de tensão).
- Opcionais (sem resposta vira premissa): `metodo_instalacao` (A1, A2, B1, B2, C),
  `isolacao` (PVC, XLPE), `ambiente_cabo` (interno, exposto), `circuitos_agrupados`, `icc_ka`.
- `certificado_inmetro`: número do registro (R05).

## Pendências humanas (não são código)

- **Catálogo verificado** (`app/core/parecer/inmetro_verificados.json`): conferir à
  mão o certificado de 2 ou 3 inversores mais vendidos e preencher `verificado_por`
  e `verificado_em`. Hoje só há uma candidata (Sungrow SG5.0RS-L), que não conta.
- **Kit da demo**: os casos prontos usam um inversor sintético (`SIMULADO-...`), que
  nunca passa na R05. Trocar por um inversor do catálogo verificado, com dados do
  datasheet real.
- **Vigência da tabela da R00** (CNC-OMBR-MAT-18-0124): a Enel está renomeando as
  normas; sai como premissa declarada até alguém confirmar.
- **Tabela 37 (XLPE)**: não validada; cabo XLPE fica INCERTA na R02.
