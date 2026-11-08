# Resultado do processo completo com LLM real

Execução de 07/11/2026 com Qwen/Qwen3.8-27B (Featherless), casos de exemplo 1 e 3 (`fixtures/contas/`), 3 repetições cada, via `evals/processo_completo.py` (o app dirigido pela API, sem atalhos nas regras). O caso 2 tem microinversor, fora do escopo do MVP: o agente para na geração do unifilar e explica o motivo, como esperado.

| caso | rep | etapa final | aprovado | rodadas | retentativas | chamadas LLM | tokens in | tokens out | LLM s | total s | erros |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | concluido | sim | 1 | 0 | 2 | 1938 | 1077 | 42.1 | 48.0 | 0 |
| 3 | 1 | concluido | sim | 1 | 0 | 2 | 1979 | 1993 | 67.2 | 69.9 | 0 |
| 1 | 2 | concluido | sim | 1 | 0 | 2 | 1938 | 1300 | 48.5 | 52.0 | 0 |
| 3 | 2 | concluido | sim | 1 | 0 | 2 | 1979 | 1009 | 45.6 | 48.3 | 0 |
| 1 | 3 | concluido | sim | 1 | 0 | 2 | 1938 | 712 | 23.9 | 27.3 | 0 |
| 3 | 3 | concluido | sim | 1 | 0 | 2 | 1979 | 1349 | 12.7 | 15.4 | 0 |

Médias de 6 execução(ões), 6 concluída(s): 2.0 chamadas LLM, 1958 tokens in, 1240 tokens out, 40.0 s de LLM, 43.5 s de relógio.
Tokens gastos no total: 19191 (11751 in, 7440 out).

Custo por processo (conta nossa): a Featherless não publica preço por token. Pela faixa pública de modelos Qwen da mesma classe (US$ 0,08 a 0,57 por milhão de tokens, ver `docs/pesquisa/anexos/prova-de-custo.md`), cerca de 3,2 mil tokens custam menos de US$ 0,002, ou seja, menos de 2 centavos de real por processo. O custo fixo relevante é o plano Developer da Featherless (US$ 50/mês, cerca de R$ 2,75 por processo a 100 processos por mês).
