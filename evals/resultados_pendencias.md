# Resultado do eval de pendências com LLM real

Execução de 08/11/2026 com Qwen/Qwen3.8-27B (Featherless), 48 textos sintéticos rotulados antes de rodar o modelo. Uso medido no trace: 48 chamadas, 23.370 tokens de entrada, 13.741 de saída, 591,6 s somados (cerca de 12,3 s por chamada), 0 erros.

| Método | Acerto geral | Acerto em paráfrases | n |
|---|---|---|---|
| Classe majoritária (unifilar_inconsistente; dados balanceados) | 12.5% | 14.3% | 48 |
| Linha de base: palavras-chave | 50.0% | 0.0% | 48 |
| Classificador do produto | 93.8% | 95.2% | 48 |

LLM disponível: sim.
Textos sintéticos, rotulados antes de rodar qualquer modelo.

Erros do classificador do produto:
- p18: esperado documentacao_incompleta, obtido art_irregular
- p23: esperado art_irregular, obtido outros
- p36: esperado localizacao, obtido outros
