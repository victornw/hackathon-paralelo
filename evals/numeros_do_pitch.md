# Números do pitch

Fechado em 07/11/2026. Cada número aponta para a fonte e para o script que o gera.
Nada aqui é estimativa sem rótulo: o que é conta nossa está marcado.

## Mercado e dor (ANEEL, pedidos de 2022 a 2023)

Base: "Atendimento a pedidos de conexões MMGD, pós Lei 14.300", ZIPs das cinco regiões
(extração de 28/10/2026), recorte residencial B1, solar, até 10 kW, solicitação entre
07/01/2022 e 07/01/2023. Gerado por `python -m evals.run --aneel data/aneel/zips`.

| Número | Valor |
|---|---|
| Pedidos residenciais solares até 10 kW, em um ano | **974.941** (52 distribuidoras) |
| Casos-problema: negados ou com vistoria parada | **127.075** |
| Casos-problema em categorias que o agente cobre | **76.433 (60,1%)** |
| Negados por documentação incorreta | 39.485 |
| Vistoria não solicitada | 16.919 |
| Cemig: casos cobertos | 13.872 de 17.987 (77,1%); 1 em cada 6 pedidos negados por documentação |
| Equatorial AL: casos cobertos | 4.601 de 5.746 (80,1%); 1 em cada 7 pedidos negados por documentação |
| Enel CE: casos cobertos | 378 de 693 (54,5%); nenhum negado por documentação |

Dizer sempre "segundo a ANEEL, em 2022 e 2023". Não há base mais recente com esse detalhe.

## Mercado endereçável (conta nossa)

| Número | Valor | Fonte |
|---|---|---|
| Integradores que terceirizam projeto e engenharia | 37% | Greener, set/2025 |
| Conexões novas por ano | ~600 mil | pv magazine (ritmo de 2026) |
| Processos terceirizados por ano | **~222 mil** | 600 mil × 37% (conta nossa) |
| Preço que o integrador paga hoje | R$ 400 a 690 avulso; R$ 250 a 400 em assinatura | páginas públicas das homologadoras (Raio, Spinatec, Solardesc) |
| Referência de produtividade | Tellar: 14 engenheiros, ~350 projetos/mês, ~1 projeto por engenheiro por dia útil | pv magazine, nov/2024 |

## O produto, medido

| Número | Valor | Fonte |
|---|---|---|
| Classificador de pendências, acerto geral | **93,8%** (95,2% em paráfrases), contra 50,0% de palavras-chave | `evals/resultados_pendencias.md` (Qwen real, 48 textos sintéticos rotulados antes) |
| Processo completo com IA real | **6 de 6 concluídos**, da conta ao protocolo | `evals/resultados_processo_completo.md` |
| Chamadas de IA por processo | 8 (o agente decide cada passo e a IA confere a conta) | idem |
| Tokens por processo | ~13 mil | idem |
| Tempo de máquina por processo | ~90 s | idem |
| Custo de IA por processo | ~R$ 0,07 (preço publicado da Featherless, US$ 0,40/3,00 por milhão de tokens) | idem |
| Revisão do engenheiro | 15 a 20 min por pacote (hipótese da equipe; a tela grava o tempo real de cada revisão) | `app/web/revisao.py` |

## Frases

- "Segundo a ANEEL, em um ano, 127 mil pedidos residenciais de energia solar foram negados ou pararam na vistoria. 60% deles, 76 mil, em problemas que o agente previne: documentação e vistoria esquecida."
- "Hoje um engenheiro de homologadora monta cerca de um projeto por dia. Com o agente, ele revisa um pacote já conferido em 15 a 20 minutos."
- "O agente gasta uns 7 centavos de IA por processo; o custo que importa é o tempo do engenheiro, e é ele que reduzimos."
