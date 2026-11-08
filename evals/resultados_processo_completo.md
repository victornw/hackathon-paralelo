# Resultado do processo completo com LLM real

Execução de 08/11/2026 com Qwen/Qwen3.8-27B (Featherless), casos de exemplo 1 e 3 (`fixtures/contas/`), 3 repetições cada, pelo fluxo do produto: "Começar" no exemplo (conta e proposta enviadas juntas), o agente decide cada passo com o modelo (Vercel AI SDK), as perguntas abertas recebem as respostas pré-preenchidas, o engenheiro confirma a R05, aprova e usa o protocolo simulado. Consulta ao INMETRO desligada (`INMETRO_CONSULTA=0`). O caso 2 tem microinversor, fora do escopo do MVP.

| caso | rep | etapa final | chamadas LLM | tokens in | tokens out | relógio s | custo R$ |
|---|---|---|---|---|---|---|---|
| 1 | 1 | protocolado | 8 | 9755 | 2351 | 86.6 | 0.0603 |
| 3 | 1 | protocolado | 8 | 10316 | 3441 | 94.9 | 0.0795 |
| 1 | 2 | protocolado | 8 | 10181 | 2375 | 71.8 | 0.0616 |
| 3 | 2 | protocolado | 8 | 10063 | 3412 | 119.9 | 0.0785 |
| 1 | 3 | protocolado | 8 | 9664 | 4184 | 102.1 | 0.0903 |
| 3 | 3 | protocolado | 8 | 10218 | 2338 | 67.1 | 0.0611 |

Médias de 6 execução(ões), 6 concluída(s): 8.0 chamadas LLM, 10033 tokens in, 3017 tokens out, 90.4 s de relógio.
Custo médio por processo: R$ 0.0719

Custo: preço publicado da Featherless para o Qwen3.8-27B (US$ 0,40 por milhão de tokens de entrada e US$ 3,00 por milhão de saída) e PTAX de venda de 06/11/2026 (R$ 5,5013), aplicado aos tokens gravados no rastro de cada passo. As 8 chamadas por processo: decisões do agente sobre o próximo passo, leitura da proposta, conferência da conta pela IA. O custo fixo relevante é o plano Developer da Featherless (US$ 50/mês).

Antes de 08/11 este arquivo registrava ~3,2 mil tokens e 2 chamadas por processo: a medição antiga não passava pelo modelo de decisão nem pela conferência da conta pela IA.
