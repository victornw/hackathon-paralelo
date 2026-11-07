# Evidências encontradas — 07/11/2026

## Resultado

Há evidência pública de esforço de elaboração e de oferta comercial para substituir
esse trabalho. A economia do nosso agente ainda não foi medida ponta a ponta.
A pesquisa não autoriza converter dias de espera em horas de trabalho economizadas.

## 1. Caso de trabalho técnico documentado

[Relatório UFCG / Ecosol, 2024](https://dspace.sti.ufcg.edu.br/jspui/bitstream/riufcg/37231/1/HENRIQUE%20FRANKLIN%20BRAZIL%20DA%20SILVA-RELAT%C3%93RIO%20DE%20EST%C3%81GIO-CEEI-ENGENHARIA%20EL%C3%89TRICA%20%282024%29.pdf).
PDF de 67 páginas baixado e conferido localmente. SHA na transcrição técnica.

- Página 25: cerca de uma semana para elaborar projetos monofásicos; 1,5–2 semanas
  para trifásicos. Usa Adobe Illustrator. São durações relatadas, não horas cronometradas.
- O relatório detalha seis projetos e declara aprovação Energisa/PB e instalação.
- Páginas 39–41: caso residencial monofásico, 12 módulos de 570 Wp e inversor de
  8 kW. Foram coletados dados, cargas, especificações, proteções e elaborado unifilar.
- A descrição apresenta inconsistências: cálculo menciona 13 módulos, mas resumo
  e strings usam 12; possibilidade declarada de expansão também não fecha.

O relato inclui dimensionamento, fora do nosso escopo. Não transferir a duração
inteira para o produto. Aprovação é declaração do autor, sem parecer original
verificado. Fonte útil para estudar o trabalho e erros, não gabarito normativo.

Artefato utilizável: [transcrição técnica sem identificação do cliente](../../fixtures/casos_publicados/ufcg_2024_projeto4.json).
Não inclui imagens, UC, CPF, endereço, coordenadas ou assinaturas do original.
Foi executado apenas o conferidor determinístico sobre a transcrição: R02 e R03
incertas, R04 aprovada numericamente. Sem chamadas de LLM. O motor levou 7,33 ms
nesta execução; isso não mede o tempo economizado no processo inteiro. Os limites
regulatórios do teste estão no [resultado](../evidencias/caso-publicado-ufcg-projeto4.json).

## 2. Oferta comercial que cobre o mesmo trabalho

[Spinatec — página consultada](https://homologacao.spinatec.com.br/contato):

| Escopo anunciado | Preço inicial anunciado |
|---|---|
| Documentação: memorial, diagramas, datasheets e formulários | R$ 250/projeto |
| Homologação completa com ART/TRT do cliente | R$ 459/projeto |
| Homologação completa com ART da prestadora | R$ 559/projeto |

A empresa declara mais de 6 mil homologações entregues e protocolo em até 3 dias
úteis. São declarações comerciais da prestadora, não números auditados de vendas.

[Raio Soluções](https://raiosolucoes.com/homologacao) anuncia homologação a partir
de R$ 450 com TRT e protocolo em até 2 dias úteis após documentos completos.
Atende outras distribuidoras; não é referência de prazo específico da Enel CE.

Conclusão: temos uma referência econômica concreta de alternativa ofertada ao
integrador. Não é prova de que nosso produto já gera esse valor ou venderá por
esse preço. Os serviços incluem responsabilidades diferentes.

## 3. Base oficial da ANEEL processada nesta pesquisa

[Conjunto oficial](https://dadosabertos.aneel.gov.br/dataset/atendimento-mmgd-mini-e-micro-geracao-distribuida).
ZIP Nordeste: 343.263.091 bytes; CSV descompactado: 3.731.835.150 bytes.
13.690.608 linhas lidas; 1.625.758 referentes à Enel CE antes da deduplicação.
Deduplicação por protocolo, preservando maior data de envio; empates usam última
linha do arquivo. Foram obtidos 35.030 pedidos da Enel CE, solicitados de
07/01/2022 a 07/01/2023. Não foram exportados CPF/CNPJ ou protocolos.

| Medida | Resultado |
|---|---|
| Pedidos B1 até 10 kW | 24.269 |
| Vistoria não solicitada, último estado informado | 378 |
| Vistoria reprovada aguardando nova solicitação, último estado | 315 |
| Total desses dois estados | 693 (2,86% do recorte) |
| Solicitação até injeção: mediana | 33 dias corridos |
| Solicitação até injeção: percentil 90 | 86 dias corridos |
| Pares de datas válidos usados | 23.571 |
| Datas ausentes / intervalos negativos excluídos | 694 / 4 |

Não é taxa histórica de ocorrência de pendência: é o último estado informado de
cada protocolo. Projetos já conectados podem ter passado por pendências antes.
A mediana exclui pedidos sem datas e não estima a espera final dos ainda abertos.
Foi usada diferença entre datas, sem contar ambos os dias inclusivamente.
Os 34/87 dias anteriores da spec foram corrigidos para esta convenção reproduzível.

Em todos os segmentos Enel CE: 304 indeferimentos por documentação incompleta e
94 orçamentos que perderam validade por não aprovação no prazo. No recorte B1
até 10 kW não há pedidos classificados como negados. Logo, não usar os 304 casos
como frequência de rejeição documental residencial. O campo de motivos dos
conectados não foi interpretado como causa, dado seu preenchimento ambíguo.

[Agregados e hash](../evidencias/dor-aneel-enel-ce.json).
Reprodução: `python scripts/analisar_dor_aneel.py data/pesquisa/nordeste.zip --saida docs/evidencias/dor-aneel-enel-ce.json`.
ZIP/CSV e PDF original ficam em `data/`, ignorados pelo Git.

## 4. Fiscalização: dor de espera confirmada, distinta de trabalho interno

[Comunicado da Arce republicado pela ABAR](https://abar.org.br/arce-aplica-multa-de-r-194-milhoes-na-enel-ceara/),
09/01/2025: 1.444 reclamações MMGD recebidas em 2024; 353 casos analisados pela
fiscalização; multa de R$ 19,4 milhões anunciada, sujeita a recurso. A publicação
relata atrasos em análises, orçamentos e vistorias. Não somar percentuais das
categorias nem tratá-los como amostra aleatória de todos os consumidores.
Nosso agente pode acompanhar e escalar; não controla a execução da distribuidora.

## Alegação sustentada para o pitch

“Encontramos um relato técnico de seis instalações que descreve semanas de
elaboração e prestadores que ofertam documentação a partir de R$ 250 por projeto.
Na base histórica da Enel CE, 693 pedidos residenciais até 10 kW estavam com
vistoria não solicitada ou reprovada aguardando nova solicitação. Automatizamos
preparação e acompanhamento; a redução de horas humanas ainda está em validação.”

Não afirmar “reduzimos uma semana para segundos”, “eliminamos os atrasos da
Enel” ou “economizamos R$ 250 por projeto” com os dados disponíveis.
